"""
Radar Live Capture — Screen capture + thao tác thủ công
- Chụp màn hình từ cửa sổ bất kỳ (mss + win32gui)
- Detect blip theo màu, tracking theo vị trí gần nhất
- Chuột TRÁI lên blip  → phát thông tin mục tiêu ngay (TTS)
- Chuột PHẢI lên blip  → dialog: nhập ID + chu kỳ auto-speak
- Xuất live_tracks.json + live_tracks.html liên tục
"""
import ctypes
import cv2
import numpy as np
import json
import threading
import queue
import os
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import mss
import win32gui
from pynput import mouse as pmouse
from ultralytics import YOLO
import pygame
import tkinter as tk
import tkinter.messagebox

try:
    _PIL_FONT    = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf",   18)
    _PIL_FONT_BD = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 18)
except Exception:
    _PIL_FONT = _PIL_FONT_BD = ImageFont.load_default()

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
# Radar calibration — không thay đổi
CX, CY   = 518, 486
R_300KM  = 292
KM_PX    = 300.0 / R_300KM

# Pipeline
DETECT_EVERY = 5          # detect blip mỗi N frame
MAX_LOST     = 60
ASSOC_DIST   = 30
TAIL_LEN     = 25
PRED_SEC     = 30
HOVER_RADIUS  = 22
TARGET_FPS    = 15
GLOBAL_RADIUS = 150      # km — bán kính cho "Phát tự động"
_BTN_AUTO_W   = 158
_BTN_AUTO_H   = 22

# Audio
SPEAK_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speak")
_audio_queue  = queue.Queue()
_audio_cancel = threading.Event()

# ──────────────────────────────────────────────────────────────────────────────
# BEARING: Bắc = 0°, chiều kim đồng hồ = dương, 0 – 360°
# east_km  : thành phần hướng Đông  (dx = (bx - CX) * KM_PX)
# north_km : thành phần hướng Bắc   (dy = (CY - by) * KM_PX)
# ──────────────────────────────────────────────────────────────────────────────
def compass_bearing(east_km, north_km):
    return float(np.degrees(np.arctan2(east_km, north_km)) % 360)

# Màu (BGR)
COLOR_MAP = {
    "RED":     (60,  60,  255),
    "GREEN":   (60,  220,  60),
    "YELLOW":  (0,   220, 220),
    "CYAN":    (220, 200,  30),
    "MAGENTA": (220,  60, 220),
}
UNKNOWN_COL = (160, 160, 160)

# Table
TABLE_W       = 510
TABLE_WIN_H   = 300
TABLE_TITLE_H = 36
TABLE_HDR_H   = 30
TABLE_ROW_H   = 28
_COL_DIV = [0, 42, 130, 198, 288, 378, TABLE_W]
_COL_HDR = ["STT", "Mau", "ID", "Cu ly(km)", "GPV(deg)", "Toc(km/h)"]

# ══════════════════════════════════════════════════════════════════════════════
# WINDOW UTILITIES
# ══════════════════════════════════════════════════════════════════════════════
def list_visible_windows():
    result = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            if t and len(t) > 1:
                result.append((hwnd, t))
    win32gui.EnumWindows(_cb, None)
    return result

def choose_window():
    wins = list_visible_windows()
    print("\n=== DANH SÁCH CỬA SỔ ===")
    for i, (hwnd, title) in enumerate(wins):
        print(f"  {i:3d}.  {title[:90]}")
    while True:
        try:
            idx = int(input(f"\nChọn số thứ tự cửa sổ (0-{len(wins)-1}): "))
            if 0 <= idx < len(wins):
                return wins[idx]
        except (ValueError, KeyboardInterrupt):
            pass
        print("Nhập lại...")

def get_client_screen_rect(hwnd):
    cr = win32gui.GetClientRect(hwnd)
    tl = win32gui.ClientToScreen(hwnd, (cr[0], cr[1]))
    br = win32gui.ClientToScreen(hwnd, (cr[2], cr[3]))
    return tl[0], tl[1], br[0], br[1]

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL MOUSE HOOKS (pynput) — chỉ cần chuột, không cần bàn phím
# ══════════════════════════════════════════════════════════════════════════════
_left_click_q  = queue.Queue()   # (screen_x, screen_y)
_right_click_q = queue.Queue()

def _on_mouse_click(x, y, button, pressed):
    if not pressed:
        return
    if button == pmouse.Button.left:
        _left_click_q.put((x, y))
    elif button == pmouse.Button.right:
        _right_click_q.put((x, y))

# ══════════════════════════════════════════════════════════════════════════════
# AUDIO
# ══════════════════════════════════════════════════════════════════════════════
def _play_clip(name):
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
        print(f"[AUDIO] {e}")
    return not _audio_cancel.is_set()

def _audio_worker():
    while True:
        clips = _audio_queue.get()
        if clips is None:
            break
        _audio_cancel.clear()
        for clip in clips:
            if not _play_clip(clip):
                break

def speak_target(tid, info, prefix=None, interrupt=True):
    hist = info["history"]
    if not hist:
        return
    _, xkm, ykm, _, _ = hist[-1]
    dist = int(np.sqrt(xkm**2 + ykm**2) + 0.5)
    bear = int(compass_bearing(xkm, ykm) + 0.5)
    now  = datetime.now()
    clips = []
    if not info.get("spoken_once"):
        clips.extend(["xuat_hien", "xuat_hien"])
        info["spoken_once"] = True
    elif prefix:
        clips.extend(prefix)
    if tid.isdigit():
        clips.extend(list(tid))
    clips.append("khong")
    clips.extend(list(f"{bear:03d}"))
    clips.extend(list(f"{dist:03d}"))
    clips.extend(list(now.strftime("%H%M")))
    if interrupt:
        # Click chuột trái: chỉ ngắt nếu đang có âm thanh phát
        if pygame.mixer.music.get_busy():
            _audio_cancel.set()
        while not _audio_queue.empty():
            try:
                _audio_queue.get_nowait()
            except queue.Empty:
                break
    _audio_queue.put(clips)

