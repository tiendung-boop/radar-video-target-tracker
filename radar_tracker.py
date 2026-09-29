"""
Radar Tracking Pipeline
- Phat hien blip + OCR so hieu moi 10 frame
- Bam sat track qua cac frame (theo ID hoac vi tri gan nhat)
- Du doan quy dao 30 giay tiep theo
- Hien thi truc tiep; hover chuot de xem thong tin blip
- Xuat video co chu thich (output_tracking.mp4)
"""
import cv2
import numpy as np
import json
from ultralytics import YOLO
from collections import defaultdict
import pygame
import threading
import queue
import os
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import tkinter as tk
from tkinter import simpledialog

try:
    _PIL_FONT    = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf",   18)
    _PIL_FONT_BD = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 18)
except Exception:
    _PIL_FONT = _PIL_FONT_BD = ImageFont.load_default()

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
VIDEO_PATH  = r"c:\Users\ygost\radar\thucte.mp4"
MODEL_PATH  = r"c:\Users\ygost\radar\runs\ocr\weights\best.pt"
OUTPUT_PATH = r"c:\Users\ygost\radar\output_tracking.mp4"

# Radar calibration: vong 6 tu trong ra = 300km, 50km moi vong
CX, CY   = 772, 522
R_300KM  = 438          # ban kinh pixel cua vong 300km (vong thu 6)
KM_PX    = 300.0 / R_300KM   # ~0.6849 km/px

# Pipeline params
OCR_EVERY   = 10        # chay OCR moi N frame (~ 3fps)
CONF_THRESH = 0.45
PAD         = 35        # crop half-size cho OCR
ZOOM_SIZE   = 280

# Track params
MAX_LOST    = 60        # frame khong thay -> xoa track
ASSOC_DIST  = 30        # pixel: gan nhat de ghep track khi OCR fail
TAIL_LEN    = 25        # so vi tri lich su ve len anh
PRED_SEC    = 30        # du doan truoc bao nhieu giay

# Hover tooltip
HOVER_RADIUS = 22       # pixel: khoang cach chuot de hien tooltip

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
click_event = None       # (x, y) khi user click trai vao blip

# Auto-speak state
_auto_speak_stop   = threading.Event()
_auto_speak_thread = None

