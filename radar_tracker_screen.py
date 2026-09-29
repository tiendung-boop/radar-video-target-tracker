"""
Radar Tracking Pipeline — Nguon: man hinh truc tiep (mss screen capture)
- Phat hien blip + OCR so hieu moi 10 frame
- Bam sat track qua cac frame (theo ID hoac vi tri gan nhat)
- Du doan quy dao 30 giay tiep theo
- Hien thi truc tiep; hover chuot de xem thong tin blip
- Xuat video co chu thich (output_tracking_screen.mp4) neu RECORD_OUTPUT = True
"""
import cv2
import numpy as np
import json
import mss
import mss.tools
from ultralytics import YOLO
from collections import defaultdict
import pygame
import threading
import queue
import os
import time
from PIL import Image, ImageDraw, ImageFont

try:
    _PIL_FONT    = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf",   18)
    _PIL_FONT_BD = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 18)
except Exception:
    _PIL_FONT = _PIL_FONT_BD = ImageFont.load_default()

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
MODEL_PATH   = r"c:\Users\ygost\radar\runs\ocr\weights\best.pt"
OUTPUT_PATH  = r"c:\Users\ygost\radar\output_tracking_screen.mp4"
RECORD_OUTPUT = True   # dat False neu khong muon ghi video ra file

# Screen capture
CAPTURE_MONITOR = 1       # 1 = man hinh chinh; tang len cho man hinh thu 2, 3...
CAPTURE_REGION  = None    # None = toan bo monitor
#   Hoac chi dinh vung cut: (left, top, width, height), vi du:
#   CAPTURE_REGION = (0, 0, 1544, 1044)
TARGET_FPS   = 30         # toc do chup man hinh (frame/giay)

# Radar calibration — KHONG THAY DOI (xem CLAUDE.md)
CX, CY   = 772, 522
R_300KM  = 438
KM_PX    = 300.0 / R_300KM   # ~0.6849 km/px

# Pipeline params
OCR_EVERY   = 10
CONF_THRESH = 0.45
PAD         = 35
ZOOM_SIZE   = 280

# Track params
MAX_LOST    = 60
ASSOC_DIST  = 30
TAIL_LEN    = 25
PRED_SEC    = 30

# Hover tooltip
HOVER_RADIUS = 22

# Audio
SPEAK_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speak")
_audio_queue  = queue.Queue()
_audio_cancel = threading.Event()
_tts_last_tid = None

# Mau ve (BGR)
COLOR_MAP = {
    "RED":     (60,  60,  255),
    "GREEN":   (60,  220,  60),
    "YELLOW":  (0,   220, 220),
    "CYAN":    (220, 200,  30),
    "MAGENTA": (220,  60, 220),
}
UNKNOWN_COL = (160, 160, 160)

# Global mouse state
mouse_x, mouse_y = 0, 0

# Table layout
TABLE_W       = 510
TABLE_WIN_H   = 300
TABLE_TITLE_H = 36
TABLE_HDR_H   = 30
TABLE_ROW_H   = 28
_COL_DIV  = [0, 42, 130, 198, 288, 378, TABLE_W]
_COL_HDR  = ["STT", "Mau", "ID", "Cu ly(km)", "GPV(deg)", "Toc(km/h)"]
table_img    = None
table_scroll_y = 0

def on_mouse(event, x, y, flags, param):
    global mouse_x, mouse_y
    mouse_x, mouse_y = x, y

def on_table_scroll(event, x, y, flags, param):
    global table_scroll_y
    if event == cv2.EVENT_MOUSEWHEEL:
        step = TABLE_ROW_H * 3
        if flags > 0:
            table_scroll_y = max(0, table_scroll_y - step)
        else:
            table_scroll_y += step

