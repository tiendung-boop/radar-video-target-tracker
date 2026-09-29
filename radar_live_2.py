"""
Radar Live Capture v2 — bản fork từ radar_live_capture.py, giữ nguyên cách thu
nhận khung hình (USB/HDMI capture card lấy nguyên trạng dữ liệu màn hình nguồn,
không crop/scale), chỉ nâng cấp phần BÁM MỤC TIÊU (track association) cho ổn
định hơn:
- Ghép blip↔track theo thuật toán "global nearest-pair" (xét toàn bộ cặp rồi
  gán từ khoảng cách nhỏ nhất trở lên) thay vì vòng lặp theo thứ tự blip —
  tránh việc một đốm nhiễu (noise speck do nén/nhiễu tín hiệu capture) đứng
  gần "cướp" mất track của mục tiêu thật đã khoá trước đó.
- Ưu tiên ghép CÙNG MÀU trước (đúng máy bay), chỉ chấp nhận khác màu ở vòng
  dự phòng với bán kính hẹp hơn (đề phòng màu bị đọc sai do ảnh nén/mờ).
- Dùng VỊ TRÍ DỰ ĐOÁN (ngoại suy theo vận tốc hiện tại) thay vì vị trí cũ cố
  định để gating — mục tiêu đang di chuyển vẫn được bám đúng thay vì bị neo
  vào điểm cũ rồi lệch sang blip/nhiễu khác gần đó.
- Lọc bớt nhiễu 1 pixel ở bước detect (morphological OPEN) trước khi giãn nở,
  giảm số lượng đốm giả mà bước ghép track phải xử lý.

Phần còn lại (dò cổng vào, TTS, bảng mục tiêu, live_tracks.json/html,
calibration tâm radar) giữ nguyên như radar_live_capture.py.
"""
import ctypes
import cv2
import numpy as np
import json
import re
import threading
import queue
import os
import sys
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import mss
import win32com.client
from pynput import mouse as pmouse
from pynput import keyboard as pkeyboard
import pygame
import tkinter as tk
from tkinter import ttk
import tkinter.messagebox

try:
    import serial as _pyserial
    import serial.tools.list_ports as _list_ports
    _HAS_PYSERIAL = True
except ImportError:
    _HAS_PYSERIAL = False

try:
    _PIL_FONT    = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf",   18)
    _PIL_FONT_BD = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 18)
except Exception:
    _PIL_FONT = _PIL_FONT_BD = ImageFont.load_default()

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
# Radar calibration — chỉnh lại bằng bước "calibrate" khi chạy (nguồn ngoài đổi tuỳ máy)
CX, CY   = 784, 497
R_300KM  = 414
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
MAX_VIDEO_PROBE = 6      # số index tối đa dò tìm thiết bị video capture
CAPTURE_W, CAPTURE_H = 1920, 1080   # yêu cầu độ phân giải cao khi mở thiết bị capture
                                     # (DirectShow mặc định 640x480 nếu không set, chỉ lấy 1 góc/crop nhỏ)

# Shift + chuột trái để bám mục tiêu tại điểm màu bất kỳ (thay cho double-click)
SHIFT_CLICK_SKIP_RADIUS = 25   # px — nếu đã có track trong bán kính này thì bỏ qua, không tạo mới

# Thư mục gốc của app: cạnh file .exe khi đã đóng gói (PyInstaller), cạnh file
# .py khi chạy trực tiếp bằng Python — để mọi output (json/html) và asset
# (speak/) luôn nằm cùng chỗ với app, chạy được trên máy khác không cần sửa gì.
_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
            else os.path.dirname(os.path.abspath(__file__))

# Audio
SPEAK_DIR     = os.path.join(_BASE_DIR, "speak")
_audio_queue  = queue.Queue()
_audio_cancel = threading.Event()

# ──────────────────────────────────────────────────────────────────────────────
# BEARING: Bắc = 0°, chiều kim đồng hồ = dương, 0 – 360°
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

# Ngưỡng HSV cho từng màu quy định — dùng chung cho detect_blips() (quét cả khung)
# và classify_color_at() (quét 1 điểm khi double-click). V=80 (thay vì 130) để bắt
# được màu bị tối do ảnh mờ/nén.
HSV_RANGES = {
    "RED":     [((0,  100, 80),(12, 255,255)), ((168,100, 80),(180,255,255))],
    "GREEN":   [((40,  70, 80),(85, 255,255))],
    "YELLOW":  [((18,  90, 80),(38, 255,255))],
    "CYAN":    [((85,  70, 80),(105,255,255))],
    "MAGENTA": [((135, 70, 80),(165,255,255))],
}

def classify_color_at(frame, x, y, radius=3):
    """Quét vùng nhỏ quanh (x,y) trong frame BGR, trả về tên màu quy định có
    nhiều pixel khớp nhất, hoặc None nếu không có màu nào khớp."""
    h, w = frame.shape[:2]
    x0, x1 = max(0, x - radius), min(w, x + radius + 1)
    y0, y1 = max(0, y - radius), min(h, y + radius + 1)
    if x1 <= x0 or y1 <= y0:
        return None
    patch = frame[y0:y1, x0:x1]
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    best_name, best_count = None, 0
    for name, ranges in HSV_RANGES.items():
        m = np.zeros(hsv.shape[:2], np.uint8)
        for lo, hi in ranges:
            m = cv2.bitwise_or(m, cv2.inRange(hsv, np.array(lo), np.array(hi)))
        cnt = int(cv2.countNonZero(m))
        if cnt > best_count:
            best_count, best_name = cnt, name
    return best_name

# Table
TABLE_W       = 510
TABLE_WIN_H   = 300
TABLE_TITLE_H = 36
TABLE_HDR_H   = 30
TABLE_ROW_H   = 28
_COL_DIV = [0, 42, 130, 198, 288, 378, TABLE_W]
_COL_HDR = ["STT", "Mau", "ID", "Cu ly(km)", "GPV(deg)", "Toc(km/h)"]