# Table layout — chieu rong co dinh, cuon chuot de xem them hang
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
    global mouse_x, mouse_y, click_event
    mouse_x, mouse_y = x, y
    if event == cv2.EVENT_LBUTTONDOWN:
        click_event = (x, y)

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
    color_label  = np.zeros((h, w), dtype=np.uint8)   # 0=none, 1..N = index into _color_order
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
    return merged   # [(bx,by,area,dist,bear,color,dx,dy), ...]

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
        digit = str((int(box.cls[0]) + 1) % 10)   # offset fix
        dets.append((xc, yc, digit, float(box.conf[0])))
    if not dets: return ""

    # Nhom theo dong Y
    dets.sort(key=lambda d: d[1])
    lines, cur = [], [dets[0]]
    for d in dets[1:]:
        if abs(d[1]-cur[-1][1]) < 22: cur.append(d)
        else: lines.append(cur); cur = [d]
    lines.append(cur)

    # Chon dong gan tam nhat, 2-6 chu so
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
        self._unnamed = 0   # counter cho blip chua co ID

    def _new_anon(self):
        self._unnamed += 1
        return f"?{self._unnamed}"

    def update(self, frame_idx, blips, ocr_results):
        """
        blips: [(bx,by,area,dist,bear,color,dx,dy)]
        ocr_results: [track_id_str or ""] same length as blips
        """
        t_sec = frame_idx / self.fps

        # Tap hop track dang hoat dong (chua mat)
        active = {tid: info for tid, info in self.tracks.items()
                  if frame_idx - info["last_frame"] <= MAX_LOST}
        self.tracks = active

        # Tap hop vi tri blip da duoc xu ly
        matched_track_ids = set()

        for (bx,by,area,dist,bear,color,dx,dy), tid_ocr in zip(blips, ocr_results):
            tid = tid_ocr.strip() if tid_ocr.strip() else None

            # Neu khong co OCR, tim track gan nhat theo vi tri
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

            # Tao track moi neu chua co
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
        """Tinh van toc (km/s) tu lich su gan nhat"""
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
        return vx, vy   # km/s

    def predict_pos(self, tid, t_ahead_sec):
        """Tra ve (xkm_pred, ykm_pred, xpx_pred, ypx_pred) sau t_ahead_sec"""
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
# TOOLTIP — chi thay doi noi dung khi chu ky OCR moi den
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
        (f"Cự ly:  {int(dist):03d}",       (220, 220, 220), _PIL_FONT),
        (f"Phương vị:  {int(bear):03d}",   (220, 220, 220), _PIL_FONT),
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

    # Nen + vien (van dung cv2 vi nhanh)
    cv2.rectangle(canvas, (bx - 2, by - 2), (bx + W_BOX + 2, by + H_BOX + 2), color, 2)
    cv2.rectangle(canvas, (bx, by), (bx + W_BOX, by + H_BOX), (10, 10, 10), -1)

    # Ve chu co dau bang PIL (convert 1 lan cho ca tooltip)
    pil_img = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    draw    = ImageDraw.Draw(pil_img)
    for i, (text, tcol, fnt) in enumerate(lines):
        tx = bx + PAD_T
        ty = by + PAD_T + i * LINE_H
        draw.text((tx, ty), text, font=fnt, fill=(tcol[2], tcol[1], tcol[0]))
    np.copyto(canvas, cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR))

# ══════════════════════════════════════════════════════════════════════════════
# AUDIO — doc thong tin muc tieu khi hover bang file am thanh trong /speak
# Thu tu doc: "muc_tieu" [digits ID] "khong" [digits phuong_vi] "0" [digits cu_ly]
# ══════════════════════════════════════════════════════════════════════════════

def _play_clip(name: str) -> bool:
    """Phat mot file speak/<name>.wav. Tra ve False neu bi huy hoac loi."""
    path = os.path.join(SPEAK_DIR, f"{name}.wav")
    if not os.path.exists(path):
        return True   # bo qua file khong co, tiep tuc clip ke tiep
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


def speak_target(tid, info, tm):
    hist = info["history"]
    if not hist:
        return

    _, xkm, ykm, _, _ = hist[-1]
    dist = int(np.sqrt(xkm**2 + ykm**2) + 0.5)
    bear = int(np.degrees(np.arctan2(xkm, ykm)) % 360 + 0.5)

    now = datetime.now()
    clips = []

    if tid.isdigit():
        clips.extend(list(tid))   # giu nguyen so 0 dau (vi du "042" -> ['0','4','2'])

    clips.append("khong")
    clips.extend(list(f"{bear:03d}"))   # phuong_vi 3 chu so, co 0 dau neu can
    clips.extend(list(f"{dist:03d}"))   # cu_ly 3 chu so, co 0 dau neu can
    clips.extend(list(now.strftime("%H%M")))  # gio phut thuc, moi don vi 2 chu so

    # Huy clip dang phat, xoa queue, day request moi
    _audio_cancel.set()
    while not _audio_queue.empty():
        try: _audio_queue.get_nowait()
        except queue.Empty: break
    _audio_queue.put(clips)

# ══════════════════════════════════════════════════════════════════════════════
# AUTO-SPEAK — click vao blip, nhap chu ky (giay), tu dong doc dinh ky
# ══════════════════════════════════════════════════════════════════════════════

def _auto_speak_worker(tid, interval, stop_evt, tm_ref):
    stop_evt.wait(0.2)
    while not stop_evt.is_set():
        if tid in tm_ref.tracks:
            speak_target(tid, tm_ref.tracks[tid], tm_ref)
        stop_evt.wait(interval)