# ══════════════════════════════════════════════════════════════════════════════
# BLIP DETECTION
# ══════════════════════════════════════════════════════════════════════════════
def detect_blips(img):
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask_radar = np.zeros((h, w), np.uint8)
    cv2.circle(mask_radar, (CX, CY), R_300KM, 255, -1)

    color_masks = {
        "RED":     cv2.bitwise_or(cv2.inRange(hsv,(0,130,130),(12,255,255)),
                                  cv2.inRange(hsv,(168,130,130),(180,255,255))),
        "GREEN":   cv2.inRange(hsv,(40,80,130),(85,255,255)),
        "YELLOW":  cv2.inRange(hsv,(18,130,130),(38,255,255)),
        "CYAN":    cv2.inRange(hsv,(85,80,130),(105,255,255)),
        "MAGENTA": cv2.inRange(hsv,(135,80,130),(165,255,255)),
    }
    _color_order = list(color_masks.keys())
    color_label  = np.zeros((h, w), dtype=np.uint8)
    combined     = np.zeros((h, w), np.uint8)
    for ci, (cname, m) in enumerate(color_masks.items(), 1):
        m = cv2.bitwise_and(m, mask_radar)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2,2), np.uint8))
        color_label[m > 0] = ci
        combined = cv2.bitwise_or(combined, m)

    _, lbl, stats, centroids = cv2.connectedComponentsWithStats(combined, 8)
    raw = []
    for i in range(1, int(stats.shape[0])):
        x0, y0, bw, bh, area = stats[i]
        if area < 5 or area > 1200: continue
        if max(bw,bh) / max(min(bw,bh),1) > 8: continue
        bx = int(centroids[i][0]); by = int(centroids[i][1])
        dx = (bx - CX)*KM_PX; dy = (CY - by)*KM_PX
        dist = float(np.sqrt(dx**2 + dy**2))
        if dist > 305: continue
        valid_px = color_label[lbl == i]
        valid_px = valid_px[valid_px > 0]
        if valid_px.size > 0:
            dom = _color_order[int(np.bincount(valid_px).argmax()) - 1]
        else:
            dom = "?"
        bearing = float(np.degrees(np.arctan2(dx, dy)) % 360)
        raw.append((bx, by, int(area), dist, bearing, dom, dx, dy))

    raw.sort(key=lambda x: x[3])
    merged, used = [], set()
    for i, b in enumerate(raw):
        if i in used: continue
        grp = [b]
        for j, b2 in enumerate(raw):
            if j <= i or j in used: continue
            if abs(b[0]-b2[0]) < 20 and abs(b[1]-b2[1]) < 20:
                grp.append(b2); used.add(j)
        merged.append(max(grp, key=lambda x: x[2])); used.add(i)
    return merged

# ══════════════════════════════════════════════════════════════════════════════
# OCR
# ══════════════════════════════════════════════════════════════════════════════
yolo = YOLO(MODEL_PATH)

def ocr_blip(frame, bx, by):
    h, w = frame.shape[:2]
    x1=max(0,bx-PAD); x2=min(w,bx+PAD)
    y1=max(0,by-PAD); y2=min(h,by+PAD)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0: return ""
    zoomed = cv2.resize(crop, (ZOOM_SIZE, ZOOM_SIZE), interpolation=cv2.INTER_CUBIC)
    preds  = yolo(zoomed, verbose=False, conf=CONF_THRESH)[0]
    if preds.boxes is None or len(preds.boxes) == 0: return ""

    dets = []
    for box in preds.boxes:
        x1b,y1b,x2b,y2b = box.xyxy[0].tolist()
        xc=(x1b+x2b)/2; yc=(y1b+y2b)/2
        digit = str((int(box.cls[0]) + 1) % 10)
        dets.append((xc, yc, digit, float(box.conf[0])))
    if not dets: return ""

    dets.sort(key=lambda d: d[1])
    lines, cur = [], [dets[0]]
    for d in dets[1:]:
        if abs(d[1]-cur[-1][1]) < 22: cur.append(d)
        else: lines.append(cur); cur = [d]
    lines.append(cur)

    cx = cy = ZOOM_SIZE / 2
    best, bd = None, float("inf")
    for ln in lines:
        if not (2 <= len(ln) <= 6): continue
        lx = sum(d[0] for d in ln)/len(ln)
        ly = sum(d[1] for d in ln)/len(ln)
        dist = np.sqrt((lx-cx)**2+(ly-cy)**2)
        if dist < bd: bd=dist; best=ln
    if best is None: return ""
    best.sort(key=lambda d: d[0])
    return "".join(d[2] for d in best)