# ══════════════════════════════════════════════════════════════════════════════
# DÒ CỔNG VÀO: video capture (HDMI/USB), COM/Serial, thiết bị PnP khác
# ══════════════════════════════════════════════════════════════════════════════
def _wmi_query(select_clause, where_clause):
    out = []
    try:
        wmi = win32com.client.GetObject("winmgmts:")
        for it in wmi.ExecQuery(f"SELECT {select_clause} FROM Win32_PnPEntity WHERE {where_clause}"):
            out.append(it)
    except Exception:
        pass
    return out

def _wmi_video_names():
    names = []
    for it in _wmi_query("Name", "PNPClass='Camera' OR PNPClass='Image' OR PNPClass='MEDIA' OR PNPClass='AVC'"):
        if getattr(it, "Name", None):
            names.append(it.Name)
    return names

def list_video_capture_devices(max_index=MAX_VIDEO_PROBE):
    """Dò index 0..N-1 qua DirectShow, giữ lại thiết bị mở được và đọc được frame."""
    devices = []
    wmi_names = _wmi_video_names()
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        opened = cap.isOpened()
        w = h = 0
        ok = False
        if opened:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAPTURE_W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_H)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            ok, _frame = cap.read()
        cap.release()
        if not opened or not ok or w <= 0 or h <= 0:
            continue
        label = wmi_names[idx] if idx < len(wmi_names) else f"Video Capture #{idx}"
        devices.append({"index": idx, "name": label, "res": f"{w}x{h}"})
    return devices

def list_serial_ports():
    ports = []
    if _HAS_PYSERIAL:
        for p in _list_ports.comports():
            ports.append({"port": p.device, "desc": p.description or p.device, "hwid": p.hwid or ""})
        return ports
    # Fallback không cần pyserial: chỉ liệt kê tên qua WMI (không mở được cổng)
    for it in _wmi_query("Name, DeviceID", "Name LIKE '%(COM%'"):
        name = getattr(it, "Name", "") or ""
        i = name.rfind("(COM")
        port = name[i+1:-1] if i != -1 else name
        ports.append({"port": port, "desc": name, "hwid": getattr(it, "DeviceID", "") or ""})
    return ports

_OTHER_PNP_CLASSES = ["USB", "Ports", "SoundVideo", "Net", "Mouse", "Keyboard",
                       "HIDClass", "Media", "Camera", "Image", "AVC", "WPD", "USBDevice"]

def list_other_devices(limit=60):
    devices = []
    seen = set()
    where = " OR ".join(f"PNPClass='{c}'" for c in _OTHER_PNP_CLASSES)
    for it in _wmi_query("Name, PNPClass, Status", where):
        name = getattr(it, "Name", None)
        if not name or name in seen:
            continue
        seen.add(name)
        devices.append({"name": name, "class": getattr(it, "PNPClass", None) or "?",
                        "status": getattr(it, "Status", None) or "?"})
    return devices[:limit]

def scan_ports():
    print("[SCAN] Dang do video capture (HDMI/USB)...", flush=True)
    video = list_video_capture_devices()
    print("[SCAN] Dang do cong COM/Serial...", flush=True)
    serial_ports = list_serial_ports()
    print("[SCAN] Dang do thiet bi PnP khac...", flush=True)
    other = list_other_devices()
    print(f"[SCAN] Xong — video:{len(video)}  COM:{len(serial_ports)}  khac:{len(other)}", flush=True)
    return {"video": video, "serial": serial_ports, "other": other}

# ══════════════════════════════════════════════════════════════════════════════
# DIALOG CHỌN CỔNG VÀO — bảng hiện đã kết nối với gì
# ══════════════════════════════════════════════════════════════════════════════
def show_port_selection_dialog(scan_result):
    """Trả về dict {'type': 'video'|'serial'|'other'|'refresh', ...} hoặc None nếu huỷ."""
    result = {"value": None}

    root = tk.Tk()
    root.title("Chọn cổng tín hiệu vào")
    root.geometry("780x480")
    root.configure(bg="#111")
    root.attributes("-topmost", True)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("Treeview", background="#1a1a1a", fieldbackground="#1a1a1a",
                     foreground="#dddddd", rowheight=26, font=("Consolas", 10))
    style.configure("Treeview.Heading", background="#0d3333", foreground="#00dddd",
                     font=("Consolas", 10, "bold"))
    style.map("Treeview", background=[("selected", "#005555")])

    tk.Label(root, text="Các cổng vào đã dò được — chọn một thiết bị rồi bấm Chọn:",
             bg="#111", fg="#00dddd", font=("Consolas", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 4))

    tree = ttk.Treeview(root, columns=("info", "status"), show="tree headings", height=16)
    tree.heading("#0", text="Thiết bị")
    tree.heading("info", text="Chi tiết")
    tree.heading("status", text="Trạng thái")
    tree.column("#0", width=300)
    tree.column("info", width=290)
    tree.column("status", width=150)
    tree.pack(fill="both", expand=True, padx=12, pady=4)

    node_map = {}

    cat_video = tree.insert("", "end", text="VIDEO / HDMI CAPTURE", open=True)
    for d in scan_result["video"]:
        iid = tree.insert(cat_video, "end", text=d["name"],
                           values=(f"index={d['index']}  {d['res']}", "Đã kết nối — có tín hiệu"))
        node_map[iid] = {"type": "video", "index": d["index"], "name": d["name"]}
    if not scan_result["video"]:
        tree.insert(cat_video, "end", text="(không tìm thấy thiết bị video)", values=("", "—"))

    cat_serial = tree.insert("", "end", text="COM / SERIAL", open=True)
    for d in scan_result["serial"]:
        iid = tree.insert(cat_serial, "end", text=d["port"],
                           values=(d["desc"], "Khả dụng" if _HAS_PYSERIAL else "Khả dụng (cần cài pyserial)"))
        node_map[iid] = {"type": "serial", "port": d["port"], "name": d["desc"]}
    if not scan_result["serial"]:
        tree.insert(cat_serial, "end", text="(không tìm thấy cổng COM)", values=("", "—"))

    cat_other = tree.insert("", "end", text="THIẾT BỊ KHÁC (USB / PnP)", open=False)
    for d in scan_result["other"]:
        iid = tree.insert(cat_other, "end", text=d["name"], values=(d["class"], d["status"]))
        node_map[iid] = {"type": "other", "name": d["name"]}

    btn_frame = tk.Frame(root, bg="#111")
    btn_frame.pack(fill="x", padx=12, pady=(4, 12))

    def on_select(_event=None):
        sel = tree.selection()
        if not sel or sel[0] not in node_map:
            tkinter.messagebox.showwarning("Chưa chọn", "Hãy chọn một thiết bị cụ thể trong danh sách.", parent=root)
            return
        result["value"] = node_map[sel[0]]
        root.destroy()

    def on_refresh():
        result["value"] = {"type": "refresh"}
        root.destroy()

    def on_cancel():
        root.destroy()

    tk.Button(btn_frame, text="Làm mới", width=12, bg="#333333", fg="#ffffff",
              font=("Consolas", 10), relief="flat", command=on_refresh).pack(side="left", padx=4)
    tk.Button(btn_frame, text="Chọn", width=12, bg="#005555", fg="#ffffff",
              font=("Consolas", 10), relief="flat", command=on_select).pack(side="right", padx=4)
    tk.Button(btn_frame, text="Huỷ", width=12, bg="#553300", fg="#ffffff",
              font=("Consolas", 10), relief="flat", command=on_cancel).pack(side="right", padx=4)

    tree.bind("<Double-1>", on_select)
    root.mainloop()
    return result["value"]