def start_auto_speak(tid, interval, tm):
    global _auto_speak_stop, _auto_speak_thread
    _auto_speak_stop.set()
    if _auto_speak_thread and _auto_speak_thread.is_alive():
        _auto_speak_thread.join(timeout=1.5)
    _auto_speak_stop = threading.Event()
    _auto_speak_thread = threading.Thread(
        target=_auto_speak_worker, args=(tid, interval, _auto_speak_stop, tm), daemon=True
    )
    _auto_speak_thread.start()
    print(f"[AUTO-SPEAK] Doc muc tieu {tid} moi {interval}s", flush=True)

def show_interval_dialog(tid, tm):
    def _run():
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        val = simpledialog.askstring(
            "Tu dong doc muc tieu",
            f"Muc tieu: {tid}\nNhap chu ky doc tu dong (giay):",
            parent=root
        )
        root.destroy()
        if val is None:
            return
        try:
            secs = float(val)
            if secs > 0:
                start_auto_speak(tid, secs, tm)
        except ValueError:
            pass
    threading.Thread(target=_run, daemon=True).start()

# ══════════════════════════════════════════════════════════════════════════════
# DRAW FRAME
# ══════════════════════════════════════════════════════════════════════════════
def draw_frame(canvas, frame_idx, tm, fps, mx=0, my=0):
    t_sec = frame_idx / fps

    hovered_tid = None  # track blip gan chuot nhat

    for tid, info in tm.tracks.items():
        if frame_idx - info["last_frame"] > OCR_EVERY * 3:
            continue

        hist  = info["history"]
        color = COLOR_MAP.get(info["color"], UNKNOWN_COL)
        if not hist: continue

        t_last, xkm, ykm, px_last, py_last = hist[-1]

        # --- DUOI LICH SU ---
        tail_pts = hist[-TAIL_LEN:]
        for k in range(1, len(tail_pts)):
            alpha = k / len(tail_pts)
            c = tuple(int(v * alpha * 0.7) for v in color)
            p1 = (tail_pts[k-1][3], tail_pts[k-1][4])
            p2 = (tail_pts[k][3],   tail_pts[k][4])
            cv2.line(canvas, p1, p2, c, 1)

        # --- DU DOAN ---
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

        # --- ICON BLIP (chi vien, khong to dac, de nhin xuyen qua nen goc) ---
        cv2.circle(canvas, (px_last, py_last), 9, color, 2)
        cv2.line(canvas, (px_last - 5, py_last), (px_last + 5, py_last), color, 1)
        cv2.line(canvas, (px_last, py_last - 5), (px_last, py_last + 5), color, 1)

        # Kiem tra hover: chon blip gan chuot nhat trong pham vi
        if (mx - px_last)**2 + (my - py_last)**2 <= HOVER_RADIUS**2:
            hovered_tid = tid

    # Ve tooltip SAU khi ve xong tat ca blip (de hien tren cung)
    if hovered_tid and hovered_tid in tm.tracks:
        draw_tooltip(canvas, hovered_tid, tm.tracks[hovered_tid], tm, mx, my)

    # --- THANH THONG TIN PHIA TREN ---
    n_active = sum(1 for tid, info in tm.tracks.items()
                   if frame_idx - info["last_frame"] <= OCR_EVERY * 3
                   and not tid.startswith("?"))
    now = datetime.now()
    clock_str = now.strftime("%H:%M")
    bar = f"  t = {t_sec:.1f}s   |   {n_active} muc tieu nhan dien   |   Radar 300km   |   {clock_str}   |   [Q/Esc] thoat"
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 22), (0, 0, 0), -1)
    cv2.putText(canvas, bar, (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 220), 1)

    return hovered_tid