# ══════════════════════════════════════════════════════════════════════════════
# TRACK MANAGER
# ══════════════════════════════════════════════════════════════════════════════
class TrackManager:
    def __init__(self, fps):
        self.fps = fps
        self.tracks = {}
        self._unnamed = 0

    def _new_anon(self):
        self._unnamed += 1
        return f"?{self._unnamed}"

    def update(self, frame_idx, blips, ocr_results):
        t_sec = frame_idx / self.fps

        active = {tid: info for tid, info in self.tracks.items()
                  if frame_idx - info["last_frame"] <= MAX_LOST}
        self.tracks = active

        matched_track_ids = set()

        for (bx,by,area,dist,bear,color,dx,dy), tid_ocr in zip(blips, ocr_results):
            tid = tid_ocr.strip() if tid_ocr.strip() else None

            if not tid:
                best_match = None; best_px_dist = ASSOC_DIST
                for etid, einfo in active.items():
                    if etid in matched_track_ids: continue
                    if not einfo["history"]: continue
                    ex, ey = einfo["history"][-1][3], einfo["history"][-1][4]
                    d = np.sqrt((bx-ex)**2+(by-ey)**2)
                    if d < best_px_dist:
                        best_px_dist = d; best_match = etid
                tid = best_match if best_match else self._new_anon()

            if tid not in self.tracks:
                self.tracks[tid] = {"history": [], "color": color, "last_frame": frame_idx}

            info = self.tracks[tid]
            info["history"].append((t_sec, dx, dy, bx, by))
            if len(info["history"]) > 200:
                info["history"] = info["history"][-200:]
            info["last_frame"] = frame_idx
            info["color"]      = color
            matched_track_ids.add(tid)

    def get_velocity(self, tid, min_pts=3):
        hist = self.tracks[tid]["history"]
        if len(hist) < min_pts: return None, None
        recent = hist[-min(10, len(hist)):]
        ts  = np.array([h[0] for h in recent])
        xs  = np.array([h[1] for h in recent])
        ys  = np.array([h[2] for h in recent])
        dt  = ts[-1] - ts[0]
        if dt < 0.5: return None, None
        vx = float(np.polyfit(ts, xs, 1)[0])
        vy = float(np.polyfit(ts, ys, 1)[0])
        return vx, vy

    def predict_pos(self, tid, t_ahead_sec):
        vx, vy = self.get_velocity(tid)
        if vx is None: return None
        hist = self.tracks[tid]["history"]
        t0, x0, y0 = hist[-1][0], hist[-1][1], hist[-1][2]
        xp = x0 + vx * t_ahead_sec
        yp = y0 + vy * t_ahead_sec
        pxp = int(CX + xp / KM_PX)
        pyp = int(CY - yp / KM_PX)
        return xp, yp, pxp, pyp

# ══════════════════════════════════════════════════════════════════════════════
# TOOLTIP
# ══════════════════════════════════════════════════════════════════════════════
def draw_tooltip(canvas, tid, info, tm, mx, my):
    hist = info["history"]
    if not hist: return

    _, xkm, ykm, _, _ = hist[-1]
    dist = float(np.sqrt(xkm**2 + ykm**2))
    bear = float(np.degrees(np.arctan2(xkm, ykm)) % 360)
    color = COLOR_MAP.get(info["color"], UNKNOWN_COL)
    display_id = tid if not tid.startswith("?") else "???"

    _LOAI_VN = {"RED": "Quân sự", "GREEN": "Quá cảnh", "YELLOW": "Không xác định",
                "CYAN": "Địch", "MAGENTA": "Quốc tế"}
    color_vn = _LOAI_VN.get(info["color"], info["color"])

    lines = [
        (f"ID: {display_id}",         (220, 220, 220), _PIL_FONT),
        (f"Loại: {color_vn} ", color, _PIL_FONT_BD),
        (f"Cự ly:  {dist:.0f}",       (220, 220, 220), _PIL_FONT),
        (f"Phương vị:  {bear:.0f}",   (220, 220, 220), _PIL_FONT),
    ]

    LINE_H = 26
    PAD_T  = 10
    W_BOX  = 210
    H_BOX  = len(lines) * LINE_H + PAD_T * 2

    h, w = canvas.shape[:2]
    bx = mx + 24
    by = my - H_BOX // 2
    if bx + W_BOX > w: bx = mx - W_BOX - 24
    by = max(4, min(by, h - H_BOX - 4))

    cv2.rectangle(canvas, (bx - 2, by - 2), (bx + W_BOX + 2, by + H_BOX + 2), color, 2)
    cv2.rectangle(canvas, (bx, by), (bx + W_BOX, by + H_BOX), (10, 10, 10), -1)

    pil_img = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    draw    = ImageDraw.Draw(pil_img)
    for i, (text, tcol, fnt) in enumerate(lines):
        tx = bx + PAD_T
        ty = by + PAD_T + i * LINE_H
        draw.text((tx, ty), text, font=fnt, fill=(tcol[2], tcol[1], tcol[0]))
    np.copyto(canvas, cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR))