# ══════════════════════════════════════════════════════════════════════════════
# SERIAL MONITOR (chế độ đơn giản khi chọn cổng COM — không có blip tracking)
# ══════════════════════════════════════════════════════════════════════════════
def _ask_baud_rate(port_name):
    result = {"value": None}
    root = tk.Tk()
    root.title(f"Tốc độ baud — {port_name}")
    root.configure(bg="#111")
    root.attributes("-topmost", True)

    tk.Label(root, text=f"Cổng: {port_name}", bg="#111", fg="#00dddd",
             font=("Consolas", 11)).grid(row=0, column=0, columnspan=2, padx=14, pady=(14, 4), sticky="w")
    tk.Label(root, text="Baud rate:", bg="#111", fg="#00dddd",
             font=("Consolas", 11)).grid(row=1, column=0, padx=14, pady=4, sticky="w")
    baud_var = tk.StringVar(value="9600")
    combo = ttk.Combobox(root, textvariable=baud_var, width=14,
                          values=["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"])
    combo.grid(row=1, column=1, padx=14, pady=4)

    def on_ok(_event=None):
        try:
            result["value"] = int(baud_var.get())
        except ValueError:
            result["value"] = 9600
        root.destroy()

    def on_cancel():
        root.destroy()

    btn_frame = tk.Frame(root, bg="#111")
    btn_frame.grid(row=2, column=0, columnspan=2, pady=(8, 14))
    tk.Button(btn_frame, text="Mở cổng", width=10, bg="#005555", fg="#ffffff",
              relief="flat", command=on_ok).pack(side="left", padx=6)
    tk.Button(btn_frame, text="Huỷ", width=10, bg="#333", fg="#aaaaaa",
              relief="flat", command=on_cancel).pack(side="left", padx=6)
    root.bind("<Return>", on_ok)
    root.mainloop()
    return result["value"]

def run_serial_monitor(choice):
    if not _HAS_PYSERIAL:
        _root = tk.Tk(); _root.withdraw(); _root.attributes("-topmost", True)
        tkinter.messagebox.showerror(
            "Thiếu pyserial",
            "Cần cài pyserial để đọc dữ liệu COM:\n\n    pip install pyserial\n\n"
            f"Cổng đã chọn: {choice['port']}", parent=_root)
        _root.destroy()
        return

    baud = _ask_baud_rate(choice["port"])
    if baud is None:
        return
    try:
        ser = _pyserial.Serial(choice["port"], baudrate=baud, timeout=0.5)
    except Exception as e:
        _root = tk.Tk(); _root.withdraw(); _root.attributes("-topmost", True)
        tkinter.messagebox.showerror("Lỗi mở cổng", f"Không mở được {choice['port']}:\n{e}", parent=_root)
        _root.destroy()
        return

    print(f"[SERIAL] Đã mở {choice['port']} @ {baud} baud. Đóng cửa sổ để dừng.")
    win = tk.Tk()
    win.title(f"Serial Monitor — {choice['port']} @ {baud}")
    win.configure(bg="#0a0a0a")
    win.geometry("640x420")
    tk.Label(win, text="Dữ liệu thô nhận từ cổng COM (không phải khung hình radar):",
             bg="#0a0a0a", fg="#888888", font=("Consolas", 9)).pack(anchor="w", padx=6, pady=(6, 0))
    txt = tk.Text(win, bg="#0a0a0a", fg="#33dd33", insertbackground="#33dd33",
                   font=("Consolas", 10), wrap="word")
    txt.pack(fill="both", expand=True, padx=6, pady=6)
    stop_evt = threading.Event()

    def _reader():
        while not stop_evt.is_set():
            try:
                line = ser.readline()
            except Exception:
                break
            if line:
                ts = datetime.now().strftime("%H:%M:%S")
                text = line.decode(errors="replace").rstrip()
                try:
                    txt.insert("end", f"[{ts}] {text}\n")
                    txt.see("end")
                except tk.TclError:
                    break

    thr = threading.Thread(target=_reader, daemon=True)
    thr.start()

    def _on_close():
        stop_evt.set()
        try:
            ser.close()
        except Exception:
            pass
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)
    win.mainloop()
    stop_evt.set()

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL MOUSE + KEYBOARD HOOKS (pynput)
# ══════════════════════════════════════════════════════════════════════════════
_left_click_q  = queue.Queue()
_right_click_q = queue.Queue()
_delete_key_q  = queue.Queue()
_shift_state   = {"held": False}

def _on_mouse_click(x, y, button, pressed):
    if not pressed:
        return
    if button == pmouse.Button.left:
        _left_click_q.put((x, y))
    elif button == pmouse.Button.right:
        _right_click_q.put((x, y))