# ══════════════════════════════════════════════════════════════════════════════
# TABLE — cap nhat theo chu ky OCR, khong thay doi giua cac frame
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

    # Tieu de
    cv2.rectangle(img, (0, 0), (TABLE_W, TABLE_TITLE_H), (0, 55, 55), -1)
    cv2.putText(img, "DANH SACH MUC TIEU", (10, TABLE_TITLE_H - 9),
                cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 230, 230), 2, cv2.LINE_AA)
    n_named = sum(1 for t, _ in active if not t.startswith("?"))
    cv2.putText(img, f"{n_named}/{len(active)}",
                (TABLE_W - 60, TABLE_TITLE_H - 9),
                cv2.FONT_HERSHEY_SIMPLEX, 0.46, (150, 200, 150), 1, cv2.LINE_AA)

    # Header
    hy = TABLE_TITLE_H
    cv2.rectangle(img, (0, hy), (TABLE_W, hy + TABLE_HDR_H), (38, 38, 38), -1)
    for j, name in enumerate(_COL_HDR):
        cv2.putText(img, name, (_COL_DIV[j] + 5, hy + TABLE_HDR_H - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, (0, 210, 210), 1, cv2.LINE_AA)
    cv2.line(img, (0, hy + TABLE_HDR_H), (TABLE_W, hy + TABLE_HDR_H), (90, 90, 90), 1)

    # Cac hang du lieu
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

    # Duong ke doc cac cot
    for x in _COL_DIV[1:-1]:
        cv2.line(img, (x, TABLE_TITLE_H), (x, H - 1), (60, 60, 60), 1)

    # Khung ngoai
    cv2.rectangle(img, (0, 0), (TABLE_W - 1, H - 1), (80, 80, 80), 1)
    return img

# ══════════════════════════════════════════════════════════════════════════════
# LIVE HTML — ghi moi chu ky OCR, browser tu refresh moi 2 giay
# ══════════════════════════════════════════════════════════════════════════════
_HTML_PATH = r"c:\Users\ygost\radar\live_tracks.html"
_LOAI_VN   = {"RED":"Quân sự","GREEN":"Quá cảnh","YELLOW":"Không xác định",
               "CYAN":"Địch","MAGENTA":"Quốc tế"}
_CSS_COLOR = {"RED":"#ff4444","GREEN":"#44dd44","YELLOW":"#dddd00",
              "CYAN":"#00dddd","MAGENTA":"#dd44dd"}

def write_live_html(tm, frame_idx, fps, total):
    active = [(tid, info) for tid, info in tm.tracks.items()
              if frame_idx - info["last_frame"] <= OCR_EVERY * 3]
    active.sort(key=lambda x: (x[0].startswith("?"), x[0]))

    t_sec   = frame_idx / fps
    pct     = frame_idx / total * 100 if total > 0 else 0
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
  .badge {{ display:inline-block; padding:1px 6px; border-radius:3px; background:#0d2020; font-size:11px; }}
</style>
</head>
<body>
<h2>&#9632; RADAR LIVE — DANH SÁCH MỤC TIÊU</h2>
<div class="info">
  t = {t_sec:.1f}s &nbsp;|&nbsp; frame {frame_idx} &nbsp;|&nbsp;
  tiến độ {pct:.1f}% &nbsp;|&nbsp;
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

cap   = cv2.VideoCapture(VIDEO_PATH)
FPS   = cap.get(cv2.CAP_PROP_FPS)
TOTAL = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
W     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
H     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"Video: {W}x{H}, {FPS:.1f}fps, {TOTAL} frames ({TOTAL/FPS:.0f}s)")
print("Hover chuot len blip de xem thong tin. Nhan Q hoac Esc de thoat.")

writer = cv2.VideoWriter(OUTPUT_PATH, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
if not writer.isOpened():
    writer = cv2.VideoWriter(OUTPUT_PATH.replace(".mp4", ".avi"),
                             cv2.VideoWriter_fourcc(*"MJPG"), FPS, (W, H))
    print("mp4v codec not available, falling back to MJPG (.avi)")

tm = TrackManager(FPS)
table_img = build_table(tm, 0)

cv2.namedWindow("Radar Tracker", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Radar Tracker", W, H)
cv2.setMouseCallback("Radar Tracker", on_mouse)

cv2.namedWindow("Bang thong tin", cv2.WINDOW_AUTOSIZE)
cv2.setMouseCallback("Bang thong tin", on_table_scroll)

cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
frame_idx = 0
try:
    while True:
        ret, frame = cap.read()
        if not ret: break

        # Phat hien + OCR moi OCR_EVERY frame
        if frame_idx % OCR_EVERY == 0:
            blips = detect_blips(frame)
            ocr_results = [ocr_blip(frame, b[0], b[1]) for b in blips]
            tm.update(frame_idx, blips, ocr_results)
            table_img = build_table(tm, frame_idx)
            pct = frame_idx / TOTAL * 100 if TOTAL > 0 else 0
            print(f"\r  {pct:5.1f}%  [{frame_idx}/{TOTAL}]  tracks={len(tm.tracks)}", end="", flush=True)

            # Ghi live JSON moi chu ky OCR de code khac co the doc real-time
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
                "frame":    frame_idx,
                "t_sec":    round(frame_idx / FPS, 2),
                "progress": round(pct, 1),
                "tracks":   _live_tracks,
            }
            _live_path = r"c:\Users\ygost\radar\live_tracks.json"
            _live_tmp  = _live_path + ".tmp"
            with open(_live_tmp, "w", encoding="utf-8") as _f:
                json.dump(_live_payload, _f, ensure_ascii=False, separators=(",", ":"))
            os.replace(_live_tmp, _live_path)   # atomic write — tranh doc file dang ghi do
            write_live_html(tm, frame_idx, FPS, TOTAL)

        # Ve len frame voi vi tri chuot hien tai
        canvas = frame.copy()
        hovered = draw_frame(canvas, frame_idx, tm, FPS, mouse_x, mouse_y)
        writer.write(canvas)

        # Xu ly click: tim blip gan vi tri click, hien dialog nhap chu ky
        if click_event:
            clk_x, clk_y = click_event
            click_event = None
            for _ctid, _cinfo in tm.tracks.items():
                if frame_idx - _cinfo["last_frame"] > OCR_EVERY * 3: continue
                if not _cinfo["history"]: continue
                _, _, _, _cpx, _cpy = _cinfo["history"][-1]
                if (clk_x - _cpx)**2 + (clk_y - _cpy)**2 <= HOVER_RADIUS**2:
                    show_interval_dialog(_ctid, tm)
                    break

        # TTS: chi doc khi hover sang muc tieu moi
        if hovered != _tts_last_tid:
            _tts_last_tid = hovered
            if hovered and hovered in tm.tracks:
                speak_target(hovered, tm.tracks[hovered], tm)

        cv2.imshow("Radar Tracker", canvas)

        # Hien thi bang voi scroll: cat slice TABLE_WIN_H px tu vi tri cuon
        _max_scroll = max(0, table_img.shape[0] - TABLE_WIN_H)
        table_scroll_y = min(table_scroll_y, _max_scroll)
        _view = table_img[table_scroll_y : table_scroll_y + TABLE_WIN_H]
        if _view.shape[0] < TABLE_WIN_H:
            _pad = np.zeros((TABLE_WIN_H - _view.shape[0], TABLE_W, 3), dtype=np.uint8)
            _view = np.vstack([_view, _pad])
        cv2.imshow("Bang thong tin", _view)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:   # Q hoac Esc
            break

        frame_idx += 1
finally:
    print()
    cap.release()
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

print(f"\nDone! Output: {OUTPUT_PATH}")
print(f"Tracks: {len(tm.tracks)} total")
named_tracks = {k:v for k,v in tm.tracks.items() if not k.startswith("?")}
print(f"Named : {len(named_tracks)} -> {sorted(named_tracks.keys())}")