# ══════════════════════════════════════════════════════════════════════════════
# AUDIO
# ══════════════════════════════════════════════════════════════════════════════
_COLOR_FILE = {
    "RED":     "quan_su",
    "GREEN":   "qua_canh",
    "YELLOW":  "khong_xac_dinh",
    "CYAN":    "dich",
    "MAGENTA": "quoc_te",
}

def _play_clip(name: str) -> bool:
    path = os.path.join(SPEAK_DIR, f"{name}.wav")
    if not os.path.exists(path):
        return True
    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if _audio_cancel.is_set():
                pygame.mixer.music.stop()
                return False
            time.sleep(0.02)
    except Exception as e:
        print(f"[AUDIO] LOI phat {name}: {e}", flush=True)
    return not _audio_cancel.is_set()

def _audio_worker():
    while True:
        clips = _audio_queue.get()
        if clips is None:
            break
        _audio_cancel.clear()
        print(f"[AUDIO] Doc: {' '.join(clips)}", flush=True)
        for clip in clips:
            if not _play_clip(clip):
                break

def _digits(n: int) -> list:
    return list(str(max(0, int(n))))

def speak_target(tid, info, tm):
    hist = info["history"]
    if not hist:
        return

    _, xkm, ykm, _, _ = hist[-1]
    dist = int(np.sqrt(xkm**2 + ykm**2) + 0.5)
    bear = int(np.degrees(np.arctan2(xkm, ykm)) % 360 + 0.5)

    clips = ["muc_tieu"]

    if tid.isdigit():
        clips.extend(list(tid))

    color_file = _COLOR_FILE.get(info["color"])
    if color_file:
        clips.append(color_file)

    clips.append("cu_ly")
    clips.extend(_digits(dist))

    clips.append("phuong_vi")
    clips.extend(_digits(bear))

    _audio_cancel.set()
    while not _audio_queue.empty():
        try: _audio_queue.get_nowait()
        except queue.Empty: break
    _audio_queue.put(clips)