# ══════════════════════════════════════════════════════════════════════════════
# AUTO-SPEAK  (nhiều mục tiêu đồng thời, mỗi tid một thread riêng)
# ══════════════════════════════════════════════════════════════════════════════
_auto_speak_threads = {}            # tid -> (stop_evt, thread)
_audio_auto_lock    = threading.Lock()  # chỉ một worker phát tại một thời điểm

def _auto_speak_worker(tid, interval, stop_evt, tm_ref):
    stop_evt.wait(0.2)
    while not stop_evt.is_set():
        if tid in tm_ref.tracks:
            # Chờ lấy slot phát — kiểm tra stop_evt mỗi 0.5s để không block mãi
            acquired = False
            while not stop_evt.is_set():
                acquired = _audio_auto_lock.acquire(timeout=0.5)
                if acquired:
                    break
            if not acquired:
                break
            try:
                # 1. Đợi audio đang phát kết thúc — không ngắt
                while pygame.mixer.music.get_busy() and not stop_evt.is_set():
                    time.sleep(0.1)
                if not stop_evt.is_set():
                    info = tm_ref.tracks.get(tid)
                    if info:
                        # 2. Phát thông tin máy bay
                        prefix = None
                        if info.get("was_lost"):
                            prefix = ["xuat_hien_lai"]
                            info["was_lost"] = False
                        speak_target(tid, info, prefix=prefix, interrupt=False)
                        # 3. Đợi audio worker kịp bắt đầu, rồi chờ phát xong hết
                        time.sleep(0.4)
                        while pygame.mixer.music.get_busy() and not stop_evt.is_set():
                            time.sleep(0.1)
            finally:
                _audio_auto_lock.release()
        # 4. Bắt đầu đếm interval SAU KHI audio đã xong hẳn
        stop_evt.wait(interval)

def start_auto_speak(tid, interval, tm):
    # Dừng thread cũ cho chính tid này nếu đang chạy
    if tid in _auto_speak_threads:
        old_evt, old_thr = _auto_speak_threads.pop(tid)
        old_evt.set()
        old_thr.join(timeout=1.5)
    stop_evt = threading.Event()
    thr = threading.Thread(
        target=_auto_speak_worker,
        args=(tid, interval, stop_evt, tm),
        daemon=True
    )
    _auto_speak_threads[tid] = (stop_evt, thr)
    thr.start()
    print(f"[AUTO-SPEAK] {tid} mỗi {interval}s  (tong: {len(_auto_speak_threads)} muc tieu)", flush=True)

def stop_auto_speak(tid=None):
    if tid is not None:
        if tid in _auto_speak_threads:
            evt, _ = _auto_speak_threads.pop(tid)
            evt.set()
            print(f"[AUTO-SPEAK] Dung {tid}", flush=True)
    else:
        for evt, _ in _auto_speak_threads.values():
            evt.set()
        _auto_speak_threads.clear()

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL AUTO-SPEAK — button "Phat tu dong", tat ca muc tieu <= 150 km
# ══════════════════════════════════════════════════════════════════════════════
_global_auto_active = False
_global_auto_stop   = threading.Event()
_global_auto_thread = None

def _global_auto_worker(stop_evt, tm_ref):
    while not stop_evt.is_set():
        candidates = []
        for tid, info in list(tm_ref.tracks.items()):
            hist = info.get("history")
            if not hist:
                continue
            _, xkm, ykm, _, _ = hist[-1]
            dist = float(np.sqrt(xkm**2 + ykm**2))
            if dist > GLOBAL_RADIUS:
                continue
            candidates.append((
                tid, info, dist,
                not info.get("spoken_once", False),  # is_new
                bool(info.get("was_lost", False)),   # is_relost
            ))

        # Thu tu uu tien: muc tieu moi -> xuat hien lai -> gan den xa
        candidates.sort(key=lambda c: (0 if c[3] else (1 if c[4] else 2), c[2]))

        if not candidates:
            stop_evt.wait(1.0)
            continue

        for tid, _info, _dist, _is_new, _is_relost in candidates:
            if stop_evt.is_set():
                break
            acquired = False
            while not stop_evt.is_set():
                acquired = _audio_auto_lock.acquire(timeout=0.5)
                if acquired:
                    break
            if not acquired:
                break
            try:
                while pygame.mixer.music.get_busy() and not stop_evt.is_set():
                    time.sleep(0.1)
                if not stop_evt.is_set():
                    info = tm_ref.tracks.get(tid)
                    if info:
                        prefix = None
                        if info.get("was_lost"):
                            prefix = ["xuat_hien_lai"]
                            info["was_lost"] = False
                        speak_target(tid, info, prefix=prefix, interrupt=False)
                        time.sleep(0.4)
                        while pygame.mixer.music.get_busy() and not stop_evt.is_set():
                            time.sleep(0.1)
            finally:
                _audio_auto_lock.release()