_SHIFT_KEYS = (pkeyboard.Key.shift, pkeyboard.Key.shift_l, pkeyboard.Key.shift_r)

def _on_key_press(key):
    if key in _SHIFT_KEYS:
        _shift_state["held"] = True
    elif key == pkeyboard.Key.delete:
        _delete_key_q.put(True)

def _on_key_release(key):
    if key in _SHIFT_KEYS:
        _shift_state["held"] = False

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
        item = _audio_queue.get()
        if item is None:
            break
        clips, gap = item if isinstance(item, tuple) else (item, 0.0)
        _audio_cancel.clear()
        for clip in clips:
            if not _play_clip(clip):
                break
            if gap > 0 and not _audio_cancel.is_set():
                time.sleep(gap)

def speak_target(tid, info, prefix=None, interrupt=True, slow=False):
    hist = info["history"]
    if not hist:
        return
    _, xkm, ykm, _, _ = hist[-1]
    dist = int(np.sqrt(xkm**2 + ykm**2) + 0.5)
    bear = int(compass_bearing(xkm, ykm) + 0.5)
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
    if interrupt:
        if pygame.mixer.music.get_busy():
            _audio_cancel.set()
        while not _audio_queue.empty():
            try:
                _audio_queue.get_nowait()
            except queue.Empty:
                break
    _audio_queue.put((clips, AUTO_SLOW_GAP) if slow else clips)

# ══════════════════════════════════════════════════════════════════════════════
# AUTO-SPEAK
# ══════════════════════════════════════════════════════════════════════════════
_auto_speak_threads = {}
_audio_auto_lock    = threading.Lock()

def _auto_speak_worker(tid, interval, stop_evt, tm_ref):
    stop_evt.wait(0.2)
    while not stop_evt.is_set():
        if tid in tm_ref.tracks:
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
        stop_evt.wait(interval)

def start_auto_speak(tid, interval, tm):
    if tid in _auto_speak_threads:
        old_evt, old_thr = _auto_speak_threads.pop(tid)
        old_evt.set()
        old_thr.join(timeout=1.5)
    stop_evt = threading.Event()
    thr = threading.Thread(target=_auto_speak_worker, args=(tid, interval, stop_evt, tm), daemon=True)
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
# GLOBAL AUTO-SPEAK
# ══════════════════════════════════════════════════════════════════════════════
_global_auto_active = False
_global_auto_stop   = threading.Event()
_global_auto_thread = None

_global_auto_slow_active = False
_global_auto_slow_stop   = threading.Event()
_global_auto_slow_thread = None
AUTO_SLOW_GAP = 0.35   # giây nghỉ giữa mỗi chữ số khi đọc chậm

# Chế độ của phiên Phát tự động/chậm HIỆN TẠI, quyết định lúc bấm bật:
#   True  = "tự do quét" — lúc bật CHƯA có mục tiêu nào được chọn thủ công
#           (Shift+trái) → tự động dò + đọc mọi blip trong 150km, và xoá hết
#           các track tự động này khi dừng.
#   False = "chỉ mục tiêu đã chọn" — lúc bật ĐÃ có ít nhất 1 mục tiêu được
#           chọn thủ công → không tự dò thêm nữa, chỉ đọc các mục tiêu đã chọn.
_auto_scan_mode = False

def _start_auto_session(tm):
    global _auto_scan_mode
    _auto_scan_mode = not any(not info.get("auto", False) for info in tm.tracks.values())

def _finish_auto_session(tm):
    """Nếu phiên vừa dừng là phiên tự-do-quét: xoá hết các track do phiên đó
    tự tạo ra (auto=True), coi như dọn sạch, không giữ lại gì sau khi dừng."""
    if not _auto_scan_mode:
        return
    to_delete = [tid for tid, info in tm.tracks.items() if info.get("auto", False)]
    for tid in to_delete:
        stop_auto_speak(tid)
        del tm.tracks[tid]
    if to_delete:
        print(f"[GLOBAL-AUTO] Da xoa {len(to_delete)} muc tieu tu-dong-quet khi dung", flush=True)

def _global_auto_worker(stop_evt, tm_ref, slow=False):
    while not stop_evt.is_set():
        candidates = []
        for tid, info in list(tm_ref.tracks.items()):
            if not _auto_scan_mode and info.get("auto", False):
                continue   # che do "chi muc tieu da chon" — bo qua track tu dong
            hist = info.get("history")
            if not hist:
                continue
            _, xkm, ykm, _, _ = hist[-1]
            dist = float(np.sqrt(xkm**2 + ykm**2))
            if dist > GLOBAL_RADIUS:
                continue
            candidates.append((tid, info, dist, not info.get("spoken_once", False), bool(info.get("was_lost", False))))

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
                        speak_target(tid, info, prefix=prefix, interrupt=False, slow=slow)
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
        _finish_auto_session(tm)
        print("[GLOBAL-AUTO] Dung", flush=True)
    else:
        if _global_auto_slow_active:
            toggle_global_auto_slow(tm)
        _start_auto_session(tm)
        _global_auto_stop = threading.Event()
        _global_auto_thread = threading.Thread(target=_global_auto_worker, args=(_global_auto_stop, tm, False), daemon=True)
        _global_auto_thread.start()
        _global_auto_active = True
        mode_txt = "tu dong quet" if _auto_scan_mode else "chi muc tieu da chon"
        print(f"[GLOBAL-AUTO] Bat dau (nhanh) — {mode_txt} <= 150km", flush=True)

def toggle_global_auto_slow(tm):
    global _global_auto_slow_active, _global_auto_slow_stop, _global_auto_slow_thread
    if _global_auto_slow_active:
        _global_auto_slow_stop.set()
        _global_auto_slow_active = False
        _finish_auto_session(tm)
        print("[GLOBAL-AUTO-CHAM] Dung", flush=True)
    else:
        if _global_auto_active:
            toggle_global_auto(tm)
        _start_auto_session(tm)
        _global_auto_slow_stop = threading.Event()
        _global_auto_slow_thread = threading.Thread(target=_global_auto_worker, args=(_global_auto_slow_stop, tm, True), daemon=True)
        _global_auto_slow_thread.start()
        _global_auto_slow_active = True
        mode_txt = "tu dong quet" if _auto_scan_mode else "chi muc tieu da chon"
        print(f"[GLOBAL-AUTO-CHAM] Bat dau (cham) — {mode_txt} <= 150km", flush=True)