# ══════════════════════════════════════════════════════════════════════════════
# DRAW FRAME
# ══════════════════════════════════════════════════════════════════════════════
def draw_frame(canvas, frame_idx, tm, fps, t_real, mx=0, my=0):
    hovered_tid = None

    for tid, info in tm.tracks.items():
        if frame_idx - info["last_frame"] > OCR_EVERY * 3:
            continue

        hist  = info["history"]
        color = COLOR_MAP.get(info["color"], UNKNOWN_COL)
        if not hist: continue

        t_last, xkm, ykm, px_last, py_last = hist[-1]

        tail_pts = hist[-TAIL_LEN:]
        for k in range(1, len(tail_pts)):
            alpha = k / len(tail_pts)
            c = tuple(int(v * alpha * 0.7) for v in color)
            p1 = (tail_pts[k-1][3], tail_pts[k-1][4])
            p2 = (tail_pts[k][3],   tail_pts[k][4])
            cv2.line(canvas, p1, p2, c, 1)

        pred = tm.predict_pos(tid, PRED_SEC)
        if pred:
            xp, yp, pxp, pyp = pred
            steps = 8
            for s in range(steps):
                frac1 = s / steps; frac2 = (s+1) / steps
                ix1 = int(px_last + (pxp - px_last) * frac1)
                iy1 = int(py_last + (pyp - py_last) * frac1)
                ix2 = int(px_last + (pxp - px_last) * frac2)
                iy2 = int(py_last + (pyp - py_last) * frac2)
                if s % 2 == 0:
                    cv2.line(canvas, (ix1, iy1), (ix2, iy2), color, 1)
            cv2.arrowedLine(canvas,
                (int(px_last+(pxp-px_last)*0.88), int(py_last+(pyp-py_last)*0.88)),
                (pxp, pyp), color, 1, tipLength=0.4)

        cv2.circle(canvas, (px_last, py_last), 9, color, 2)
        cv2.line(canvas, (px_last - 5, py_last), (px_last + 5, py_last), color, 1)
        cv2.line(canvas, (px_last, py_last - 5), (px_last, py_last + 5), color, 1)

        if (mx - px_last)**2 + (my - py_last)**2 <= HOVER_RADIUS**2:
            hovered_tid = tid

    if hovered_tid and hovered_tid in tm.tracks:
        draw_tooltip(canvas, hovered_tid, tm.tracks[hovered_tid], tm, mx, my)

    n_active = sum(1 for tid, info in tm.tracks.items()
                   if frame_idx - info["last_frame"] <= OCR_EVERY * 3
                   and not tid.startswith("?"))
    mins = int(t_real // 60); secs = int(t_real % 60)
    bar = f"  t = {mins:02d}:{secs:02d}   |   {n_active} muc tieu nhan dien   |   Radar 300km   |   [Q/Esc] thoat"
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 22), (0, 0, 0), -1)
    cv2.putText(canvas, bar, (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 220), 1)

    return hovered_tid