def toggle_global_auto(tm):
    global _global_auto_active, _global_auto_stop, _global_auto_thread
    if _global_auto_active:
        _global_auto_stop.set()
        _global_auto_active = False
        print("[GLOBAL-AUTO] Dung", flush=True)
    else:
        _global_auto_stop = threading.Event()
        _global_auto_thread = threading.Thread(
            target=_global_auto_worker,
            args=(_global_auto_stop, tm),
            daemon=True
        )
        _global_auto_thread.start()
        _global_auto_active = True
        print("[GLOBAL-AUTO] Bat dau — tat ca muc tieu <= 150km", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# DIALOG CHUỘT PHẢI: nhập ID + chu kỳ auto-speak
# ══════════════════════════════════════════════════════════════════════════════
def show_target_dialog(tid, tm):
    def _run():
        root = tk.Tk()
        root.title(f"Mục tiêu  [ {tid} ]")
        root.resizable(False, False)
        root.attributes("-topmost", True)
        root.configure(bg="#111")

        style_lbl = {"bg": "#111", "fg": "#00dddd", "font": ("Consolas", 11)}
        style_ent = {"bg": "#1a1a1a", "fg": "#ffffff", "insertbackground": "#00dddd",
                     "font": ("Consolas", 11), "relief": "flat", "bd": 2}

        tk.Label(root, text="ID mục tiêu:", **style_lbl).grid(
            row=0, column=0, padx=14, pady=(14, 4), sticky="w")
        id_var   = tk.StringVar()
        id_entry = tk.Entry(root, textvariable=id_var, width=16, **style_ent)
        id_entry.grid(row=0, column=1, padx=14, pady=(14, 4))
        id_entry.focus()

        tk.Label(root, text="Chu kỳ phát (giây):", **style_lbl).grid(
            row=1, column=0, padx=14, pady=4, sticky="w")
        int_var   = tk.StringVar()
        int_entry = tk.Entry(root, textvariable=int_var, width=16, **style_ent)
        int_entry.grid(row=1, column=1, padx=14, pady=4)

        def on_ok(_event=None):
            new_id  = id_var.get().strip()
            int_str = int_var.get().strip()
            active_tid = tid
            if new_id:
                tm.rename(tid, new_id)
                active_tid = new_id
            if int_str:
                try:
                    secs = float(int_str)
                    if secs > 0:
                        start_auto_speak(active_tid, secs, tm)
                except ValueError:
                    pass
            root.destroy()

        btn_frame = tk.Frame(root, bg="#111")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(8, 14))
        tk.Button(btn_frame, text="OK",   width=10, bg="#005555", fg="#ffffff",
                  font=("Consolas", 10), relief="flat", command=on_ok).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Dừng phát", width=10, bg="#553300", fg="#ffffff",
                  font=("Consolas", 10), relief="flat",
                  command=lambda: (stop_auto_speak(tid), root.destroy())).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Huỷ",  width=10, bg="#333", fg="#aaaaaa",
                  font=("Consolas", 10), relief="flat", command=root.destroy).pack(side="left", padx=6)

        root.bind("<Return>", on_ok)
        root.bind("<Escape>", lambda e: root.destroy())
        root.mainloop()

    threading.Thread(target=_run, daemon=True).start()

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
    for ci, (_, m) in enumerate(color_masks.items(), 1):
        m = cv2.bitwise_and(m, mask_radar)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        color_label[m > 0] = ci
        combined = cv2.bitwise_or(combined, m)

    _, lbl, stats, centroids = cv2.connectedComponentsWithStats(combined, 8)
    raw = []
    for i in range(1, int(stats.shape[0])):
        x0, y0, bw, bh, area = stats[i]
        if area < 5 or area > 1200:
            continue
        if max(bw, bh) / max(min(bw, bh), 1) > 8:
            continue
        bx = int(centroids[i][0]); by = int(centroids[i][1])
        dx = (bx - CX) * KM_PX;   dy = (CY - by) * KM_PX
        dist = float(np.sqrt(dx**2 + dy**2))
        if dist > 305:
            continue
        valid_px = color_label[lbl == i]
        valid_px = valid_px[valid_px > 0]
        dom = _color_order[int(np.bincount(valid_px).argmax()) - 1] if valid_px.size > 0 else "?"
        bearing = compass_bearing(dx, dy)
        raw.append((bx, by, int(area), dist, bearing, dom, dx, dy))

    raw.sort(key=lambda x: x[3])
    merged, used = [], set()
    for i, b in enumerate(raw):
        if i in used:
            continue
        grp = [b]
        for j, b2 in enumerate(raw):
            if j <= i or j in used:
                continue
            if abs(b[0]-b2[0]) < 20 and abs(b[1]-b2[1]) < 20:
                grp.append(b2); used.add(j)
        merged.append(max(grp, key=lambda x: x[2])); used.add(i)
    return merged

# ══════════════════════════════════════════════════════════════════════════════
# TRACK MANAGER
# ══════════════════════════════════════════════════════════════════════════════
class TrackManager:
    def __init__(self, fps):
        self.fps     = fps
        self.tracks  = {}
        self._unnamed = 0

    def _new_anon(self):
        self._unnamed += 1
        return f"?{self._unnamed}"

    def rename(self, old_tid, new_id):
        if old_tid not in self.tracks:
            return
        if new_id in self.tracks:
            self.tracks[new_id]["history"].extend(self.tracks[old_tid]["history"])
            self.tracks[new_id]["history"].sort(key=lambda h: h[0])
            del self.tracks[old_tid]
        else:
            self.tracks[new_id] = self.tracks.pop(old_tid)
        print(f"[TRACK] {old_tid} → {new_id}", flush=True)

    def update(self, frame_idx, blips):
        t_sec  = frame_idx / self.fps
        active = {tid: info for tid, info in self.tracks.items()
                  if frame_idx - info["last_frame"] <= MAX_LOST}
        self.tracks = active
        matched = set()

        for (bx, by, area, dist, bear, color, dx, dy) in blips:
            # Proximity matching với track đang hoạt động
            best_match = None; best_d = ASSOC_DIST
            for etid, einfo in active.items():
                if etid in matched or not einfo["history"]:
                    continue
                ex, ey = einfo["history"][-1][3], einfo["history"][-1][4]
                d = np.sqrt((bx-ex)**2 + (by-ey)**2)
                if d < best_d:
                    best_d = d; best_match = etid
            tid = best_match if best_match else self._new_anon()

            if tid not in self.tracks:
                self.tracks[tid] = {"history": [], "color": color, "last_frame": frame_idx,
                                    "spoken_once": False, "was_lost": False}

            info = self.tracks[tid]
            # Phát hiện tái xuất hiện: track đã mất bám (> DETECT_EVERY*3 frame không thấy)
            if best_match and frame_idx - info["last_frame"] > DETECT_EVERY * 3:
                info["was_lost"] = True
            info["history"].append((t_sec, dx, dy, bx, by))
            if len(info["history"]) > 200:
                info["history"] = info["history"][-200:]
            info["last_frame"] = frame_idx
            info["color"]      = color
            matched.add(tid)

    def get_velocity(self, tid, min_pts=3):
        hist = self.tracks[tid]["history"]
        if len(hist) < min_pts:
            return None, None
        recent = hist[-min(10, len(hist)):]
        ts = np.array([h[0] for h in recent])
        xs = np.array([h[1] for h in recent])
        ys = np.array([h[2] for h in recent])
        if ts[-1] - ts[0] < 0.5:
            return None, None
        return float(np.polyfit(ts, xs, 1)[0]), float(np.polyfit(ts, ys, 1)[0])

    def predict_pos(self, tid, t_ahead_sec):
        vx, vy = self.get_velocity(tid)
        if vx is None:
            return None
        hist = self.tracks[tid]["history"]
        t0, x0, y0 = hist[-1][0], hist[-1][1], hist[-1][2]
        xp = x0 + vx * t_ahead_sec
        yp = y0 + vy * t_ahead_sec
        return xp, yp, int(CX + xp/KM_PX), int(CY - yp/KM_PX)