def auto_confirm_nearby(tm, frame_idx, unmatched_blips):
    """Khi Phát tự động/chậm đang bật VÀ đang ở chế độ tự-do-quét (chưa có
    mục tiêu nào được chọn thủ công lúc bật): tự động xác nhận (tạo track,
    auto=True) cho mọi blip trong bán kính GLOBAL_RADIUS (150km), để auto-speak
    đọc được cả những mục tiêu chưa từng click. Nếu đã có mục tiêu được chọn
    thủ công từ trước, KHÔNG tự dò thêm nữa — chỉ đọc các mục tiêu đã chọn."""
    if not (_global_auto_active or _global_auto_slow_active):
        return
    if not _auto_scan_mode:
        return
    for blip in unmatched_blips:
        bx, by, area, dist, bear, color, dx, dy = blip
        if dist <= GLOBAL_RADIUS:
            tm.confirm_candidate(frame_idx, bx, by, color, dx, dy, auto=True)

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

        tk.Label(root, text="ID mục tiêu:", **style_lbl).grid(row=0, column=0, padx=14, pady=(14, 4), sticky="w")
        id_var   = tk.StringVar()
        id_entry = tk.Entry(root, textvariable=id_var, width=16, **style_ent)
        id_entry.grid(row=0, column=1, padx=14, pady=(14, 4))
        id_entry.focus()

        tk.Label(root, text="Chu kỳ phát (giây):", **style_lbl).grid(row=1, column=0, padx=14, pady=4, sticky="w")
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

    color_masks = {}
    for name, ranges in HSV_RANGES.items():
        m = np.zeros((h, w), np.uint8)
        for lo, hi in ranges:
            m = cv2.bitwise_or(m, cv2.inRange(hsv, np.array(lo), np.array(hi)))
        color_masks[name] = m
    # Tìm connected components RIÊNG cho từng màu (không gộp mask trước) — nếu
    # 2 máy bay khác màu đứng sát/dính pixel nhau (thường gặp ở cụm gần tâm),
    # xử lý trên mask gộp sẽ biến chúng thành 1 component và mất máy bay thiểu số.
    # Xử lý riêng từng màu đảm bảo mỗi máy bay luôn được tính, bất kể máy bay
    # màu khác đứng sát bên cạnh.
    kernel       = np.ones((5, 5), np.uint8)
    kernel_noise = np.ones((2, 2), np.uint8)
    raw = []
    for color_name, m in color_masks.items():
        m = cv2.bitwise_and(m, mask_radar)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel_noise)  # loai dom nhieu 1px do nen/nhieu tin hieu USB capture
        m = cv2.dilate(m, kernel, iterations=1)   # nối pixel cùng màu bị đứt đoạn do ảnh mờ
        m = cv2.bitwise_and(m, mask_radar)        # giữ trong vòng radar

        _, lbl, stats, centroids = cv2.connectedComponentsWithStats(m, 8)
        for i in range(1, int(stats.shape[0])):
            x0, y0, bw, bh, area = stats[i]
            if area < 1 or area > 5000:    # rất thoáng — user sẽ click xác nhận
                continue
            bx = int(centroids[i][0]); by = int(centroids[i][1])
            dx = (bx - CX) * KM_PX;   dy = (CY - by) * KM_PX
            dist = float(np.sqrt(dx**2 + dy**2))
            if dist > 305:
                continue
            bearing = compass_bearing(dx, dy)
            raw.append((bx, by, int(area), dist, bearing, color_name, dx, dy))

    # Gộp các blip CÙNG MÀU quá gần nhau (< 18px) thành một — đây là các mảnh vỡ
    # của cùng một icon bị đứt đoạn do ảnh mờ/nén. Khác màu = khác máy bay,
    # KHÔNG được gộp dù đứng sát nhau (vd. nhiều mục tiêu tụ gần tâm radar).
    raw.sort(key=lambda x: x[3])
    merged, used = [], set()
    for i, b in enumerate(raw):
        if i in used:
            continue
        grp = [b]
        for j, b2 in enumerate(raw):
            if j <= i or j in used:
                continue
            if b[5] == b2[5] and abs(b[0]-b2[0]) < 18 and abs(b[1]-b2[1]) < 18:
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

    def _predict_pixel_pos(self, tid, t_sec):
        """Vị trí (px,py) dự đoán của track tại thời điểm t_sec, ngoại suy theo
        vận tốc hiện tại. Nếu chưa đủ điểm để tính vận tốc → trả về vị trí cuối
        cùng đã biết (giống hành vi cũ)."""
        hist = self.tracks[tid]["history"]
        last_t, _, _, lx, ly = hist[-1]
        vx, vy = self.get_velocity(tid)   # km/s (dx,dy) — None nếu chưa đủ điểm
        if vx is None:
            return lx, ly
        dt = t_sec - last_t
        return lx + (vx / KM_PX) * dt, ly - (vy / KM_PX) * dt

    def update(self, frame_idx, blips):
        """Cập nhật track đã có. Blip không khớp track nào → trả về dưới dạng candidates.

        Ghép blip↔track bằng thuật toán "global nearest-pair": xét TẤT CẢ cặp
        (blip, track) hợp lệ, sắp theo khoảng cách tăng dần rồi gán tham lam từ
        gần nhất trở đi — thay vì lặp theo thứ tự blip và lấy match gần nhất
        CHO TỪNG blip riêng lẻ (cách cũ). Cách cũ có thể để một đốm nhiễu đứng
        gần "cướp" track của mục tiêu thật nếu nó được xử lý trước, khiến track
        đã khoá bị nhảy sang vị trí sai. Ưu tiên khớp CÙNG MÀU trước (vòng 1),
        chỉ chấp nhận khác màu ở vòng dự phòng với bán kính hẹp hơn — đề phòng
        màu bị đọc sai do ảnh nén/mờ chứ không phải nhiễu ăn nhầm.
        """
        t_sec  = frame_idx / self.fps
        active = {tid: info for tid, info in self.tracks.items()
                  if frame_idx - info["last_frame"] <= MAX_LOST and info["history"]}
        self.tracks = active

        pred = {tid: self._predict_pixel_pos(tid, t_sec) for tid in active}

        def gen_pairs(same_color, gate):
            pairs = []
            for bi, blip in enumerate(blips):
                bx, by, area, dist, bear, color, dx, dy = blip
                for tid, info in active.items():
                    if (info["color"] == color) != same_color:
                        continue
                    px, py = pred[tid]
                    d = np.sqrt((bx - px) ** 2 + (by - py) ** 2)
                    if d < gate:
                        pairs.append((d, bi, tid))
            pairs.sort(key=lambda p: p[0])
            return pairs

        matched_bi  = set()
        matched_tid = set()
        blip_track  = {}
        for _d, bi, tid in gen_pairs(True, ASSOC_DIST) + gen_pairs(False, ASSOC_DIST * 0.5):
            if bi in matched_bi or tid in matched_tid:
                continue
            matched_bi.add(bi); matched_tid.add(tid)
            blip_track[bi] = tid

        unmatched = []
        for bi, blip in enumerate(blips):
            bx, by, area, dist, bear, color, dx, dy = blip
            tid = blip_track.get(bi)
            if tid is not None:
                info = self.tracks[tid]
                if frame_idx - info["last_frame"] > DETECT_EVERY * 3:
                    info["was_lost"] = True
                info["history"].append((t_sec, dx, dy, bx, by))
                if len(info["history"]) > 200:
                    info["history"] = info["history"][-200:]
                info["last_frame"] = frame_idx
                info["color"]      = color
            else:
                unmatched.append(blip)  # chờ user xác nhận

        return unmatched

    def confirm_candidate(self, frame_idx, bx, by, color, dx, dy, auto=False):
        """Xác nhận blip chờ thành track mới. `auto=True` khi track được tạo tự
        động bởi Phát tự động/chậm (auto_confirm_nearby) chứ không phải do
        người dùng bấm chọn thủ công — dùng để phân biệt lúc dọn dẹp/lọc."""
        t_sec = frame_idx / self.fps
        tid   = self._new_anon()
        self.tracks[tid] = {
            "history":     [(t_sec, dx, dy, bx, by)],
            "color":       color,
            "last_frame":  frame_idx,
            "spoken_once": False,
            "was_lost":    False,
            "auto":        auto,
        }
        print(f"[CONFIRM] {tid} ({color}) @ px({bx},{by})" + (" [auto]" if auto else ""), flush=True)
        return tid

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
def draw_frame(canvas, frame_idx, tm, mx=0, my=0, source_label=""):
    hovered_tid  = None

    for tid, info in tm.tracks.items():
        if frame_idx - info["last_frame"] > DETECT_EVERY * 3:
            continue
        hist  = info["history"]
        color = COLOR_MAP.get(info["color"], UNKNOWN_COL)
        if not hist:
            continue
        _, xkm, ykm, px_last, py_last = hist[-1]

        tail = hist[-TAIL_LEN:]
        for k in range(1, len(tail)):
            alpha = k / len(tail)
            c = tuple(int(v * alpha * 0.7) for v in color)
            cv2.line(canvas, (tail[k-1][3], tail[k-1][4]), (tail[k][3], tail[k][4]), c, 1)

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

        cv2.circle(canvas, (px_last, py_last), 9, color, 2)
        cv2.line(canvas, (px_last-5, py_last), (px_last+5, py_last), color, 1)
        cv2.line(canvas, (px_last, py_last-5), (px_last, py_last+5), color, 1)

        if (mx-px_last)**2 + (my-py_last)**2 <= HOVER_RADIUS**2:
            hovered_tid = tid

    if hovered_tid and hovered_tid in tm.tracks:
        draw_tooltip(canvas, hovered_tid, tm.tracks[hovered_tid], mx, my)

    n_active = sum(1 for tid, info in tm.tracks.items()
                   if frame_idx - info["last_frame"] <= DETECT_EVERY * 3
                   and not tid.startswith("?"))
    bar   = (f"  frame={frame_idx}   {n_active} muc tieu   Nguon: {source_label}"
             f"   [Trai] phat   [Shift+Trai] bam muc tieu   [Delete] xoa muc tieu da chon"
             f"   [Phai] ID/hua   [Q/Esc] thoat")
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 22), (0, 0, 0), -1)
    cv2.putText(canvas, bar, (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,220,220), 1)

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

    # Nut PHAT TU DONG CHAM — ben trai nut nhanh
    sbx2 = bx1 - 4;  sbx1 = sbx2 - _BTN_AUTO_W
    sbtn_bg  = (0, 90, 140)   if _global_auto_slow_active else (38, 38, 38)
    sbtn_bdr = (0, 170, 255)  if _global_auto_slow_active else (90, 90, 90)
    sbtn_txt = "|| DUNG CHAM" if _global_auto_slow_active else ">  PHAT CHAM"
    cv2.rectangle(canvas, (sbx1, by1), (sbx2, by2), sbtn_bg,  -1)
    cv2.rectangle(canvas, (sbx1, by1), (sbx2, by2), sbtn_bdr,  1)
    cv2.putText(canvas, sbtn_txt, (sbx1 + 7, by2 - 5),
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
_HTML_PATH = os.path.join(_BASE_DIR, "live_tracks.html")
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
    _p = os.path.join(_BASE_DIR, "live_tracks.json")
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
# CHUYỂN TỌA ĐỘ CLICK → FRAME SPACE (chỉ có 1 màn output CV2, không có cửa sổ nguồn)
# ══════════════════════════════════════════════════════════════════════════════
def click_to_frame(sx, sy, fs_mon, frame_shape):
    fh, fw = frame_shape[:2]
    fl, ft = fs_mon["left"], fs_mon["top"]
    fw_d,  fh_d = fs_mon["width"], fs_mon["height"]
    if fl <= sx < fl + fw_d and ft <= sy < ft + fh_d:
        return int((sx - fl) * fw / fw_d), int((sy - ft) * fh / fh_d)
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
def _persist_calibration_to_file(cx, cy, r):
    """Ghi CX/CY/R_300KM moi nhat vao chinh file nay, de lan chay sau tu dong dung."""
    path = os.path.abspath(__file__)
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        src = re.sub(r"^CX, CY\s*=.*$", f"CX, CY   = {cx}, {cy}", src, count=1, flags=re.MULTILINE)
        src = re.sub(r"^R_300KM\s*=.*$", f"R_300KM  = {r}", src, count=1, flags=re.MULTILINE)
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
        print(f"[CALIB] Da ghi vao file: {path}")
    except Exception as e:
        print(f"[CALIB] Loi ghi file calibration: {e}")

def calibrate_radar_center(frame, mon):
    """
    Hiển thị frame để user chỉnh tâm radar và bán kính 300km.
    S = lưu & cập nhật CX/CY/R_300KM/KM_PX, đồng thời ghi thẳng vào file này
    (radar_live_capture.py) để lần chạy sau tự dùng giá trị mới nhất.
    Q/Esc = huỷ (giữ nguyên).
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
        cv2.circle(img, (cxd, cyd), rd, (0, 180, 255), 2)
        lx = cxd + int(rd * 0.707);  ly = cyd - int(rd * 0.707)
        if 0 < lx < dw - 60 and 4 < ly < dh:
            cv2.putText(img, "300km", (lx+4, ly-4), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,180,255), 2)
        cv2.line(img, (0, cyd), (dw, cyd), (0, 255, 255), 1)
        cv2.line(img, (cxd, 0), (cxd, dh), (0, 255, 255), 1)
        cv2.circle(img, (cxd, cyd),  6, (0, 255, 255), -1)
        cv2.circle(img, (cxd, cyd), 14, (0, 255, 255),  2)
        mode_str = "[CHINH TAM]" if _mode[0] == 0 else "[CHINH BAN KINH]"
        label = f"CX={_cx[0]} CY={_cy[0]}  R={_r[0]}px  {km_px:.4f}km/px  {mode_str}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(img, (6, 6), (14+tw, 16+th), (0,0,0), -1)
        cv2.putText(img, label, (10, 10+th), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,255,255), 1)
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
            _persist_calibration_to_file(CX, CY, R_300KM)
            break
        elif key in (ord('q'), 27):
            print("[CALIB] Huy — giu nguyen toa do cu.")
            break
        elif key == 9:               _mode[0] = 1 - _mode[0]   # Tab
        elif key in (82, ord('w')):  _cy[0] -= 1                # len
        elif key in (84, ord('x')):  _cy[0] += 1                # xuong
        elif key in (81, ord('a')):  _cx[0] -= 1                # trai
        elif key in (83, ord('d')):  _cx[0] += 1                # phai
        elif key in (ord('+'), ord('=')):  _r[0] += 1
        elif key == ord('-'):              _r[0] = max(10, _r[0] - 1)

    cv2.destroyWindow(WIN_CAL)

# ══════════════════════════════════════════════════════════════════════════════
# CHẠY PIPELINE RADAR TỪ THIẾT BỊ VIDEO CAPTURE (HDMI/USB)
# ══════════════════════════════════════════════════════════════════════════════
def run_radar_from_capture(device_index, device_label):
    cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"[LOI] Khong mo duoc thiet bi #{device_index} ({device_label})")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAPTURE_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_H)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap_fps = cap.get(cv2.CAP_PROP_FPS)
    if not cap_fps or cap_fps <= 1 or cap_fps > 120:
        cap_fps = float(TARGET_FPS)
    print(f"[OK] Nguon: {device_label}  (index={device_index})  {actual_w}x{actual_h}  ~{cap_fps:.0f}fps bao cao")

    ok, first = cap.read()
    if not ok or first is None:
        print("[LOI] Khong doc duoc frame dau tien tu thiet bi.")
        cap.release()
        return

    sct      = mss.MSS()
    monitors = sct.monitors[1:]
    if len(monitors) >= 2:
        fs_mon, tbl_mon = monitors[0], monitors[1]
    else:
        fs_mon = tbl_mon = monitors[0]

    print(f"[MONITOR] Output fullscreen: {fs_mon['width']}x{fs_mon['height']} @({fs_mon['left']},{fs_mon['top']})")
    print(f"[MONITOR] Bang thong tin:    {tbl_mon['width']}x{tbl_mon['height']} @({tbl_mon['left']},{tbl_mon['top']})")

    # ── Xác định tâm radar ───────────────────────────────────────────────────
    _root = tk.Tk()
    _root.withdraw()
    _root.attributes("-topmost", True)
    _keep = tkinter.messagebox.askyesno(
        "Tâm Radar",
        f"Giữ nguyên tâm radar?\n\n"
        f"CX = {CX}   CY = {CY}\n"
        f"R_300KM = {R_300KM} px   ({KM_PX:.4f} km/px)\n\n"
        f"Nguồn mới ({device_label}) có thể có bố cục màn hình khác — "
        f"nếu không chắc, bấm Không để chỉnh lại.",
        parent=_root,
    )
    _root.destroy()

    if not _keep:
        calibrate_radar_center(first, fs_mon)

    # Audio
    try:
        pygame.mixer.init()
        print("[AUDIO] OK")
    except Exception as e:
        print(f"[AUDIO] Lỗi: {e}")
    threading.Thread(target=_audio_worker, daemon=True).start()

    # pynput
    m_listener = pmouse.Listener(on_click=_on_mouse_click)
    m_listener.start()
    k_listener = pkeyboard.Listener(on_press=_on_key_press, on_release=_on_key_release)
    k_listener.start()
    print("[INPUT] Mouse + keyboard listener OK")

    FAKE_FPS          = float(TARGET_FPS)
    tm                = TrackManager(FAKE_FPS)
    table_img         = build_table(tm, 0)
    table_scroll_y = 0
    _selected_tid  = [None]    # tid được chọn gần nhất bằng chuột trái (để xoá bằng Delete)
    cv_mouse   = [0, 0]

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

    frame_idx = 0
    FRAME_DT  = 1.0 / TARGET_FPS

    print(f"[OK] Chạy {TARGET_FPS} fps.  Chuột TRÁI: phát   Shift+Trái: bám mục tiêu   "
          f"Delete: xoá mục tiêu đã chọn   Chuột PHẢI: ID/hẹn giờ   Q/Esc: thoát\n")

    try:
        while True:
            t0 = time.perf_counter()

            ok, frame = cap.read()
            if not ok or frame is None:
                print("\r[CANH BAO] Mat tin hieu tu thiet bi, dang thu lai...", end="", flush=True)
                time.sleep(0.2)
                continue

            if frame_idx % DETECT_EVERY == 0:
                blips = detect_blips(frame)
                unmatched = tm.update(frame_idx, blips)
                auto_confirm_nearby(tm, frame_idx, unmatched)
                table_img = build_table(tm, frame_idx)
                write_live_outputs(tm, frame_idx, FAKE_FPS)
                print(f"\r  frame={frame_idx}  tracks={len(tm.tracks)}", end="", flush=True)

            # ── Chuột TRÁI: button / Shift+Trái bám mục tiêu / Trái phát track ─
            while not _left_click_q.empty():
                sx, sy = _left_click_q.get_nowait()
                coords = click_to_frame(sx, sy, fs_mon, frame.shape)
                if coords:
                    lx, ly = coords
                    fw_f = frame.shape[1]
                    if fw_f - _BTN_AUTO_W - 4 <= lx <= fw_f - 4 and 0 <= ly <= _BTN_AUTO_H:
                        toggle_global_auto(tm)
                    elif fw_f - 2*_BTN_AUTO_W - 8 <= lx <= fw_f - _BTN_AUTO_W - 8 and 0 <= ly <= _BTN_AUTO_H:
                        toggle_global_auto_slow(tm)
                    elif _shift_state["held"]:
                        # Shift + Trái: bám mục tiêu tại điểm màu bất kỳ (xác nhận thành track)
                        color = classify_color_at(frame, lx, ly)
                        if color:
                            nearby = find_nearest_blip(lx, ly, tm, frame_idx,
                                                        radius_mult=SHIFT_CLICK_SKIP_RADIUS / HOVER_RADIUS)
                            if nearby is None:
                                dx = (lx - CX) * KM_PX;  dy = (CY - ly) * KM_PX
                                _selected_tid[0] = tm.confirm_candidate(frame_idx, lx, ly, color, dx, dy)
                            else:
                                _selected_tid[0] = nearby
                    else:
                        hit = find_nearest_blip(lx, ly, tm, frame_idx)
                        if hit:
                            speak_target(hit, tm.tracks[hit])
                            _selected_tid[0] = hit

            # ── Chuột PHẢI: dialog ID + auto-speak ───────────────────────────
            while not _right_click_q.empty():
                sx, sy = _right_click_q.get_nowait()
                coords = click_to_frame(sx, sy, fs_mon, frame.shape)
                if coords:
                    hit = find_nearest_blip(coords[0], coords[1], tm, frame_idx)
                    if hit:
                        show_target_dialog(hit, tm)

            # ── Delete: xoá track đang được chọn (chọn bằng chuột trái gần nhất) ─
            while not _delete_key_q.empty():
                _delete_key_q.get_nowait()
                _tid = _selected_tid[0]
                if _tid and _tid in tm.tracks:
                    stop_auto_speak(_tid)
                    del tm.tracks[_tid]
                    print(f"\n[XOA] {_tid}", flush=True)
                    _selected_tid[0] = None

            # ── Vẽ ───────────────────────────────────────────────────────────
            canvas = frame.copy()
            fh, fw = frame.shape[:2]
            frame_mx = int(cv_mouse[0] * fw / max(fs_mon["width"],  1))
            frame_my = int(cv_mouse[1] * fh / max(fs_mon["height"], 1))
            frame_mx = max(0, min(frame_mx, fw - 1))
            frame_my = max(0, min(frame_my, fh - 1))
            draw_frame(canvas, frame_idx, tm, frame_mx, frame_my,
                       source_label=device_label)

            display = cv2.resize(canvas, (fs_mon["width"], fs_mon["height"]),
                                 interpolation=cv2.INTER_LINEAR)
            cv2.imshow("Radar Live", display)

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

            elapsed = time.perf_counter() - t0
            if elapsed < FRAME_DT:
                time.sleep(FRAME_DT - elapsed)

    except KeyboardInterrupt:
        pass
    finally:
        m_listener.stop()
        k_listener.stop()
        cap.release()
        sct.close()
        _global_auto_stop.set()
        _global_auto_slow_stop.set()
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
        with open(os.path.join(_BASE_DIR, "tracks.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"Tracks: {sorted(out.keys())}")

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("=== RADAR LIVE — NGUON TU THIET BI NGOAI (HDMI/COM/...) ===\n")

    while True:
        scan = scan_ports()
        choice = show_port_selection_dialog(scan)

        if choice is None:
            print("[HUY] Nguoi dung thoat.")
            return

        if choice["type"] == "refresh":
            continue

        if choice["type"] == "other":
            _root = tk.Tk(); _root.withdraw(); _root.attributes("-topmost", True)
            tkinter.messagebox.showinfo(
                "Không thể dùng làm nguồn",
                "Thiết bị này không phải nguồn video/hình ảnh nên không thể dùng trực tiếp "
                "cho radar tracking.\n\nVui lòng chọn thiết bị trong mục VIDEO hoặc COM.",
                parent=_root)
            _root.destroy()
            continue

        if choice["type"] == "serial":
            run_serial_monitor(choice)
            continue  # quay lai menu chon sau khi dong serial monitor

        if choice["type"] == "video":
            run_radar_from_capture(choice["index"], choice["name"])
            return

if __name__ == "__main__":
    # Per-monitor DPI aware: mọi Win32 API (mss, pynput) dùng physical pixels
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass
    main()