# ══════════════════════════════════════════════════════════════════════════════
# TABLE
# ══════════════════════════════════════════════════════════════════════════════
def build_table(tm, frame_idx):
    active = [
        (tid, info) for tid, info in tm.tracks.items()
        if frame_idx - info["last_frame"] <= OCR_EVERY * 3
    ]
    active.sort(key=lambda x: (x[0].startswith("?"), x[0]))

    n   = max(len(active), 1)
    H   = TABLE_TITLE_H + TABLE_HDR_H + n * TABLE_ROW_H + 4
    img = np.full((H, TABLE_W, 3), (20, 20, 20), dtype=np.uint8)

    cv2.rectangle(img, (0, 0), (TABLE_W, TABLE_TITLE_H), (0, 55, 55), -1)
    cv2.putText(img, "DANH SACH MUC TIEU", (10, TABLE_TITLE_H - 9),
                cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 230, 230), 2, cv2.LINE_AA)
    n_named = sum(1 for t, _ in active if not t.startswith("?"))
    cv2.putText(img, f"{n_named}/{len(active)}",
                (TABLE_W - 60, TABLE_TITLE_H - 9),
                cv2.FONT_HERSHEY_SIMPLEX, 0.46, (150, 200, 150), 1, cv2.LINE_AA)

    hy = TABLE_TITLE_H
    cv2.rectangle(img, (0, hy), (TABLE_W, hy + TABLE_HDR_H), (38, 38, 38), -1)
    for j, name in enumerate(_COL_HDR):
        cv2.putText(img, name, (_COL_DIV[j] + 5, hy + TABLE_HDR_H - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, (0, 210, 210), 1, cv2.LINE_AA)
    cv2.line(img, (0, hy + TABLE_HDR_H), (TABLE_W, hy + TABLE_HDR_H), (90, 90, 90), 1)

    for i, (tid, info) in enumerate(active):
        ry    = TABLE_TITLE_H + TABLE_HDR_H + i * TABLE_ROW_H
        bg    = (32, 32, 32) if i % 2 == 0 else (22, 22, 22)
        cv2.rectangle(img, (0, ry), (TABLE_W, ry + TABLE_ROW_H), bg, -1)

        hist  = info["history"]
        color = COLOR_MAP.get(info["color"], UNKNOWN_COL)
        did   = tid if not tid.startswith("?") else "???"

        dist_str  = "---"
        bear_str  = "---"
        speed_str = "---"
        if hist:
            _, xkm, ykm, _, _ = hist[-1]
            dist_str = f"{float(np.sqrt(xkm**2 + ykm**2)):.0f}"
            bear_str = f"{float(np.degrees(np.arctan2(xkm, ykm)) % 360):.0f}"
            vx, vy = tm.get_velocity(tid)
            if vx is not None:
                speed_str = f"{float(np.sqrt(vx**2 + vy**2)) * 3600:.0f}"

        ty    = ry + TABLE_ROW_H - 7
        cells = [
            (str(i + 1),     (180, 180, 180)),
            (info["color"],  color),
            (did,            color),
            (dist_str,       (215, 215, 215)),
            (bear_str,       (215, 215, 215)),
            (speed_str,      (215, 215, 215)),
        ]
        for (text, tcol), cx in zip(cells, _COL_DIV):
            cv2.putText(img, text, (cx + 5, ty),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, tcol, 1, cv2.LINE_AA)

        cv2.line(img, (0, ry + TABLE_ROW_H), (TABLE_W, ry + TABLE_ROW_H), (48, 48, 48), 1)

    for x in _COL_DIV[1:-1]:
        cv2.line(img, (x, TABLE_TITLE_H), (x, H - 1), (60, 60, 60), 1)

    cv2.rectangle(img, (0, 0), (TABLE_W - 1, H - 1), (80, 80, 80), 1)
    return img

# ══════════════════════════════════════════════════════════════════════════════
# LIVE HTML
# ══════════════════════════════════════════════════════════════════════════════
_HTML_PATH = r"c:\Users\ygost\radar\live_tracks.html"
_LOAI_VN   = {"RED":"Quân sự","GREEN":"Quá cảnh","YELLOW":"Không xác định",
               "CYAN":"Địch","MAGENTA":"Quốc tế"}
_CSS_COLOR = {"RED":"#ff4444","GREEN":"#44dd44","YELLOW":"#dddd00",
              "CYAN":"#00dddd","MAGENTA":"#dd44dd"}

def write_live_html(tm, frame_idx, fps, t_real):
    active = [(tid, info) for tid, info in tm.tracks.items()
              if frame_idx - info["last_frame"] <= OCR_EVERY * 3]
    active.sort(key=lambda x: (x[0].startswith("?"), x[0]))

    mins = int(t_real // 60); secs = int(t_real % 60)
    n_named = sum(1 for t, _ in active if not t[0].startswith("?"))

    rows = []
    for i, (tid, info) in enumerate(active, 1):
        hist  = info["history"]
        color = _CSS_COLOR.get(info["color"], "#aaaaaa")
        did   = tid if not tid.startswith("?") else "???"
        loai  = _LOAI_VN.get(info["color"], info["color"])
        dist_str = bear_str = spd_str = "---"
        if hist:
            _, xkm, ykm, _, _ = hist[-1]
            dist_str = f"{float(np.sqrt(xkm**2+ykm**2)):.0f}"
            bear_str = f"{float(np.degrees(np.arctan2(xkm,ykm))%360):.0f}"
            vx, vy = tm.get_velocity(tid)
            if vx is not None:
                spd_str = f"{float(np.sqrt(vx**2+vy**2))*3600:.0f}"
        rows.append(f"""<tr>
          <td>{i}</td>
          <td style="color:{color};font-weight:bold">{loai}</td>
          <td style="color:{color};font-weight:bold">{did}</td>
          <td>{dist_str}</td>
          <td>{bear_str}</td>
          <td>{spd_str}</td>
        </tr>""")

    rows_html = "\n".join(rows) if rows else '<tr><td colspan="6" style="text-align:center;color:#666">Chưa phát hiện mục tiêu</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="2">
<title>Radar Live</title>
<style>
  body {{ background:#0a0a0a; color:#ddd; font-family:monospace; margin:0; padding:12px; }}
  h2   {{ color:#00dddd; margin:0 0 6px 0; font-size:16px; letter-spacing:2px; }}
  .info {{ color:#888; font-size:12px; margin-bottom:10px; }}
  table {{ border-collapse:collapse; width:100%; max-width:600px; }}
  th {{ background:#0d3333; color:#00dddd; padding:7px 10px; text-align:left; font-size:13px; border-bottom:1px solid #1a5555; }}
  td {{ padding:6px 10px; font-size:13px; border-bottom:1px solid #1a1a1a; }}
  tr:hover td {{ background:#111; }}
</style>
</head>
<body>
<h2>&#9632; RADAR LIVE — DANH SÁCH MỤC TIÊU (MÀN HÌNH TRỰC TIẾP)</h2>
<div class="info">
  t = {mins:02d}:{secs:02d} &nbsp;|&nbsp; frame {frame_idx} &nbsp;|&nbsp;
  <b style="color:#44dd44">{n_named}</b> / {len(active)} mục tiêu nhận diện
  &nbsp;|&nbsp; <span style="color:#555">tự cập nhật mỗi 2s</span>
</div>
<table>
  <thead><tr>
    <th>#</th><th>Loại</th><th>ID</th>
    <th>Cự ly (km)</th><th>Phương vị (°)</th><th>Tốc độ (km/h)</th>
  </tr></thead>
  <tbody>{rows_html}</tbody>
</table>
</body>
</html>"""

    _tmp = _HTML_PATH + ".tmp"
    with open(_tmp, "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(_tmp, _HTML_PATH)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
try:
    pygame.mixer.init()
    print("[AUDIO] pygame.mixer OK", flush=True)
except Exception as e:
    print(f"[AUDIO] pygame.mixer FAILED: {e}", flush=True)

threading.Thread(target=_audio_worker, daemon=True).start()

FPS = TARGET_FPS

# Khoi tao mss va lay kich thuoc vung chup
with mss.mss() as _sct:
    _mon_info = _sct.monitors[CAPTURE_MONITOR]
    if CAPTURE_REGION:
        _region = {"top": CAPTURE_REGION[1], "left": CAPTURE_REGION[0],
                   "width": CAPTURE_REGION[2], "height": CAPTURE_REGION[3]}
    else:
        _region = _mon_info
    W = _region["width"]
    H_FRAME = _region["height"]

print(f"Screen capture: {W}x{H_FRAME}, target {FPS}fps, monitor={CAPTURE_MONITOR}")
if CAPTURE_REGION:
    print(f"  Vung chup: {CAPTURE_REGION}")
print("Hover chuot len blip de xem thong tin. Nhan Q hoac Esc de thoat.")

writer = None
if RECORD_OUTPUT:
    writer = cv2.VideoWriter(OUTPUT_PATH, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H_FRAME))
    if not writer.isOpened():
        writer = cv2.VideoWriter(OUTPUT_PATH.replace(".mp4", ".avi"),
                                 cv2.VideoWriter_fourcc(*"MJPG"), FPS, (W, H_FRAME))
        print("mp4v codec not available, falling back to MJPG (.avi)")
    print(f"Ghi video: {OUTPUT_PATH}")

tm = TrackManager(FPS)
table_img = build_table(tm, 0)

cv2.namedWindow("Radar Tracker", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Radar Tracker", W, H_FRAME)
cv2.setMouseCallback("Radar Tracker", on_mouse)

cv2.namedWindow("Bang thong tin", cv2.WINDOW_AUTOSIZE)
cv2.setMouseCallback("Bang thong tin", on_table_scroll)

frame_idx = 0
t_start   = time.perf_counter()
_frame_dur = 1.0 / FPS

try:
    with mss.mss() as sct:
        region = _region
        while True:
            t0 = time.perf_counter()

            # Chup man hinh
            shot  = sct.grab(region)
            frame = cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
            t_real = t0 - t_start

            # Phat hien + OCR moi OCR_EVERY frame
            if frame_idx % OCR_EVERY == 0:
                blips = detect_blips(frame)
                ocr_results = [ocr_blip(frame, b[0], b[1]) for b in blips]
                tm.update(frame_idx, blips, ocr_results)
                table_img = build_table(tm, frame_idx)
                mins = int(t_real // 60); secs = int(t_real % 60)
                print(f"\r  {mins:02d}:{secs:02d}  frame={frame_idx}  tracks={len(tm.tracks)}", end="", flush=True)

                # Ghi live JSON
                _live_tracks = {}
                for _tid, _info in tm.tracks.items():
                    if frame_idx - _info["last_frame"] > OCR_EVERY * 3: continue
                    if not _info["history"]: continue
                    _, _xkm, _ykm, _px, _py = _info["history"][-1]
                    _vx, _vy = tm.get_velocity(_tid)
                    _speed = round(float(np.sqrt(_vx**2 + _vy**2)) * 3600, 0) if _vx is not None else None
                    _live_tracks[_tid] = {
                        "color":     _info["color"],
                        "dist_km":   round(float(np.sqrt(_xkm**2 + _ykm**2)), 1),
                        "bearing":   round(float(np.degrees(np.arctan2(_xkm, _ykm)) % 360), 1),
                        "speed_kmh": _speed,
                        "pos_px":    [_px, _py],
                        "named":     not _tid.startswith("?"),
                    }
                _live_payload = {
                    "frame":   frame_idx,
                    "t_sec":   round(t_real, 2),
                    "tracks":  _live_tracks,
                }
                _live_path = r"c:\Users\ygost\radar\live_tracks.json"
                _live_tmp  = _live_path + ".tmp"
                with open(_live_tmp, "w", encoding="utf-8") as _f:
                    json.dump(_live_payload, _f, ensure_ascii=False, separators=(",", ":"))
                os.replace(_live_tmp, _live_path)
                write_live_html(tm, frame_idx, FPS, t_real)

            # Ve va hien thi
            canvas  = frame.copy()
            hovered = draw_frame(canvas, frame_idx, tm, FPS, t_real, mouse_x, mouse_y)
            if writer:
                writer.write(canvas)

            if hovered != _tts_last_tid:
                _tts_last_tid = hovered
                if hovered and hovered in tm.tracks:
                    speak_target(hovered, tm.tracks[hovered], tm)

            cv2.imshow("Radar Tracker", canvas)

            _max_scroll = max(0, table_img.shape[0] - TABLE_WIN_H)
            table_scroll_y = min(table_scroll_y, _max_scroll)
            _view = table_img[table_scroll_y : table_scroll_y + TABLE_WIN_H]
            if _view.shape[0] < TABLE_WIN_H:
                _pad = np.zeros((TABLE_WIN_H - _view.shape[0], TABLE_W, 3), dtype=np.uint8)
                _view = np.vstack([_view, _pad])
            cv2.imshow("Bang thong tin", _view)

            # Tinh thoi gian con lai de giu dung FPS
            elapsed = time.perf_counter() - t0
            wait_ms = max(1, int((_frame_dur - elapsed) * 1000))
            key = cv2.waitKey(wait_ms) & 0xFF
            if key == ord('q') or key == 27:
                break

            frame_idx += 1
finally:
    print()
    if writer:
        writer.release()
    cv2.destroyAllWindows()

# Luu JSON tracks
out_tracks = {}
for tid, info in tm.tracks.items():
    out_tracks[tid] = {
        "color": info["color"],
        "history": [
            {"t": h[0], "dx_km": round(h[1],1), "dy_km": round(h[2],1),
             "dist_km": round(float(np.sqrt(h[1]**2+h[2]**2)),1),
             "bearing":  round(float(np.degrees(np.arctan2(h[1],h[2]))%360),1)}
            for h in info["history"]
        ]
    }
with open(r"c:\Users\ygost\radar\tracks.json","w",encoding="utf-8") as f:
    json.dump(out_tracks, f, indent=2, ensure_ascii=False)

print(f"\nDone! Frames: {frame_idx}")
print(f"Tracks: {len(tm.tracks)} total")
named_tracks = {k:v for k,v in tm.tracks.items() if not k.startswith("?")}
print(f"Named : {len(named_tracks)} -> {sorted(named_tracks.keys())}")