# ══════════════════════════════════════════════════════════════════════════════
# TOOLTIP
# ══════════════════════════════════════════════════════════════════════════════
_LOAI_VN = {"RED": "Quân sự", "GREEN": "Quá cảnh", "YELLOW": "Không xác định",
             "CYAN": "Địch", "MAGENTA": "Quốc tế"}

def draw_tooltip(canvas, tid, info, mx, my):
    hist = info["history"]
    if not hist:
        return
    _, xkm, ykm, _, _ = hist[-1]
    dist  = float(np.sqrt(xkm**2 + ykm**2))
    bear  = compass_bearing(xkm, ykm)
    color = COLOR_MAP.get(info["color"], UNKNOWN_COL)
    did   = tid if not tid.startswith("?") else "???"

    lines = [
        (f"ID: {did}",                                            (220,220,220), _PIL_FONT),
        (f"Loại: {_LOAI_VN.get(info['color'], info['color'])}",  color,         _PIL_FONT_BD),
        (f"Cự ly:  {int(dist):03d} km",                          (220,220,220), _PIL_FONT),
        (f"Góc:   {int(bear):03d}°",                              (220,220,220), _PIL_FONT),
    ]
    LINE_H = 26; PAD_T = 10; W_BOX = 210
    H_BOX  = len(lines) * LINE_H + PAD_T * 2
    h, w   = canvas.shape[:2]
    bx = mx + 24; by = my - H_BOX // 2
    if bx + W_BOX > w: bx = mx - W_BOX - 24
    by = max(4, min(by, h - H_BOX - 4))

    cv2.rectangle(canvas, (bx-2, by-2), (bx+W_BOX+2, by+H_BOX+2), color, 2)
    cv2.rectangle(canvas, (bx, by),     (bx+W_BOX,   by+H_BOX),   (10,10,10), -1)
    pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    drw = ImageDraw.Draw(pil)
    for i, (text, tcol, fnt) in enumerate(lines):
        drw.text((bx+PAD_T, by+PAD_T+i*LINE_H), text, font=fnt,
                 fill=(tcol[2], tcol[1], tcol[0]))
    np.copyto(canvas, cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR))

# ══════════════════════════════════════════════════════════════════════════════
# DRAW FRAME
# ══════════════════════════════════════════════════════════════════════════════
def draw_frame(canvas, frame_idx, tm, mx=0, my=0):
    hovered_tid = None

    for tid, info in tm.tracks.items():
        if frame_idx - info["last_frame"] > DETECT_EVERY * 3:
            continue
        hist  = info["history"]
        color = COLOR_MAP.get(info["color"], UNKNOWN_COL)
        if not hist:
            continue
        _, xkm, ykm, px_last, py_last = hist[-1]

        # Đuôi lịch sử
        tail = hist[-TAIL_LEN:]
        for k in range(1, len(tail)):
            alpha = k / len(tail)
            c = tuple(int(v * alpha * 0.7) for v in color)
            cv2.line(canvas, (tail[k-1][3], tail[k-1][4]),
                              (tail[k][3],   tail[k][4]), c, 1)

        # Dự đoán
        pred = tm.predict_pos(tid, PRED_SEC)
        if pred:
            xp, yp, pxp, pyp = pred
            for s in range(8):
                f1 = s / 8; f2 = (s+1) / 8
                p1 = (int(px_last+(pxp-px_last)*f1), int(py_last+(pyp-py_last)*f1))
                p2 = (int(px_last+(pxp-px_last)*f2), int(py_last+(pyp-py_last)*f2))
                if s % 2 == 0:
                    cv2.line(canvas, p1, p2, color, 1)
            cv2.arrowedLine(canvas,
                (int(px_last+(pxp-px_last)*0.88), int(py_last+(pyp-py_last)*0.88)),
                (pxp, pyp), color, 1, tipLength=0.4)

        # Icon blip
        cv2.circle(canvas, (px_last, py_last), 9, color, 2)
        cv2.line(canvas, (px_last-5, py_last), (px_last+5, py_last), color, 1)
        cv2.line(canvas, (px_last, py_last-5), (px_last, py_last+5), color, 1)

        if (mx-px_last)**2 + (my-py_last)**2 <= HOVER_RADIUS**2:
            hovered_tid = tid

    if hovered_tid and hovered_tid in tm.tracks:
        draw_tooltip(canvas, hovered_tid, tm.tracks[hovered_tid], mx, my)

    # Thanh trạng thái
    n_active = sum(1 for tid, info in tm.tracks.items()
                   if frame_idx - info["last_frame"] <= DETECT_EVERY * 3
                   and not tid.startswith("?"))
    clock = datetime.now().strftime("%H:%M")
    bar   = (f"  frame={frame_idx}   {n_active} muc tieu   Radar 300km   {clock}"
             f"   [Trai] phat   [Phai] ID/hua   [Q/Esc] thoat")
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 22), (0, 0, 0), -1)
    cv2.putText(canvas, bar, (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,220,220), 1)

    # Nút "Phát tự động" — góc trên bên phải
    fw_c = canvas.shape[1]
    bx1 = fw_c - _BTN_AUTO_W - 4;  bx2 = fw_c - 4
    by1 = 0;                         by2 = _BTN_AUTO_H
    btn_bg  = (0, 110, 0)    if _global_auto_active else (38, 38, 38)
    btn_bdr = (0, 210, 80)   if _global_auto_active else (90, 90, 90)
    btn_txt = "|| DUNG TU DONG" if _global_auto_active else ">  PHAT TU DONG"
    cv2.rectangle(canvas, (bx1, by1), (bx2, by2), btn_bg,  -1)
    cv2.rectangle(canvas, (bx1, by1), (bx2, by2), btn_bdr,  1)
    cv2.putText(canvas, btn_txt, (bx1 + 7, by2 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.44, (225, 225, 225), 1, cv2.LINE_AA)

    return hovered_tid

# ══════════════════════════════════════════════════════════════════════════════
# TABLE
# ══════════════════════════════════════════════════════════════════════════════
def build_table(tm, frame_idx):
    active = [(tid, info) for tid, info in tm.tracks.items()
              if frame_idx - info["last_frame"] <= DETECT_EVERY * 3]
    active.sort(key=lambda x: (x[0].startswith("?"), x[0]))

    n   = max(len(active), 1)
    H   = TABLE_TITLE_H + TABLE_HDR_H + n * TABLE_ROW_H + 4
    img = np.full((H, TABLE_W, 3), (20, 20, 20), dtype=np.uint8)

    cv2.rectangle(img, (0, 0), (TABLE_W, TABLE_TITLE_H), (0,55,55), -1)
    cv2.putText(img, "DANH SACH MUC TIEU [LIVE]", (10, TABLE_TITLE_H-9),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0,230,230), 2, cv2.LINE_AA)
    n_named = sum(1 for t, _ in active if not t.startswith("?"))
    cv2.putText(img, f"{n_named}/{len(active)}", (TABLE_W-60, TABLE_TITLE_H-9),
                cv2.FONT_HERSHEY_SIMPLEX, 0.46, (150,200,150), 1, cv2.LINE_AA)

    hy = TABLE_TITLE_H
    cv2.rectangle(img, (0, hy), (TABLE_W, hy+TABLE_HDR_H), (38,38,38), -1)
    for j, name in enumerate(_COL_HDR):
        cv2.putText(img, name, (_COL_DIV[j]+5, hy+TABLE_HDR_H-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, (0,210,210), 1, cv2.LINE_AA)
    cv2.line(img, (0, hy+TABLE_HDR_H), (TABLE_W, hy+TABLE_HDR_H), (90,90,90), 1)

    for i, (tid, info) in enumerate(active):
        ry  = TABLE_TITLE_H + TABLE_HDR_H + i * TABLE_ROW_H
        bg  = (32,32,32) if i % 2 == 0 else (22,22,22)
        cv2.rectangle(img, (0, ry), (TABLE_W, ry+TABLE_ROW_H), bg, -1)
        hist  = info["history"]
        color = COLOR_MAP.get(info["color"], UNKNOWN_COL)
        did   = tid if not tid.startswith("?") else "???"
        dist_str = bear_str = spd_str = "---"
        if hist:
            _, xkm, ykm, _, _ = hist[-1]
            dist_str = f"{float(np.sqrt(xkm**2+ykm**2)):.0f}"
            bear_str = f"{compass_bearing(xkm, ykm):.0f}"
            vx, vy = tm.get_velocity(tid)
            if vx is not None:
                spd_str = f"{float(np.sqrt(vx**2+vy**2))*3600:.0f}"
        ty    = ry + TABLE_ROW_H - 7
        cells = [(str(i+1),(180,180,180)), (info["color"],color), (did,color),
                 (dist_str,(215,215,215)), (bear_str,(215,215,215)), (spd_str,(215,215,215))]
        for (text, tcol), cx in zip(cells, _COL_DIV):
            cv2.putText(img, text, (cx+5, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.50, tcol, 1, cv2.LINE_AA)
        cv2.line(img, (0, ry+TABLE_ROW_H), (TABLE_W, ry+TABLE_ROW_H), (48,48,48), 1)

    for x in _COL_DIV[1:-1]:
        cv2.line(img, (x, TABLE_TITLE_H), (x, H-1), (60,60,60), 1)
    cv2.rectangle(img, (0, 0), (TABLE_W-1, H-1), (80,80,80), 1)
    return img

# ══════════════════════════════════════════════════════════════════════════════
# LIVE JSON + HTML
# ══════════════════════════════════════════════════════════════════════════════
_HTML_PATH = r"c:\Users\ygost\radar\live_tracks.html"
_CSS_COLOR = {"RED":"#ff4444","GREEN":"#44dd44","YELLOW":"#dddd00",
              "CYAN":"#00dddd","MAGENTA":"#dd44dd"}

def write_live_outputs(tm, frame_idx, fps):
    active = [(tid, info) for tid, info in tm.tracks.items()
              if frame_idx - info["last_frame"] <= DETECT_EVERY * 3]
    active.sort(key=lambda x: (x[0].startswith("?"), x[0]))
    t_sec   = frame_idx / fps
    n_named = sum(1 for t, _ in active if not t.startswith("?"))

    lt = {}
    for tid, info in active:
        if not info["history"]: continue
        _, xkm, ykm, px, py = info["history"][-1]
        vx, vy = tm.get_velocity(tid)
        spd = round(float(np.sqrt(vx**2+vy**2))*3600, 0) if vx else None
        lt[tid] = {"color": info["color"],
                   "dist_km":  round(float(np.sqrt(xkm**2+ykm**2)), 1),
                   "bearing":  round(compass_bearing(xkm, ykm), 1),
                   "speed_kmh": spd, "pos_px": [px, py],
                   "named": not tid.startswith("?")}
    payload = {"frame": frame_idx, "t_sec": round(t_sec, 2), "tracks": lt}
    _p = r"c:\Users\ygost\radar\live_tracks.json"
    with open(_p+".tmp", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    try:
        os.replace(_p+".tmp", _p)
    except PermissionError:
        try: os.remove(_p+".tmp")
        except OSError: pass

    rows = []
    for i, (tid, info) in enumerate(active, 1):
        if not info["history"]: continue
        _, xkm, ykm, _, _ = info["history"][-1]
        color = _CSS_COLOR.get(info["color"], "#aaaaaa")
        did   = tid if not tid.startswith("?") else "???"
        loai  = _LOAI_VN.get(info["color"], info["color"])
        vx, vy = tm.get_velocity(tid)
        rows.append(
            f'<tr><td>{i}</td>'
            f'<td style="color:{color};font-weight:bold">{loai}</td>'
            f'<td style="color:{color};font-weight:bold">{did}</td>'
            f'<td>{float(np.sqrt(xkm**2+ykm**2)):.0f}</td>'
            f'<td>{compass_bearing(xkm, ykm):.0f}</td>'
            f'<td>{"---" if vx is None else f"{float(np.sqrt(vx**2+vy**2))*3600:.0f}"}</td></tr>'
        )
    rows_html = "\n".join(rows) or '<tr><td colspan="6" style="text-align:center;color:#666">Chưa phát hiện</td></tr>'
    html = (
        '<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">'
        '<meta http-equiv="refresh" content="2"><title>Radar Live</title>'
        '<style>body{background:#0a0a0a;color:#ddd;font-family:monospace;margin:0;padding:12px}'
        'h2{color:#00dddd;margin:0 0 6px;font-size:16px;letter-spacing:2px}'
        '.info{color:#888;font-size:12px;margin-bottom:10px}'
        'table{border-collapse:collapse;width:100%;max-width:620px}'
        'th{background:#0d3333;color:#00dddd;padding:7px 10px;text-align:left;font-size:13px;border-bottom:1px solid #1a5555}'
        'td{padding:6px 10px;font-size:13px;border-bottom:1px solid #1a1a1a}'
        'tr:hover td{background:#111}</style></head><body>'
        '<h2>&#9632; RADAR LIVE — DANH SÁCH MỤC TIÊU</h2>'
        f'<div class="info">t={t_sec:.1f}s &nbsp;|&nbsp; '
        f'<b style="color:#44dd44">{n_named}</b>/{len(active)} mục tiêu &nbsp;|&nbsp; '
        '<span style="color:#555">tự cập nhật mỗi 2s</span></div>'
        '<table><thead><tr>'
        '<th>#</th><th>Loại</th><th>ID</th>'
        '<th>Cự ly(km)</th><th>Góc(°)</th><th>Tốc(km/h)</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table></body></html>'
    )
    with open(_HTML_PATH+".tmp", "w", encoding="utf-8") as f:
        f.write(html)
    try:
        os.replace(_HTML_PATH+".tmp", _HTML_PATH)
    except PermissionError:
        try: os.remove(_HTML_PATH+".tmp")
        except OSError: pass

# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# CHUYỂN TỌA ĐỘ CLICK → FRAME SPACE
# Hỗ trợ click từ cả màn nguồn (Monitor 1) lẫn màn output CV2 (Monitor 2)
# ══════════════════════════════════════════════════════════════════════════════
def click_to_frame(sx, sy, cl, ct, cr, cb, fs_mon, frame_shape):
    """
    Trả về (lx, ly) trong frame space, hoặc None nếu click ngoài cả 2 vùng.
    - Nếu click trên màn output (CV2 fullscreen): scale ngược display → frame
    - Nếu click trên cửa sổ nguồn: chỉ cần trừ offset
    """
    fh, fw = frame_shape[:2]
    fl, ft = fs_mon["left"], fs_mon["top"]
    fw_d,  fh_d = fs_mon["width"], fs_mon["height"]
    if fl <= sx < fl + fw_d and ft <= sy < ft + fh_d:
        return int((sx - fl) * fw / fw_d), int((sy - ft) * fh / fh_d)
    if cl <= sx < cr and ct <= sy < cb:
        return sx - cl, sy - ct
    return None

# ══════════════════════════════════════════════════════════════════════════════
# HÀM TÌM BLIP GẦN NHẤT TẠI TỌA ĐỘ LOCAL
# ══════════════════════════════════════════════════════════════════════════════
def find_nearest_blip(lx, ly, tm, frame_idx, radius_mult=2.5):
    best_tid = None; best_d = HOVER_RADIUS * radius_mult
    for _tid, _info in tm.tracks.items():
        if frame_idx - _info["last_frame"] > DETECT_EVERY * 3: continue
        if not _info["history"]: continue
        _, _, _, _px, _py = _info["history"][-1]
        d = np.sqrt((lx-_px)**2 + (ly-_py)**2)
        if d < best_d:
            best_d = d; best_tid = _tid
    return best_tid

# ══════════════════════════════════════════════════════════════════════════════
# XÁC ĐỊNH TÂM RADAR
# ══════════════════════════════════════════════════════════════════════════════
def calibrate_radar_center(frame, mon):
    """
    Hiển thị frame để user chỉnh tâm radar và bán kính 300km.
    S = lưu & cập nhật CX/CY/R_300KM/KM_PX.  Q/Esc = huỷ (giữ nguyên).
    """
    global CX, CY, R_300KM, KM_PX

    fh, fw  = frame.shape[:2]
    max_w   = max(mon["width"]  - 20, 200)
    max_h   = max(mon["height"] - 80, 200)
    scale   = min(max_w / max(fw, 1), max_h / max(fh, 1), 1.0)
    dw, dh  = max(int(fw * scale), 1), max(int(fh * scale), 1)

    _cx   = [CX]; _cy = [CY]; _r = [R_300KM]; _mode = [0]

    def draw_overlay():
        img  = cv2.resize(frame, (dw, dh), interpolation=cv2.INTER_LINEAR)
        cxd  = int(_cx[0] * scale);  cyd = int(_cy[0] * scale)
        rd   = int(_r[0]  * scale);  km_px = 300.0 / max(_r[0], 1)
        # Vòng 300 km
        cv2.circle(img, (cxd, cyd), rd, (0, 180, 255), 2)
        lx = cxd + int(rd * 0.707);  ly = cyd - int(rd * 0.707)
        if 0 < lx < dw - 60 and 4 < ly < dh:
            cv2.putText(img, "300km", (lx+4, ly-4), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,180,255), 2)
        # Crosshair
        cv2.line(img, (0, cyd), (dw, cyd), (0, 255, 255), 1)
        cv2.line(img, (cxd, 0), (cxd, dh), (0, 255, 255), 1)
        cv2.circle(img, (cxd, cyd),  6, (0, 255, 255), -1)
        cv2.circle(img, (cxd, cyd), 14, (0, 255, 255),  2)
        # Info bar (top)
        mode_str = "[CHINH TAM]" if _mode[0] == 0 else "[CHINH BAN KINH]"
        label = f"CX={_cx[0]} CY={_cy[0]}  R={_r[0]}px  {km_px:.4f}km/px  {mode_str}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(img, (6, 6), (14+tw, 16+th), (0,0,0), -1)
        cv2.putText(img, label, (10, 10+th), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,255,255), 1)
        # Help bar (bottom)
        g1 = "[Click T] dat tam  [Click P] ban kinh 300km  [Tab] doi che do"
        g2 = "[WASD/X] tinh chinh  [+/-] ban kinh  [S] Luu  [Q] Huy"
        cv2.rectangle(img, (6, dh-42), (dw-6, dh-4), (0,0,0), -1)
        cv2.putText(img, g1, (10, dh-28), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180,180,180), 1)
        cv2.putText(img, g2, (10, dh-10), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180,180,180), 1)
        return img

    def on_mouse(event, x, y, flags, param):
        fx = int(x / scale + 0.5);  fy = int(y / scale + 0.5)
        if event == cv2.EVENT_LBUTTONDOWN:
            _cx[0] = fx;  _cy[0] = fy;  _mode[0] = 0
        elif event == cv2.EVENT_RBUTTONDOWN:
            _r[0]  = max(10, int(np.sqrt((fx-_cx[0])**2 + (fy-_cy[0])**2)))
            _mode[0] = 1

    WIN_CAL = "Dat Tam Radar — S:Luu  Q:Huy"
    cv2.namedWindow(WIN_CAL, cv2.WINDOW_AUTOSIZE)
    cv2.moveWindow(WIN_CAL, mon["left"] + 10, mon["top"] + 10)
    cv2.setMouseCallback(WIN_CAL, on_mouse)

    while True:
        cv2.imshow(WIN_CAL, draw_overlay())
        key = cv2.waitKey(30) & 0xFF
        if   key in (ord('s'), ord('S')):
            CX = _cx[0];  CY = _cy[0]
            R_300KM = _r[0];  KM_PX = 300.0 / max(R_300KM, 1)
            print(f"[CALIB] Luu: CX={CX} CY={CY} R_300KM={R_300KM} KM_PX={KM_PX:.4f}")
            break
        elif key in (ord('q'), 27):
            print("[CALIB] Huy — giu nguyen toa do cu.")
            break
        elif key == 9:               _mode[0] = 1 - _mode[0]   # Tab
        elif key in (82, ord('w')):  _cy[0] -= 1                # len
        elif key in (84, ord('x')):  _cy[0] += 1                # xuong
        elif key in (81, ord('a')):  _cx[0] -= 1                # trai
        elif key in (83, ord('d')):  _cx[0] += 1                # phai (83 != ord('S'))
        elif key in (ord('+'), ord('=')):  _r[0] += 1
        elif key == ord('-'):              _r[0] = max(10, _r[0] - 1)

    cv2.destroyWindow(WIN_CAL)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("=== RADAR LIVE CAPTURE ===\n")

    # 1. Chọn cửa sổ nguồn
    hwnd, win_title = choose_window()
    print(f"\n[OK] Cửa sổ: '{win_title}'  hwnd={hwnd}")

    # 2. Tự động phát hiện màn hình
    sct      = mss.MSS()
    monitors = sct.monitors[1:]   # [1]+ = từng màn riêng

    try:
        wl, wt, wr, wb = get_client_screen_rect(hwnd)
        win_cx, win_cy  = (wl + wr) // 2, (wt + wb) // 2
    except Exception:
        win_cx, win_cy  = 0, 0

    src_idx = 0
    for i, m in enumerate(monitors):
        if (m["left"] <= win_cx < m["left"] + m["width"] and
                m["top"] <= win_cy < m["top"] + m["height"]):
            src_idx = i; break

    other_mons = [m for i, m in enumerate(monitors) if i != src_idx]
    fs_mon  = other_mons[0] if other_mons else monitors[src_idx]
    tbl_mon = monitors[src_idx]

    print(f"[MONITOR] Tất cả màn hình:")
    for i, m in enumerate(monitors):
        tag = " <-- NGUON" if i == src_idx else (" <-- OUTPUT CV2" if m is fs_mon else "")
        print(f"  [{i+1}] {m['width']}x{m['height']} @({m['left']},{m['top']}){tag}")
    print(f"[OK] Nguồn: Monitor {src_idx+1} — Output fullscreen: "
          f"{fs_mon['width']}x{fs_mon['height']} @({fs_mon['left']},{fs_mon['top']})")

    # ── Xác định tâm radar ───────────────────────────────────────────────────
    _root = tk.Tk()
    _root.withdraw()
    _root.attributes("-topmost", True)
    _keep = tkinter.messagebox.askyesno(
        "Tâm Radar",
        f"Giữ nguyên tâm radar?\n\n"
        f"CX = {CX}   CY = {CY}\n"
        f"R_300KM = {R_300KM} px   ({KM_PX:.4f} km/px)",
        parent=_root,
    )
    _root.destroy()

    if not _keep:
        try:
            _wl, _wt, _wr, _wb = get_client_screen_rect(hwnd)
            if _wr > _wl and _wb > _wt:
                _mon_grab = {"left": _wl, "top": _wt, "width": _wr-_wl, "height": _wb-_wt}
                _first    = cv2.cvtColor(np.array(sct.grab(_mon_grab)), cv2.COLOR_BGRA2BGR)
            else:
                _first = np.zeros((480, 640, 3), np.uint8)
        except Exception as _e:
            print(f"[CALIB] Khong chup duoc frame: {_e}")
            _first = np.zeros((480, 640, 3), np.uint8)
        calibrate_radar_center(_first, tbl_mon)

    # 3. Audio
    try:
        pygame.mixer.init()
        print("[AUDIO] OK")
    except Exception as e:
        print(f"[AUDIO] Lỗi: {e}")
    threading.Thread(target=_audio_worker, daemon=True).start()

    # 4. pynput — chỉ cần mouse listener
    m_listener = pmouse.Listener(on_click=_on_mouse_click)
    m_listener.start()
    print("[INPUT] Mouse listener OK")

    # 5. TrackManager + CV2 windows
    FAKE_FPS = float(TARGET_FPS)
    tm        = TrackManager(FAKE_FPS)
    table_img = build_table(tm, 0)
    table_scroll_y = 0
    cv_mouse   = [0, 0]   # tọa độ display (monitor space)

    def on_cv_mouse(event, x, y, flags, param):
        cv_mouse[0] = x; cv_mouse[1] = y

    def on_table_scroll(event, x, y, flags, param):
        nonlocal table_scroll_y
        if event == cv2.EVENT_MOUSEWHEEL:
            step = TABLE_ROW_H * 3
            if flags > 0: table_scroll_y = max(0, table_scroll_y - step)
            else:          table_scroll_y += step

    cv2.namedWindow("Radar Live", cv2.WINDOW_NORMAL)
    cv2.moveWindow("Radar Live", fs_mon["left"], fs_mon["top"])
    cv2.setWindowProperty("Radar Live", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback("Radar Live", on_cv_mouse)

    cv2.namedWindow("Bang thong tin", cv2.WINDOW_AUTOSIZE)
    cv2.moveWindow("Bang thong tin", tbl_mon["left"] + 10, tbl_mon["top"] + 10)
    cv2.setMouseCallback("Bang thong tin", on_table_scroll)

    # 6. Capture loop
    frame_idx = 0
    FRAME_DT  = 1.0 / TARGET_FPS

    print(f"[OK] Chạy {TARGET_FPS} fps.  Chuột TRÁI: phát   Chuột PHẢI: ID/hẹn giờ   Q/Esc: thoát\n")

    try:
        while True:
            t0 = time.perf_counter()

            # Vị trí client area (cập nhật mỗi frame — theo window di chuyển)
            try:
                cl, ct, cr, cb = get_client_screen_rect(hwnd)
            except Exception:
                time.sleep(0.1); continue
            if cr <= cl or cb <= ct:
                time.sleep(0.05); continue

            # Chụp frame
            mon    = {"left": cl, "top": ct, "width": cr-cl, "height": cb-ct}
            sct_img = sct.grab(mon)
            frame   = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)

            # Detect + track mỗi DETECT_EVERY frame
            if frame_idx % DETECT_EVERY == 0:
                blips = detect_blips(frame)
                tm.update(frame_idx, blips)
                table_img = build_table(tm, frame_idx)
                write_live_outputs(tm, frame_idx, FAKE_FPS)
                print(f"\r  frame={frame_idx}  tracks={len(tm.tracks)}", end="", flush=True)

            # ── Chuột TRÁI: button "Phat tu dong" hoặc phát mục tiêu ──────────
            while not _left_click_q.empty():
                sx, sy = _left_click_q.get_nowait()
                coords = click_to_frame(sx, sy, cl, ct, cr, cb, fs_mon, frame.shape)
                if coords:
                    lx, ly = coords
                    fw_f = frame.shape[1]
                    # Kiểm tra click vào nút "Phát tự động"
                    if fw_f - _BTN_AUTO_W - 4 <= lx <= fw_f - 4 and 0 <= ly <= _BTN_AUTO_H:
                        toggle_global_auto(tm)
                    else:
                        hit = find_nearest_blip(lx, ly, tm, frame_idx)
                        if hit:
                            speak_target(hit, tm.tracks[hit])

            # ── Chuột PHẢI: dialog ID + auto-speak ───────────────────────────
            while not _right_click_q.empty():
                sx, sy = _right_click_q.get_nowait()
                coords = click_to_frame(sx, sy, cl, ct, cr, cb, fs_mon, frame.shape)
                if coords:
                    hit = find_nearest_blip(coords[0], coords[1], tm, frame_idx)
                    if hit:
                        show_target_dialog(hit, tm)

            # ── Vẽ ───────────────────────────────────────────────────────────
            canvas = frame.copy()
            fh, fw = frame.shape[:2]
            # cv_mouse là tọa độ trong cửa sổ CV2 (0→fs_mon["width"]) → scale về frame space
            frame_mx = int(cv_mouse[0] * fw / max(fs_mon["width"],  1))
            frame_my = int(cv_mouse[1] * fh / max(fs_mon["height"], 1))
            frame_mx = max(0, min(frame_mx, fw - 1))
            frame_my = max(0, min(frame_my, fh - 1))
            draw_frame(canvas, frame_idx, tm, frame_mx, frame_my)

            display = cv2.resize(canvas, (fs_mon["width"], fs_mon["height"]),
                                 interpolation=cv2.INTER_LINEAR)
            cv2.imshow("Radar Live", display)

            # Bảng
            _max_s = max(0, table_img.shape[0] - TABLE_WIN_H)
            table_scroll_y = min(table_scroll_y, _max_s)
            _view = table_img[table_scroll_y : table_scroll_y + TABLE_WIN_H]
            if _view.shape[0] < TABLE_WIN_H:
                _pad  = np.zeros((TABLE_WIN_H - _view.shape[0], TABLE_W, 3), np.uint8)
                _view = np.vstack([_view, _pad])
            cv2.imshow("Bang thong tin", _view)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):
                break

            frame_idx += 1

            # Throttle FPS
            elapsed = time.perf_counter() - t0
            if elapsed < FRAME_DT:
                time.sleep(FRAME_DT - elapsed)

    except KeyboardInterrupt:
        pass
    finally:
        m_listener.stop()
        sct.close()
        _global_auto_stop.set()
        stop_auto_speak()
        cv2.destroyAllWindows()
        _audio_queue.put(None)
        print(f"\n[OK] Xong. Tổng tracks: {len(tm.tracks)}")

        out = {}
        for tid, info in tm.tracks.items():
            out[tid] = {"color": info["color"], "history": [
                {"t": h[0], "dx_km": round(h[1],1), "dy_km": round(h[2],1),
                 "dist_km": round(float(np.sqrt(h[1]**2+h[2]**2)),1),
                 "bearing": round(compass_bearing(h[1], h[2]), 1)}
                for h in info["history"]
            ]}
        with open(r"c:\Users\ygost\radar\tracks.json", "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"Tracks: {sorted(out.keys())}")

if __name__ == "__main__":
    # Per-monitor DPI aware: mọi Win32 API (win32gui, mss, pynput) dùng physical pixels
    # Phải gọi trước bất kỳ cửa sổ nào được tạo
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass
    main()
