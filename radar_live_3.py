"""
Radar Live v3 — fork từ radar_live_2.py, chuyển nguồn từ thiết bị capture
(HDMI/USB) sang PHÁT LẠI FILE VIDEO đã ghi sẵn (mặc định `phong_to.mp4`),
đồng thời xử lý vấn đề video có PHÓNG TO/THU NHỎ (zoom) giữa chừng — thứ
không xảy ra với capture card (luôn giữ nguyên khung hình nguồn).

── Vì sao cần bản riêng ────────────────────────────────────────────────────
`phong_to.mp4` quay lại một phần mềm radar ATC thật (không phải màn hình PPI
mô phỏng như thucte.mp4). Phần mềm này cho phép người vận hành đổi tầm quan
sát ("Km" dropdown: 360 Km → 90 Km ...). Khi đổi tầm: TÂM RADAR (vị trí icon
trạm) đứng YÊN trên màn hình, chỉ có TỈ LỆ km/px thay đổi. Nếu dùng KM_PX cố
định như radar_live_2, mọi cự ly tính ra sau khi zoom sẽ sai theo đúng tỉ lệ
phóng đại.

── Cách xử lý: MỐC THAM CHIẾU LÀ 1 VÙNG (không phải 1 điểm) ───────────────
Đã thử qua 2 hướng trước khi chốt cách này:
  • Mốc = 1 điểm click nhỏ + OpenCV tracker/dò theo tia cố định từ tâm — mẫu
    quá nhỏ nên cực nhạy sai số scale (~1% lệch đã tụt điểm khớp mạnh); làm
    mờ ảnh để mẫu bớt nhạy thì lại dễ khớp NHẦM sang vạch lưới vòng cự ly
    khác — nền phần mềm toàn đường tròn/tia lặp lại đều quanh ĐÚNG cái tâm
    dùng làm mốc quy chiếu, nên các vạch lưới sau khi làm mờ trông na ná
    nhau (đã tái hiện lỗi này bằng test thực tế trên video).
  • Đọc chữ "Tầm quan sát" (Km) phần mềm tự in cạnh nút zoom — chính xác
    tuyệt đối nhưng CHỈ dùng được với ĐÚNG phần mềm ATC này (có ô chữ cố
    định); nguồn khác như capture card USB/HDMI không có ô chữ đó, hoặc chữ
    dễ vỡ nét do nén/nhiễu tín hiệu capture, không tổng quát được.

Cách hiện tại tổng quát cho mọi nguồn: người dùng giữ CHUỘT GIỮA và KÉO ra
1 VÙNG (không phải 1 điểm) quanh 1 chi tiết cố định có hình dạng rõ (bờ
biển, đảo, chữ nhãn...) — không phải máy bay. Vùng càng lớn/càng nhiều chi
tiết càng cho đỉnh khớp rõ ràng, ngược hẳn với mẫu điểm nhỏ trước đây. Vẫn
khai thác đúng cấu trúc bài toán — zoom là phép co giãn đều quanh tâm cố
định nên hướng từ tâm đến mốc không đổi, chỉ khoảng cách co giãn theo 1 hệ
số k — nhưng thêm 2 lớp phòng vệ để không lặp lại lỗi khớp-nhầm-vào-lưới:
  1. Ưu tiên dò QUANH ước lượng k gần nhất trước (zoom thật đổi dần qua
     nhiều chu kỳ, không nhảy cóc); chỉ mở rộng dò TOÀN DẢI khi vùng lân cận
     không cho điểm khớp đủ tốt (mới đặt mốc / mất dấu).
  2. Đo "độ chênh lệch" giữa đỉnh khớp tốt nhất và đỉnh tốt-nhì cách xa —
     nếu 2 đỉnh quá gần điểm nhau (dấu hiệu trùng chu kỳ lưới) thì KHÔNG
     chốt tỉ lệ mới, giữ tỉ lệ cũ, thay vì tự tin chọn nhầm như trước.
Xem chi tiết thuật toán trong khối docstring ngay trên `set_reference_region()`.
Toàn bộ hệ thống (detect_blips, vẽ track, tooltip, bảng, TTS) chỉ đọc biến
KM_PX toàn cục tại thời điểm cần dùng nên tự động ăn theo giá trị mới —
không cần sửa gì thêm ở các hàm đó.

Vì tâm KHÔNG dịch chuyển nhưng TỈ LỆ có thể đổi bất cứ lúc nào, các hàm vẽ
KHÔNG được dùng lại toạ độ pixel đã lưu trong lịch sử track (toạ độ đó chỉ
đúng tại tỉ lệ của khung hình lúc phát hiện). Thay vào đó mọi nơi cần vẽ đều
quy đổi lại pixel HIỆN TẠI từ khoảng cách km đã lưu (hàm `to_px()`), y hệt
cách một GIS/bản đồ luôn vẽ lại từ toạ độ thật mỗi khi đổi mức zoom.

── Nhiễu màu ở phần mềm ATC (khác thucte.mp4) ──────────────────────────────
Phần mềm này vẽ thêm nhiều lớp hoạ đồ tĩnh (đường viền khu vực bám sát nét
đứt màu xanh lá, đường bay/lưới bay chấm chấm màu vàng/cam...) trùng tông
màu với icon mục tiêu, gây rất nhiều "blip" giả nếu dùng nguyên detect_blips
cũ. Đã đo thực tế trên khung hình của phong_to.mp4: GREEN 393 blob/khung,
YELLOW 149, CYAN 128 (mục tiêu thật chỉ vài chục). Ba lớp lọc được thêm vào
`detect_blips()` / vòng lặp chính, xếp theo thứ tự xử lý:
  1. Lọc HÌNH DẠNG (kích thước hộp bao + độ đặc "solidity" = area/(bw*bh)):
     loại các đoạn nét đứt dài/mảnh của đường viền khu vực bám sát — icon
     mục tiêu luôn là khối nhỏ, đặc; một đoạn nét đứt thì dài, rỗng.
  2. Lọc MẬT ĐỘ: một chấm thuộc đường bay chấm chấm luôn có nhiều "hàng
     xóm" cùng màu đứng sát nhau dọc theo đường; icon mục tiêu thật luôn
     đứng riêng lẻ. Loại các chấm có > 1 hàng xóm cùng màu trong bán kính
     gần — hai lớp lọc 1+2 làm giảm ngay từ khung đầu tiên (không cần đợi
     tích luỹ), tránh việc "Phát tự động" (auto-scan) tạo hàng loạt track
     giả trước khi lớp lọc 3 kịp phát huy tác dụng.
  3. Lọc NỀN TĨNH theo thời gian (`StaticNoiseFilter`): CHỈ áp dụng cho các
     blip CHƯA khớp track nào (candidate, đưa vào auto-scan) — không đụng
     tới việc khớp blip↔track đã xác nhận, để mục tiêu đứng yên hợp lệ
     (như "yellow square" bất động từng gặp ở thucte.mp4) không bao giờ bị
     rớt track chỉ vì đứng yên lâu. Ô toạ độ nào liên tục là "candidate mới"
     nhiều chu kỳ liền (không phải track thật, vì track thật đã được khớp
     và không còn nằm trong danh sách candidate) thì bị coi là nền tĩnh và
     loại khỏi candidate list. Tự động reset khi tỉ lệ km/px vừa đổi đáng kể
     (video vừa zoom) vì lúc đó vị trí pixel của mọi lớp hoạ đồ tĩnh đã dịch
     chuyển, dữ liệu nền cũ không còn đúng.

Phần còn lại (TTS, bảng mục tiêu, live_tracks.json/html, calibration tâm
radar, thuật toán ghép blip↔track "global nearest-pair" của radar_live_2)
giữ nguyên logic, chỉ đổi chỗ cần thiết để hoạt động đúng khi KM_PX đổi.
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
from PIL import Image, ImageDraw, ImageFont
from pynput import keyboard as pkeyboard
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
# Radar calibration — chỉnh lại bằng bước "calibrate" khi chạy (nguồn ngoài đổi tuỳ máy)
CX, CY   = 772, 522
R_300KM  = 414
KM_PX    = 300.0 / R_300KM

# Pipeline
DETECT_EVERY = 5          # detect blip mỗi N frame
MAX_LOST     = 150        # frame (~5s @30fps) — track bị xoá hẳn nếu mất dấu lâu hơn
                           # mức này. Tăng từ mức cũ (60 = 2s) vì mục tiêu thật đôi khi
                           # mất khớp vài chu kỳ liền khi bay theo đội hình sát nhau
                           # (xem filter_dense_candidates) hoặc trong lúc video zoom
                           # đang chuyển tiếp (KM_PX/mốc chưa kịp ổn định) — cần nhiều
                           # thời gian hơn 2s để không xoá nhầm mục tiêu vẫn còn đó.
VISIBLE_LOST = DETECT_EVERY * 8   # frame — track không được vẽ/liệt kê nếu mất khớp
                                   # lâu hơn mức này (nhưng vẫn giữ trong tm.tracks tới
                                   # khi chạm MAX_LOST) — tăng từ DETECT_EVERY*3 (0.5s)
                                   # để giảm nhấp nháy "biến mất" khi chỉ mất khớp thoáng qua.
ASSOC_DIST   = 30
TAIL_LEN     = 25
PRED_SEC     = 30
HOVER_RADIUS  = 22
GLOBAL_RADIUS = 150      # km — bán kính cho "Phát tự động"
_BTN_AUTO_W   = 158
_BTN_AUTO_H   = 22

# Shift + chuột trái để bám mục tiêu tại điểm màu bất kỳ (thay cho double-click)
SHIFT_CLICK_SKIP_RADIUS = 25   # px — nếu đã có track trong bán kính này thì bỏ qua, không tạo mới

DEFAULT_VIDEO = "phong_to.mp4"

# Thư mục gốc của app: cạnh file .exe khi đã đóng gói (PyInstaller), cạnh file
# .py khi chạy trực tiếp bằng Python.
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

# ──────────────────────────────────────────────────────────────────────────────
# QUY ĐỔI KM → PIXEL HIỆN TẠI (tâm cố định, tỉ lệ có thể đổi bất cứ lúc nào)
# ──────────────────────────────────────────────────────────────────────────────
def to_px(dx_km, dy_km):
    return int(round(CX + dx_km / KM_PX)), int(round(CY - dy_km / KM_PX))

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
# và classify_color_at() (quét 1 điểm khi shift-click). V=80 (thay vì 130) để bắt
# được màu bị tối do ảnh mờ/nén.
#
# RED nới rộng hơn các màu khác (S: 100→80, hue: 0-12/168-180 → 0-14/166-180)
# — đo thực tế trên phong_to.mp4 (frame mẫu): icon RED nhỏ hay có rất ít pixel
# thật sự lọt ngưỡng cũ (có icon chỉ 5px trong 1 vùng mẫu 9x9, toàn bộ nằm sát
# mép 168), và RED là màu DUY NHẤT phải bọc qua điểm gãy 0°/180° của bánh xe
# hue (2 dải rời nhau) nên dễ bị lệch hẳn ra ngoài CẢ HAI dải chỉ với 1 chút
# trôi màu do nén/mờ — trong khi 4 màu còn lại chỉ có 1 dải liền, còn dư biên
# đáng kể. User báo track RED hay mất bám hơn các màu khác, khớp với phân
# tích này.
HSV_RANGES = {
    "RED":     [((0,  80, 80),(14, 255,255)), ((166,80, 80),(180,255,255))],
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
# GLOBAL KEYBOARD HOOK (pynput) — chỉ dùng cho phím Delete (xoá mục tiêu chọn).
# Chuột dùng cv2.setMouseCallback ngay trên cửa sổ video (không cần hook toàn
# cục như bản capture-card, vì đây là cửa sổ cục bộ phát lại file, luôn có
# focus khi thao tác).
# ══════════════════════════════════════════════════════════════════════════════
_delete_key_q = queue.Queue()

def _on_key_press(key):
    if key == pkeyboard.Key.delete:
        _delete_key_q.put(True)

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
    clips.extend(list(f"{bear:03d}"))
    clips.extend(list(f"{dist:03d}"))
    clips.append("khong")
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

# True  = "tự do quét" — lúc bật CHƯA có mục tiêu nào được chọn thủ công
#         (Shift+trái) → tự động dò + đọc mọi blip trong 150km.
# False = "chỉ mục tiêu đã chọn" — lúc bật ĐÃ có ít nhất 1 mục tiêu chọn thủ công.
_auto_scan_mode = False

def _start_auto_session(tm):
    global _auto_scan_mode
    _auto_scan_mode = not any(not info.get("auto", False) for info in tm.tracks.values())

def _finish_auto_session(tm):
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
                continue
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
    """Khi Phát tự động/chậm đang bật VÀ đang ở chế độ tự-do-quét: tự động
    xác nhận (tạo track, auto=True) cho mọi blip trong bán kính GLOBAL_RADIUS.
    `unmatched_blips` đã được StaticNoiseFilter lọc bỏ nền tĩnh (đường bay
    chấm chấm...) trước khi tới đây — xem docstring đầu file."""
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
BLIP_MAX_DIM        = 24    # px — cạnh tối đa hộp bao icon mục tiêu hợp lệ
BLIP_MIN_SOLIDITY   = 0.28  # area/(bw*bh) tối thiểu — loại nét đứt mảnh/dài
BLIP_ARTIFACT_DIM   = 8     # px — hộp bao ≤ mức này COI CHỪNG là 1 dấu chấm
BLIP_ARTIFACT_SOLID = 0.9   # ... nếu ĐỒNG THỜI đặc gần như tuyệt đối (hình
                             # vuông nhỏ hoàn hảo) — xem giải thích dưới.
BLIP_DENSITY_RADIUS = 35    # px — bán kính đếm "hàng xóm" cùng màu
BLIP_DENSITY_MAX_NB = 1     # > ngưỡng này hàng xóm cùng màu gần đó trong 1 khung
                             # hình => nghi là chuỗi chấm nền (đường bay chấm
                             # chấm). CHỈ dùng để lọc CANDIDATE (xem
                             # filter_dense_candidates() bên dưới) — KHÔNG áp
                             # dụng cho detect_blips() vì máy bay thật cũng hay
                             # bay theo đội hình sát nhau (đã đo thực tế trên
                             # phong_to.mp4: có khung 8/17 icon RED thật trong
                             # 1 cụm bị lọc nhầm nếu áp dụng ở đây — mục tiêu đã
                             # xác nhận nằm trong cụm sẽ rớt track dù vẫn hiện
                             # rõ trên màn, đúng lỗi "tự biến mất" gặp phải).

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

    kernel       = np.ones((5, 5), np.uint8)
    kernel_noise = np.ones((2, 2), np.uint8)
    raw = []
    for color_name, m in color_masks.items():
        m = cv2.bitwise_and(m, mask_radar)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel_noise)  # loai dom nhieu 1px
        m = cv2.dilate(m, kernel, iterations=1)                # noi pixel dut doan
        m = cv2.bitwise_and(m, mask_radar)

        _, lbl, stats, centroids = cv2.connectedComponentsWithStats(m, 8)

        # ── Lọc hình dạng: loại nét đứt dài/mảnh của đường viền khu vực bám
        # sát (chỉ xuất hiện ở UI phong_to.mp4, không có ở nguồn cũ) ─────────
        shaped = []
        for i in range(1, int(stats.shape[0])):
            x0, y0, bw, bh, area = stats[i]
            if area < 1 or area > 5000:
                continue
            if bw > BLIP_MAX_DIM or bh > BLIP_MAX_DIM:
                continue
            sol = area / max(bw * bh, 1)
            if sol < BLIP_MIN_SOLIDITY:
                continue
            # ── Loại "dấu chấm nền" (chấm trên đường viền khu vực/đường bay
            # đứt nét): sau OPEN(2x2) rồi DILATE(5x5), 1 chấm nền nhỏ (~2x2
            # px thô) LUÔN nở thành đúng 1 hình vuông ~6x6px, đặc GẦN TUYỆT
            # ĐỐI (solidity xấp xỉ 1.0) — đây là kích thước TỐI THIỂU về mặt
            # lý thuyết mà pipeline này có thể tạo ra, khác hẳn icon mục tiêu
            # thật (hình mũi tên/tam giác có "mũi"/"cánh" bất đối xứng, luôn
            # to hơn rõ rệt và/hoặc kém đặc hơn nhiều). Đã đo thực tế trên
            # phong_to.mp4 (frame mẫu, màu GREEN): 67 blob qua lọc cũ, trong
            # đó ~40 blob khớp CHÍNH XÁC chữ ký này (6x6, area=36, sol=1.00)
            # nằm dày đặc dọc đường viền khu vực xanh lá — không phải máy
            # bay (chỉ có ~7-8 icon thật trong cùng khung). Đây chính là
            # nguồn nhiễu khiến track màu GREEN (và ở mức nhẹ hơn, RED) hay
            # bị "cướp"/lệch khi khớp track, vì lớp lọc mật độ/nền tĩnh hiện
            # tại CHỈ áp dụng cho candidate chưa khớp, không áp dụng khi
            # khớp track đã xác nhận (xem "Lọc nhiễu 3 lớp" — cố ý, để không
            # lặp lại bug "mục tiêu tự biến mất"). Lọc ở đây AN TOÀN hơn vì
            # dựa vào CHỮ KÝ HÌNH DẠNG cố định của pipeline, không phải mật
            # độ xung quanh — không loại nhầm đội hình thật bay sát nhau.
            if bw <= BLIP_ARTIFACT_DIM and bh <= BLIP_ARTIFACT_DIM and sol >= BLIP_ARTIFACT_SOLID:
                continue
            shaped.append((int(centroids[i][0]), int(centroids[i][1]), int(area)))

        for bx, by, area in shaped:
            dx = (bx - CX) * KM_PX;   dy = (CY - by) * KM_PX
            dist = float(np.sqrt(dx**2 + dy**2))
            if dist > 305:
                continue
            bearing = compass_bearing(dx, dy)
            raw.append((bx, by, area, dist, bearing, color_name, dx, dy))

    # Gộp các blip CÙNG MÀU quá gần nhau (< 18px) — mảnh vỡ của cùng 1 icon
    # bị đứt đoạn do ảnh mờ/nén. Khác màu KHÔNG được gộp dù đứng sát nhau.
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

def filter_dense_candidates(unmatched_blips):
    """Lọc mật độ: loại các CANDIDATE (blip chưa khớp track nào) có > 1 hàng
    xóm cùng màu trong bán kính gần — dấu hiệu chuỗi chấm trên đường bay
    chấm chấm. CHỈ áp dụng cho candidate (auto-scan), KHÔNG áp dụng cho việc
    khớp blip↔track đã xác nhận (xem giải thích ở BLIP_DENSITY_MAX_NB phía
    trên `detect_blips()`) — nên máy bay thật bay theo đội hình sát nhau vẫn
    được các track ĐÃ XÁC NHẬN bám bình thường, chỉ ảnh hưởng tới việc có tự
    động tạo track MỚI cho candidate đó hay không."""
    n = len(unmatched_blips)
    keep = [True] * n
    for i in range(n):
        bxi, byi = unmatched_blips[i][0], unmatched_blips[i][1]
        ci = unmatched_blips[i][5]
        nb = 0
        for j in range(n):
            if i == j:
                continue
            if unmatched_blips[j][5] != ci:
                continue
            bxj, byj = unmatched_blips[j][0], unmatched_blips[j][1]
            if (bxi - bxj) ** 2 + (byi - byj) ** 2 <= BLIP_DENSITY_RADIUS ** 2:
                nb += 1
                if nb > BLIP_DENSITY_MAX_NB:
                    keep[i] = False
                    break
    return [b for b, k in zip(unmatched_blips, keep) if k]

# ══════════════════════════════════════════════════════════════════════════════
# LỌC NHIỄU NỀN TĨNH (đường bay chấm chấm, lưới bản đồ còn sót lại sau lọc
# hình dạng/mật độ ở trên) — CHỈ áp dụng cho blip CHƯA khớp track nào
# (candidate cho auto-scan). Việc khớp blip↔track đã xác nhận trong
# TrackManager.update() luôn dùng danh sách blip THÔ, chưa lọc bước này, nên
# mục tiêu đứng yên hợp lệ không bao giờ bị rớt track chỉ vì đứng yên lâu.
# ══════════════════════════════════════════════════════════════════════════════
STATIC_BIN_PX     = 4    # gộp toạ độ theo ô lưới N px để chịu rung/nén nhẹ
STATIC_HIT_LIMIT  = 15   # số chu kỳ detect liên tiếp là "candidate mới" tại
                          # cùng 1 ô mới bị coi là nền tĩnh (track thật một khi
                          # đã được xác nhận sẽ không còn là candidate nữa nên
                          # không bao giờ tự đạt ngưỡng này)
STATIC_MISS_RESET = 3    # số chu kỳ vắng mặt liên tiếp thì xoá đếm dồn

class StaticNoiseFilter:
    def __init__(self):
        self.hits = {}          # (color, binx, biny) -> [streak, miss]
        self.static_set = set()

    def reset(self):
        self.hits.clear()
        self.static_set.clear()
        print("\n[LOC-NEN] Reset nen tinh (ty le km/px vua doi do zoom)", flush=True)

    def filter(self, unmatched_blips):
        seen = set()
        out = []
        for blip in unmatched_blips:
            bx, by, area, dist, bear, color, dx, dy = blip
            key = (color, bx // STATIC_BIN_PX, by // STATIC_BIN_PX)
            seen.add(key)
            if key in self.static_set:
                continue
            streak, _miss = self.hits.get(key, (0, 0))
            streak += 1
            self.hits[key] = (streak, 0)
            if streak >= STATIC_HIT_LIMIT:
                self.static_set.add(key)
                continue
            out.append(blip)
        for key in list(self.hits.keys()):
            if key in seen:
                continue
            streak, miss = self.hits[key]
            miss += 1
            if miss > STATIC_MISS_RESET:
                del self.hits[key]
            else:
                self.hits[key] = (streak, miss)
        return out

# ══════════════════════════════════════════════════════════════════════════════
# MỐC THAM CHIẾU TỈ LỆ — chọn 1 VÙNG cố định (không phải điểm) để suy ra
# KM_PX khi video zoom.
#
# Lịch sử: thử điểm-click (mẫu nhỏ 30x30px) trước — thất bại vì mẫu quá nhỏ,
# thường rơi đúng vào 1 nét mảnh (đường bờ biển 1-2px), khớp cực nhạy sai số
# scale (~1% lệch đã tụt điểm khớp mạnh); làm mờ ảnh để mẫu bớt nhạy thì lại
# dễ khớp NHẦM sang vạch lưới vòng cự ly khác — nền phần mềm toàn đường tròn/
# tia lặp lại đều quanh ĐÚNG cái tâm đang dùng làm mốc quy chiếu, nên bị nhoè
# thì các vạch lưới trông na ná nhau. Thử đọc chữ "Tầm quan sát" phần mềm tự
# in — chính xác tuyệt đối nhưng chỉ dùng được cho ĐÚNG phần mềm này (có ô
# chữ cố định); nguồn khác (USB/HDMI capture card) không có chữ đó, hoặc chữ
# có nhưng dễ vỡ nét do nén/nhiễu tín hiệu capture, không đáng tin cậy.
#
# Cách hiện tại: người dùng giữ CHUỘT GIỮA và KÉO ra một VÙNG (không phải 1
# điểm) quanh 1 chi tiết cố định có hình dạng rõ (bờ biển, đảo, chữ nhãn...),
# không phải máy bay. Vùng càng lớn/càng nhiều chi tiết càng cho đỉnh khớp
# rõ ràng, ít bị nhầm — ngược với mẫu điểm nhỏ trước đây. Vẫn khai thác đúng
# cấu trúc bài toán (zoom là phép co giãn đều quanh tâm cố định → hướng từ
# tâm đến mốc không đổi, chỉ khoảng cách co giãn theo 1 hệ số k), nhưng thêm
# 2 lớp phòng vệ để không lặp lại lỗi khớp-nhầm-vào-lưới:
#   1. Ưu tiên dò QUANH ước lượng k gần nhất trước (vì zoom thật đổi dần qua
#      nhiều chu kỳ liên tiếp, không nhảy cóc); chỉ mở rộng dò TOÀN DẢI khi
#      vùng lân cận không cho điểm khớp đủ tốt (mất dấu / mới đặt mốc).
#   2. Đo "độ chênh lệch" giữa đỉnh khớp tốt nhất và đỉnh tốt-nhì (ở hệ số k
#      cách xa, > 8%): nếu 2 đỉnh gần điểm nhau → dấu hiệu mốc không đủ đặc
#      trưng (có thể trùng chu kỳ lưới) → KHÔNG chốt tỉ lệ mới, giữ nguyên
#      tỉ lệ cũ và báo cho người dùng biết, thay vì tự tin chọn nhầm.
#
# ── Mẫu tham chiếu TỰ LÀM MỚI (khắc phục mất bám ở 2 đầu dải zoom) ─────────
# Nếu chỉ giữ mãi ảnh mẫu chụp lúc đặt mốc, video zoom càng xa mức đó (vd đặt
# mốc lúc 90km rồi sau đó xem ở 360km — cách nhau 4 lần) thì vùng mốc trên
# khung hình hiện tại càng ít chi tiết hơn nhiều so với mẫu gốc (hoặc ngược
# lại), so khớp ngày càng khó — đây chính là lý do "mất bám ở mức cuối" của
# dải zoom dù đã sửa hướng resize. Khắc phục: MỖI LẦN khớp đủ tin cậy (điểm
# và độ chênh lệch cao hơn hẳn ngưỡng chấp nhận thường), chụp lại mẫu MỚI
# ngay tại vị trí/độ phân giải hiện tại (`template_k` lưu hệ số k tuyệt đối
# mà mẫu hiện tại tương ứng). Nhờ vậy mẫu luôn "bám sát" tỉ lệ gần nhất vừa
# xác nhận được — mỗi bước zoom chỉ cần so khớp với mẫu của bước NGAY TRƯỚC
# đó (chênh lệch nhỏ), không bao giờ phải so 1 bước nhảy xa từ mẫu chụp rất
# lâu/rất khác tỉ lệ. Vị trí (offset0) và khoảng cách thực (real_km) — 2 hằng
# số vật lý dùng để tính KM_PX cuối cùng — KHÔNG BAO GIỜ đổi, chỉ ảnh mẫu và
# `template_k` (thứ quyết định NHẬN DIỆN được mốc hay không) được làm mới.
# ══════════════════════════════════════════════════════════════════════════════
REF_K_MIN         = 0.05   # he so co gian nho nhat so voi luc dat moc (zoom in manh)
REF_K_MAX         = 20.0   # he so co gian lon nhat so voi luc dat moc (zoom out manh)
REF_LOCAL_SPAN    = 0.25   # do rong (ti le) vung do "quanh uoc luong gan nhat" truoc
REF_LOCAL_SAMPLES = 20
REF_WIDE_SAMPLES  = 50     # so diem do khi phai mo rong toan dai (mat dau/moi dat moc)
REF_FINE_SAMPLES  = 15     # so diem tinh chinh cuc bo quanh dinh tot nhat
REF_MIN_SCORE     = 0.6    # diem khop toi thieu (TM_CCOEFF_NORMED) de xem xet chap nhan
REF_MIN_MARGIN    = 0.12   # chenh lech toi thieu voi dinh tot-nhi (cach > 8% k) de "chac chan"
REF_JUMP_RATIO    = 1.15   # ty le km/px doi > 15% giua 2 lan cap nhat => coi la video vua zoom
REF_REFRESH_SCORE  = 0.8   # diem toi thieu de LAM MOI mau (khac nghiet hon REF_MIN_SCORE)
REF_REFRESH_MARGIN = 0.2   # chenh lech toi thieu de lam moi mau
REF_TEMPLATE_MIN_DIM = 20    # px — khong lam moi neu mau moi se qua nho (mat kha nang phan biet)
REF_TEMPLATE_MAX_DIM = 320   # px — khong lam moi neu mau moi se qua lon (ton kem + de dinh nham)

# ── Ty le km/px "thuong gap" — do truc tiep tren phong_to.mp4 bang thuoc ti
# le co san cua phan mem (bracket co do dai pixel CO DINH 147px, chi doi nhan
# so; do qua 101 mau rai deu ca video, khong lech 1px nao):
# 360 Km (nhan "100km") -> 0.6803 km/px, 90 Km (nhan "25km") -> 0.1701 km/px.
# 180 Km (nhan "50km")  -> 0.3401 km/px — phat hien SAU: doan 180Km chi ton
# tai ~27 frame (~0.9s, frame ~7648-7675 trong phong_to.mp4) giua 2 lan doi
# 360->90, nen lan quet 101 mau (buoc 100 frame) ban dau bo sot, phai quet
# lai rieng doan nay khi user bao van lech o muc 180Km. Dung nhu 1 "diem
# neo" de tang do chinh xac khi ket qua do moc lien tuc roi vao GAN 1 trong
# 3 muc nay — KHONG thay the co che moc (van la fallback cho moi truong
# hop/muc zoom khac chua do duoc). Dung sai co gian (8%) de khong bo lo do
# nhieu cua phep do moc — 3 muc nay cach nhau dung 2 lan lien tiep (khong
# phai 4 lan nhu truoc) nen it du dia hon, nhung van du xa de phan biet.
KNOWN_KM_PX     = [0.6803, 0.3401, 0.1701]
KNOWN_KM_PX_TOL = 0.08

def _snap_known_km_px(value):
    for k in KNOWN_KM_PX:
        if abs(value / k - 1.0) < KNOWN_KM_PX_TOL:
            return k
    return value

_ref = {"active": False, "template": None, "template_k": 1.0, "offset0": None,
        "real_km": None, "k_est": 1.0, "last_score": 0.0, "last_margin": 0.0,
        "manual": False, "via_known": False}

REF_MANUAL_STEP = 1.03   # he so nhan/chia moi lan bam phim chinh tay ty le

def nudge_km_px(factor):
    """Chỉnh tay KM_PX theo hệ số `factor` (vd 1.03 hoặc 1/1.03) — dùng khi
    mốc tự động khớp sai/không chắc chắn. Một khi đã chỉnh tay, HỆ THỐNG TỰ
    ĐỘNG (`update_scale_from_reference`) sẽ NGỪNG ghi đè KM_PX cho tới khi
    người dùng đặt lại mốc mới (`set_reference_region` sẽ tắt cờ này) — tránh
    tình trạng vừa chỉnh tay xong, chu kỳ dò tự động kế tiếp lại ghi đè về
    giá trị (có thể vẫn sai) mà nó tự tìm được."""
    global KM_PX
    KM_PX = max(KM_PX * factor, 1e-6)
    _ref["manual"] = True
    print(f"\n[CHINH TAY] KM_PX={KM_PX:.4f}  (tu dong da TAT — dat moc moi de bat lai)", flush=True)

def set_reference_region(frame, x0, y0, x1, y1):
    """Đặt mốc tham chiếu là VÙNG (x0,y0)-(x1,y1) trên frame hiện tại — nên
    chọn 1 chi tiết CỐ ĐỊNH có hình dạng rõ (bờ biển, đảo, chữ nhãn...), càng
    nhiều chi tiết càng khớp chắc chắn, tránh chọn mảng trơn/chỉ có lưới."""
    global _ref
    x0, x1 = sorted((int(x0), int(x1)))
    y0, y1 = sorted((int(y0), int(y1)))
    if x1 - x0 < 12 or y1 - y0 < 12:
        print("\n[MOC] Vung qua nho, keo vung lon hon (it nhat ~12x12px).", flush=True)
        return False
    cx_sel, cy_sel = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    dist_px = float(np.hypot(cx_sel - CX, cy_sel - CY))
    if dist_px < 20:
        print("\n[MOC] Vung qua gan tam, chon vung xa tam hon.", flush=True)
        return False
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    tmpl = gray[y0:y1, x0:x1].copy()
    if float(tmpl.std()) < 8.0:
        print("\n[MOC] CANH BAO: vung chon it chi tiet (gan nhu dong mau det) — de khop "
              "nham, nen chon vung co net/hinh dang ro (bo bien, dao, chu...).", flush=True)
    _ref = {
        "active": True, "template": tmpl, "template_k": 1.0,
        "offset0": (cx_sel - CX, cy_sel - CY),
        "real_km": dist_px * KM_PX, "k_est": 1.0, "last_score": 1.0, "last_margin": 1.0,
        "manual": False, "via_known": False,
    }
    print(f"\n[MOC] Da dat moc vung ({x0},{y0})-({x1},{y1})  tam vung cach tam "
          f"{dist_px:.0f}px = {_ref['real_km']:.1f}km  (ty le hien tai {KM_PX:.4f} km/px)",
          flush=True)
    return True

def _ref_score_at_k(gray, k):
    """Trả về (score, cx, cy) khớp mẫu tại hệ số co giãn TUYỆT ĐỐI k (so với
    lúc đặt mốc — dùng để tính VỊ TRÍ, luôn theo `offset0` cố định), hoặc
    None nếu vùng ảnh tương ứng nằm ngoài khung hình.

    Mẫu hiện tại (`_ref["template"]`) có thể đã được LÀM MỚI ở một tỉ lệ
    khác k=1 (xem `template_k`), nên độ phân giải cần so khớp dùng hệ số
    TƯƠNG ĐỐI `rel_k = k / template_k` — chỉ hạ độ phân giải (resize
    xuống), KHÔNG BAO GIỜ phóng to (upscale) ảnh để so khớp: phóng to không
    tạo ra chi tiết thật, chỉ nội suy mờ, làm giảm điểm khớp giả tạo. Nếu
    vùng cắt hiện tại (theo `rel_k`) chi tiết hơn mẫu (rel_k>=1, mẫu cũ hơn/
    xa hơn) → hạ vùng cắt xuống bằng mẫu; ngược lại (rel_k<1) → hạ mẫu xuống
    bằng vùng cắt."""
    ox0, oy0 = _ref["offset0"]
    cx, cy = CX + ox0 * k, CY + oy0 * k
    tmpl = _ref["template"]
    th0, tw0 = tmpl.shape[:2]
    rel_k = k / _ref["template_k"]
    half_w, half_h = (tw0 / 2.0) * rel_k, (th0 / 2.0) * rel_k
    x0, y0 = int(round(cx - half_w)), int(round(cy - half_h))
    x1, y1 = int(round(cx + half_w)), int(round(cy + half_h))
    h, w = gray.shape[:2]
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h or x1 - x0 < 4 or y1 - y0 < 4:
        return None
    crop = gray[y0:y1, x0:x1]
    if rel_k >= 1.0:
        cmp_crop = cv2.resize(crop, (tw0, th0), interpolation=cv2.INTER_AREA)
        cmp_tmpl = tmpl
    else:
        ch, cw = crop.shape[:2]
        cmp_crop = crop
        cmp_tmpl = cv2.resize(tmpl, (cw, ch), interpolation=cv2.INTER_AREA)
    score = float(cv2.matchTemplate(cmp_crop, cmp_tmpl, cv2.TM_CCOEFF_NORMED)[0, 0])
    return score, cx, cy

def _ref_scan(gray, ks):
    out = []
    for k in ks:
        r = _ref_score_at_k(gray, k)
        if r is not None:
            out.append((r[0], k))
    return out

def _ref_search_and_refine(gray, ks_initial):
    """Dò thô theo `ks_initial` rồi tinh chỉnh dần quanh đỉnh tốt nhất qua
    nhiều vòng SIẾT HẸP DẦN (±8% → ±2%). Cần tinh chỉnh nhiều vòng vì đỉnh
    khớp có thể rất HẸP (mẫu ít chi tiết/gần như 1 nét mảnh) — dò thô 1 lần
    dễ bỏ lỡ hẳn đỉnh thật (điểm dò thô gần nhất vẫn có thể rơi ngoài đỉnh
    hẹp đó), nên phải neo dần từng bước thay vì chỉ tinh chỉnh 1 lần duy nhất
    sau khi đã lỡ mở rộng sang dò toàn dải. Trả về (best_score, best_k, tất
    cả điểm đã dò được — dùng để tính "độ chắc chắn" so với đỉnh tốt-nhì)."""
    scored = _ref_scan(gray, ks_initial)
    if not scored:
        return -2.0, None, scored
    best_score, best_k = max(scored, key=lambda s: s[0])
    for span, n in ((0.08, REF_FINE_SAMPLES), (0.02, REF_FINE_SAMPLES)):
        fine_ks = np.linspace(best_k * (1 - span), best_k * (1 + span), n)
        fine_ks = fine_ks[(fine_ks >= REF_K_MIN) & (fine_ks <= REF_K_MAX)]
        fine_scored = _ref_scan(gray, fine_ks)
        if fine_scored:
            fb_score, fb_k = max(fine_scored, key=lambda s: s[0])
            if fb_score > best_score:
                best_score, best_k = fb_score, fb_k
            scored += fine_scored
    return best_score, best_k, scored

# Diem toi thieu / do vuot troi rieng cho "ung vien da biet" (KNOWN_KM_PX) —
# THAP hon REF_MIN_SCORE/REF_MIN_MARGIN vi zoom THAT (phan mem VE LAI khung
# hinh o ty le moi — khac line-width/khu rang cua/co the ca muc chi tiet du
# lieu vector — khong don thuan resize nhu test tong hop bang warpAffine)
# chi dat diem khop ~0.15-0.35 tai DUNG ty le, khong bao gio vuot noi 0.6.
# Da do truc tiep tren phong_to.mp4 qua 2 lan chuyen zoom that (90<->360Km),
# 3 vung moc khac nhau: diem tai dung k luon nam trong khoang nay, dai dong
# thoi dò lien tuc toan dai KHONG BAO GIO tim duoc diem cao hon o bat ky k
# nao khac — nen dung REF_MIN_SCORE binh thuong se KHONG BAO GIO nhan dien
# duoc zoom that, "mat bam vinh vien" sau moi lan zoom. Bu lai bang cach so
# sanh CHI trong so vai gia tri da biet truoc (it ung vien hon han so dò
# lien tuc => de phan biet dung/sai hon du diem tuyet doi thap).
KNOWN_CANDIDATE_MIN_SCORE = 0.15
KNOWN_CANDIDATE_MARGIN    = 0.08

def _ref_try_known_candidates(gray, dist_px_capture):
    """Ep k ung voi TUNG gia tri trong KNOWN_KM_PX (thay vi do lien tuc mo),
    tinh chinh nho quanh k ly thuyet cua moi gia tri roi lay diem tot nhat
    cho tung ung vien. Dung khi do lien tuc da that bai (diem qua thap).
    Tra ve DANH SACH (score,k,km_px) da sap xep giam dan theo score — noi
    goi tu quyet dinh chap nhan bang cach so sanh GIUA CAC UNG VIEN NAY VOI
    NHAU (khong so voi diem do lien tuc: da do thuc te tren phong_to.mp4 —
    do lien tuc mo toan dai co the tinh co trung 1 k SAI cho diem cao HON
    ca ung vien dung, vi no do qua hang tram k bat ky trong khi ung vien chi
    co vai gia tri biet truoc — so bang-nhau se khong cong bang)."""
    real_km = _ref["real_km"]
    results = []
    for kmpx in KNOWN_KM_PX:
        if kmpx <= 0:
            continue
        k_theory = real_km / (dist_px_capture * kmpx)
        if not (REF_K_MIN <= k_theory <= REF_K_MAX):
            continue
        fine_ks = np.linspace(k_theory * 0.97, k_theory * 1.03, 9)
        fine_ks = fine_ks[(fine_ks >= REF_K_MIN) & (fine_ks <= REF_K_MAX)]
        if len(fine_ks) == 0:
            continue
        s, k, _ = _ref_search_and_refine(gray, fine_ks)
        if s is not None:
            results.append((s, k, kmpx))
    results.sort(key=lambda r: r[0], reverse=True)
    return results

def update_scale_from_reference(frame):
    """Dò lại vùng mốc dọc theo TIA CỐ ĐỊNH từ tâm (xem giải thích ở khối
    docstring phía trên), ưu tiên tìm quanh ước lượng gần nhất trước (dò +
    tinh chỉnh ngay tại chỗ — không đợi thất bại rồi mới tinh chỉnh, vì đỉnh
    hẹp có thể bị bỏ lỡ hoàn toàn nếu chỉ tinh chỉnh SAU KHI đã nhảy sang dò
    toàn dải thô hơn), chỉ mở rộng dò TOÀN DẢI khi lân cận không đủ tốt. Chỉ
    chấp nhận kết quả khi đủ "chắc chắn" (đỉnh khớp tốt nhất tách biệt rõ
    khỏi đỉnh tốt-nhì). Cập nhật KM_PX toàn cục, trả về True nếu tỉ lệ vừa
    đổi ĐÁNG KỂ (video vừa zoom) — nơi gọi cần reset StaticNoiseFilter."""
    global KM_PX
    if not _ref["active"] or _ref["manual"]:
        return False
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    k_est = _ref["k_est"]
    local_ks = np.linspace(k_est * (1 - REF_LOCAL_SPAN), k_est * (1 + REF_LOCAL_SPAN), REF_LOCAL_SAMPLES)
    local_ks = local_ks[(local_ks >= REF_K_MIN) & (local_ks <= REF_K_MAX)]
    best_score, best_k, scored = _ref_search_and_refine(gray, local_ks)

    if best_k is None or best_score < REF_MIN_SCORE:
        wide_ks = np.geomspace(REF_K_MIN, REF_K_MAX, REF_WIDE_SAMPLES)
        wide_score, wide_k, wide_scored = _ref_search_and_refine(gray, wide_ks)
        scored += wide_scored
        if wide_k is not None and wide_score > best_score:
            best_score, best_k = wide_score, wide_k

    if best_k is None:
        _ref["last_score"] = 0.0
        _ref["via_known"]  = False
        print("\r[MOC] Dang tim lai moc...                                   ", end="", flush=True)
        return False

    # Do "do chac chan": tim dinh tot-nhi CACH XA dinh chinh (>8% k) — neu 2
    # dinh qua gan diem nhau, mau co the trung chu ky luoi, khong dang tin.
    others = [s for s in scored if abs(s[1] - best_k) / best_k > 0.08]
    second_score = max((s[0] for s in others), default=-2.0)
    margin = best_score - second_score

    _ref["last_score"]  = best_score
    _ref["last_margin"] = margin
    _ref["via_known"]   = False

    if best_score < REF_MIN_SCORE or margin < REF_MIN_MARGIN:
        # Do lien tuc that bai (thuong xay ra dung luc zoom THAT vua doi —
        # xem giai thich o KNOWN_CANDIDATE_MIN_SCORE): thu rieng cac ty le
        # "thuong gap" truoc khi bo cuoc. QUAN TRONG: quyet dinh chap nhan
        # bang cach so ung vien tot nhat VOI UNG VIEN TOT-NHI TRONG CHINH
        # DANH SACH DA BIET (khong so voi diem do lien tuc o tren) — da do
        # thuc te: do lien tuc mo toan dai co the tinh co cho diem CAO HON
        # ca ung vien dung (vi no thu hang tram k bat ky, de trung mot cho
        # "ngau nhien giong"), nen so truc tiep voi no la khap khieng.
        dist_px_capture = float(np.hypot(*_ref["offset0"]))
        kk_results = _ref_try_known_candidates(gray, dist_px_capture)
        kk_best  = kk_results[0]      if len(kk_results) >= 1 else None
        kk_second_score = kk_results[1][0] if len(kk_results) >= 2 else -2.0
        if kk_best is not None and kk_best[0] >= KNOWN_CANDIDATE_MIN_SCORE and \
           kk_best[0] - kk_second_score >= KNOWN_CANDIDATE_MARGIN:
            kk_score, kk_k, kk_kmpx = kk_best
            print(f"\r[MOC] Nhan dien ty le thuong gap ({kk_kmpx:.4f} km/px, "
                  f"diem={kk_score:.2f} chenh ung vien con lai={kk_score - kk_second_score:.2f})"
                  f"          ", end="", flush=True)
            _ref["last_score"]  = kk_score
            _ref["last_margin"] = kk_score - kk_second_score
            _ref["via_known"]   = True
            best_score, best_k = kk_score, kk_k
        else:
            print(f"\r[MOC] Khong chac chan (diem={best_score:.2f} chenh={margin:.2f}) "
                  f"— giu ty le cu...          ", end="", flush=True)
            return False

    _ref["k_est"] = float(best_k)

    # Làm mới mẫu tham chiếu nếu đủ tin cậy (ngưỡng khắt khe hơn ngưỡng chấp
    # nhận thường) — giữ mẫu luôn "bám sát" tỉ lệ gần nhất, để lần dò sau chỉ
    # cần bước nhảy nhỏ thay vì phải so với mẫu chụp từ rất lâu/rất khác tỉ
    # lệ (xem docstring khối trên). Bỏ qua nếu mẫu mới sẽ quá nhỏ (hết chi
    # tiết để phân biệt) hoặc quá lớn (tốn kém, dễ dính vào vật thể chuyển
    # động gần đó).
    if best_score >= REF_REFRESH_SCORE and margin >= REF_REFRESH_MARGIN:
        rel_k = best_k / _ref["template_k"]
        th0, tw0 = _ref["template"].shape[:2]
        new_w, new_h = tw0 * rel_k, th0 * rel_k
        if REF_TEMPLATE_MIN_DIM <= new_w <= REF_TEMPLATE_MAX_DIM and \
           REF_TEMPLATE_MIN_DIM <= new_h <= REF_TEMPLATE_MAX_DIM:
            ox0, oy0 = _ref["offset0"]
            ncx, ncy = CX + ox0 * best_k, CY + oy0 * best_k
            nx0, ny0 = int(round(ncx - new_w / 2)), int(round(ncy - new_h / 2))
            nx1, ny1 = int(round(ncx + new_w / 2)), int(round(ncy + new_h / 2))
            h, w = gray.shape[:2]
            if 0 <= nx0 and 0 <= ny0 and nx1 <= w and ny1 <= h and nx1 - nx0 >= 4 and ny1 - ny0 >= 4:
                _ref["template"]   = gray[ny0:ny1, nx0:nx1].copy()
                _ref["template_k"] = float(best_k)

    dist_px_capture = float(np.hypot(*_ref["offset0"]))
    new_dist_px = dist_px_capture * best_k
    if new_dist_px < 5 or KM_PX <= 0:
        return False
    new_km_px = _snap_known_km_px(_ref["real_km"] / new_dist_px)
    ratio_change = new_km_px / KM_PX
    KM_PX = new_km_px
    return not (1 / REF_JUMP_RATIO < ratio_change < REF_JUMP_RATIO)

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
        """Vị trí (px,py) dự đoán của track tại t_sec. Dự đoán hoàn toàn
        trong KM-SPACE (dx,dy,vx,vy đều là km/km-s) rồi mới quy đổi ra pixel
        bằng to_px() ở bước cuối — để luôn đúng dù KM_PX vừa đổi do zoom."""
        hist = self.tracks[tid]["history"]
        last_t, ldx, ldy, _, _ = hist[-1]
        vx, vy = self.get_velocity(tid)
        if vx is None:
            return to_px(ldx, ldy)
        dt = t_sec - last_t
        return to_px(ldx + vx * dt, ldy + vy * dt)

    def update(self, frame_idx, blips):
        """Cập nhật track đã có. Blip không khớp track nào → trả về dưới dạng candidates.

        Ghép blip↔track bằng thuật toán "global nearest-pair": xét TẤT CẢ cặp
        (blip, track) hợp lệ, sắp theo khoảng cách tăng dần rồi gán tham lam từ
        gần nhất trở đi. Ưu tiên khớp CÙNG MÀU trước (vòng 1), chỉ chấp nhận
        khác màu ở vòng dự phòng với bán kính hẹp hơn.
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
                    if not same_color and frame_idx - info["last_frame"] <= DETECT_EVERY:
                        # Chi cho phep khop KHAC MAU khi track da truot it nhat 1
                        # chu ky day du (chua khop lai duoc o chu ky truoc) — 1 lan
                        # mat blip thoang qua (nhieu/che khuat 1 khung) rat pho
                        # bien, khong nen coi la ly do de "cuop" sang muc tieu
                        # khac mau ben canh ngay lap tuc.
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
            bx, by, area, dist, bear, _color, dx, dy = blip
            tid = blip_track.get(bi)
            if tid is not None:
                info = self.tracks[tid]
                if frame_idx - info["last_frame"] > VISIBLE_LOST:
                    info["was_lost"] = True
                info["history"].append((t_sec, dx, dy, bx, by))
                if len(info["history"]) > 200:
                    info["history"] = info["history"][-200:]
                info["last_frame"] = frame_idx
                # KHONG ghi de info["color"] — mau la DINH DANH da khoa luc xac
                # nhan track, khong doi theo mau blip khop duoc moi chu ky. Truoc
                # day ghi de o day khien 1 lan khop-nham-khac-mau (vong du phong
                # o gen_pairs) lam track DOI MAU VINH VIEN tu do ve sau (vi chu
                # ky sau lai dung mau MOI de xet "cung mau" tiep) — dung la
                # trieu chung "dang bam nhung nhay sang ben canh thanh mau khac"
                # user bao lai.
            else:
                unmatched.append(blip)  # chờ user xác nhận / lọc nền tĩnh

        return unmatched

    def confirm_candidate(self, frame_idx, bx, by, color, dx, dy, auto=False):
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
        x0, y0 = hist[-1][1], hist[-1][2]
        xp = x0 + vx * t_ahead_sec
        yp = y0 + vy * t_ahead_sec
        pxp, pyp = to_px(xp, yp)
        return xp, yp, pxp, pyp

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
def draw_frame(canvas, frame_idx, tm, mx=0, my=0, source_label="", paused=False, drag_rect=None):
    hovered_tid  = None

    for tid, info in tm.tracks.items():
        if frame_idx - info["last_frame"] > VISIBLE_LOST:
            continue
        hist  = info["history"]
        color = COLOR_MAP.get(info["color"], UNKNOWN_COL)
        if not hist:
            continue
        _, xkm, ykm, _, _ = hist[-1]
        px_last, py_last = to_px(xkm, ykm)

        # Đuôi vệt bay: quy đổi lại pixel HIỆN TẠI từ (dx,dy) km đã lưu ở mỗi
        # điểm — KHÔNG dùng toạ độ pixel cũ (chỉ đúng tại tỉ lệ lúc phát hiện).
        tail = hist[-TAIL_LEN:]
        tail_px = [to_px(t[1], t[2]) for t in tail]
        for k in range(1, len(tail_px)):
            alpha = k / len(tail_px)
            c = tuple(int(v * alpha * 0.7) for v in color)
            cv2.line(canvas, tail_px[k-1], tail_px[k], c, 1)

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

    # ── Mốc tham chiếu tỉ lệ (vùng) ─────────────────────────────────────────
    if drag_rect:
        cv2.rectangle(canvas, drag_rect[0], drag_rect[1], (0, 255, 255), 2)
    if _ref["active"] and _ref["offset0"] is not None:
        # Vẽ TRỰC TIẾP vị trí mốc hiện tại hệ thống đang tính (theo k_est) —
        # để thấy bằng mắt khoảng cách tới tâm có dãn/co đúng tỉ lệ hay
        # không, thay vì chỉ đọc số trên thanh trạng thái.
        ox0, oy0 = _ref["offset0"]
        mk = _ref["k_est"]
        mcx = int(round(CX + ox0 * mk));  mcy = int(round(CY + oy0 * mk))
        mcol = (0, 255, 180) if (_ref["via_known"] or
                                  (_ref["last_score"] >= REF_MIN_SCORE and
                                   _ref["last_margin"] >= REF_MIN_MARGIN)) else (0, 120, 255)
        cv2.line(canvas, (CX, CY), (mcx, mcy), mcol, 1, cv2.LINE_AA)
        cv2.drawMarker(canvas, (mcx, mcy), mcol, cv2.MARKER_TILTED_CROSS, 22, 2)
        cv2.circle(canvas, (mcx, mcy), 12, mcol, 2)
        mdist_px = float(np.hypot(mcx - CX, mcy - CY))
        cv2.putText(canvas, f"moc k={mk:.2f} d={mdist_px:.0f}px",
                    (mcx + 14, mcy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.42, mcol, 1, cv2.LINE_AA)
    if _ref["manual"]:
        ref_txt = f"[CHINH TAY] KM_PX={KM_PX:.4f}  ( - / = de chinh, dat moc moi de bat tu dong lai)"
        ref_col = (0, 255, 180)
    elif not _ref["active"]:
        ref_txt = "CHUA CO MOC — giu CHUOT GIUA keo chon vung, hoac bam - / = de chinh tay"
        ref_col = (0,120,255)
    elif _ref["via_known"]:
        ref_txt = (f"MOC: {KM_PX:.4f} km/px  (ty le thuong gap, khop {_ref['last_score']*100:.0f}%  "
                   f"vuot do lien tuc {_ref['last_margin']*100:.0f}%)")
        ref_col = (0,200,255)
    elif _ref["last_score"] >= REF_MIN_SCORE and _ref["last_margin"] >= REF_MIN_MARGIN:
        ref_txt = (f"MOC: {KM_PX:.4f} km/px  (khop {_ref['last_score']*100:.0f}%  "
                   f"chenh {_ref['last_margin']*100:.0f}%)")
        ref_col = (0,200,255)
    else:
        ref_txt = (f"MOC: khong chac chan (khop {_ref['last_score']*100:.0f}%  "
                   f"chenh {_ref['last_margin']*100:.0f}%) — km/px cu: {KM_PX:.4f}  "
                   f"[bam - / = de chinh tay]")
        ref_col = (0,80,255)
    cv2.putText(canvas, ref_txt, (8, canvas.shape[0]-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, ref_col, 1, cv2.LINE_AA)

    n_active = sum(1 for tid, info in tm.tracks.items()
                   if frame_idx - info["last_frame"] <= VISIBLE_LOST
                   and not tid.startswith("?"))
    pause_txt = "  [TAM DUNG]" if paused else ""
    bar   = (f"  frame={frame_idx}   {n_active} muc tieu   Nguon: {source_label}{pause_txt}"
             f"   [Trai] phat   [Shift+Trai] bam muc tieu   [Giua] dat moc ty le"
             f"   [Delete] xoa   [Space] tam dung   [Phai] ID/hen   [Q/Esc] thoat")
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 22), (0, 0, 0), -1)
    cv2.putText(canvas, bar, (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0,220,220), 1)

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
              if frame_idx - info["last_frame"] <= VISIBLE_LOST]
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
              if frame_idx - info["last_frame"] <= VISIBLE_LOST]
    active.sort(key=lambda x: (x[0].startswith("?"), x[0]))
    t_sec   = frame_idx / fps
    n_named = sum(1 for t, _ in active if not t.startswith("?"))

    lt = {}
    for tid, info in active:
        if not info["history"]: continue
        _, xkm, ykm, _, _ = info["history"][-1]
        px, py = to_px(xkm, ykm)
        vx, vy = tm.get_velocity(tid)
        spd = round(float(np.sqrt(vx**2+vy**2))*3600, 0) if vx else None
        lt[tid] = {"color": info["color"],
                   "dist_km":  round(float(np.sqrt(xkm**2+ykm**2)), 1),
                   "bearing":  round(compass_bearing(xkm, ykm), 1),
                   "speed_kmh": spd, "pos_px": [px, py],
                   "named": not tid.startswith("?")}
    payload = {"frame": frame_idx, "t_sec": round(t_sec, 2), "km_px": round(KM_PX, 5), "tracks": lt}
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
# HÀM TÌM BLIP GẦN NHẤT TẠI TỌA ĐỘ LOCAL
# ══════════════════════════════════════════════════════════════════════════════
def find_nearest_blip(lx, ly, tm, frame_idx, radius_mult=2.5):
    best_tid = None; best_d = HOVER_RADIUS * radius_mult
    for _tid, _info in tm.tracks.items():
        if frame_idx - _info["last_frame"] > VISIBLE_LOST: continue
        if not _info["history"]: continue
        _, dxk, dyk, _, _ = _info["history"][-1]
        _px, _py = to_px(dxk, dyk)
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
    S = lưu & cập nhật CX/CY/R_300KM/KM_PX, đồng thời ghi thẳng vào file này.
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
# CHẠY PIPELINE RADAR TỪ FILE VIDEO
# ══════════════════════════════════════════════════════════════════════════════
def run_radar_from_video(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[LOI] Khong mo duoc video: {video_path}")
        return
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 1 or fps > 120:
        fps = 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"[OK] Video: {video_path}  fps={fps:.2f}  frames={total_frames}  "
          f"({total_frames/fps/60:.1f} phut)")

    ok, first = cap.read()
    if not ok or first is None:
        print("[LOI] Khong doc duoc khung hinh dau tien.")
        cap.release()
        return
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    try:
        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        screen_h = ctypes.windll.user32.GetSystemMetrics(1)
    except Exception:
        screen_w, screen_h = 1920, 1080
    mon = {"left": 20, "top": 20, "width": screen_w, "height": screen_h}

    fh, fw = first.shape[:2]
    disp_scale = min((screen_w - 40) / max(fw, 1), (screen_h - 120) / max(fh, 1), 1.0)
    disp_w = max(int(fw * disp_scale), 1)
    disp_h = max(int(fh * disp_scale), 1)

    # ── Xác định tâm radar ───────────────────────────────────────────────────
    _root = tk.Tk()
    _root.withdraw()
    _root.attributes("-topmost", True)
    _keep = tkinter.messagebox.askyesno(
        "Tâm Radar",
        f"Giữ nguyên tâm radar?\n\n"
        f"CX = {CX}   CY = {CY}\n"
        f"R_300KM = {R_300KM} px   ({KM_PX:.4f} km/px)\n\n"
        f"Nguồn mới ({os.path.basename(video_path)}) có thể có bố cục khác — "
        f"nếu không chắc, bấm Không để chỉnh lại.",
        parent=_root,
    )
    _root.destroy()

    if not _keep:
        calibrate_radar_center(first, mon)

    _root = tk.Tk(); _root.withdraw(); _root.attributes("-topmost", True)
    tkinter.messagebox.showinfo(
        "Mốc tỉ lệ (zoom)",
        "Video này có thể phóng to/thu nhỏ giữa chừng. Sau khi video bắt đầu "
        "chạy, hãy GIỮ CHUỘT GIỮA và KÉO ra một VÙNG quanh 1 chi tiết CỐ ĐỊNH "
        "(bờ biển, đảo, chữ nhãn...) — không phải máy bay — rồi thả chuột để "
        "xác nhận. Chọn vùng càng lớn/càng nhiều chi tiết rõ càng khớp chắc "
        "chắn; tránh vùng chỉ có nền trơn hoặc chỉ có lưới.\n\n"
        "Nếu định dùng cả 2 chiều phóng to LẪN thu nhỏ: nên chọn mốc cách "
        "tâm một khoảng vừa phải (không quá sát tâm) và đủ lớn — vùng quá "
        "nhỏ/quá gần tâm sẽ chỉ còn vài pixel sau khi thu nhỏ nhiều, không "
        "đủ chi tiết để khớp lại được (giới hạn vật lý, không phải lỗi).\n\n"
        "Hệ thống sẽ tự tính lại tỉ lệ km/px mỗi khi cảnh phóng to/thu nhỏ. "
        "Có thể giữ CHUỘT GIỮA kéo chọn lại bất cứ lúc nào nếu thấy mốc "
        "không chắc chắn (thanh trạng thái dưới màn hình sẽ báo).\n\n"
        "NẾU TỰ ĐỘNG VẪN SAI: bấm phím '-' hoặc '=' để CHỈNH TAY tỉ lệ km/px "
        "trực tiếp (mỗi lần bấm nhích ±3%) — vừa bấm vừa quan sát mục tiêu đã "
        "xác nhận trên màn có khớp đúng vị trí blip thật không. Một khi đã "
        "chỉnh tay, hệ thống tự động sẽ TẮT (không tự ghi đè nữa) cho tới khi "
        "đặt mốc mới.",
        parent=_root)
    _root.destroy()

    # Audio
    try:
        pygame.mixer.init()
        print("[AUDIO] OK")
    except Exception as e:
        print(f"[AUDIO] Lỗi: {e}")
    threading.Thread(target=_audio_worker, daemon=True).start()

    # pynput — chi con dung cho phim Delete
    k_listener = pkeyboard.Listener(on_press=_on_key_press)
    k_listener.start()
    print("[INPUT] Keyboard listener OK (Delete)")

    tm             = TrackManager(fps)
    noise_filter   = StaticNoiseFilter()
    table_img      = build_table(tm, 0)
    table_scroll_y = [0]
    _selected_tid  = [None]
    cv_mouse       = [0, 0]

    _left_click_q  = queue.Queue()
    _right_click_q = queue.Queue()
    _mid_drag      = {"active": False, "p0": None, "p1": None, "pending_rect": None}

    def on_video_mouse(event, x, y, flags, param):
        lx, ly = int(x / disp_scale), int(y / disp_scale)
        cv_mouse[0], cv_mouse[1] = lx, ly
        if event == cv2.EVENT_LBUTTONDOWN:
            _left_click_q.put((lx, ly, bool(flags & cv2.EVENT_FLAG_SHIFTKEY)))
        elif event == cv2.EVENT_RBUTTONDOWN:
            _right_click_q.put((lx, ly))
        elif event == cv2.EVENT_MBUTTONDOWN:
            _mid_drag["active"] = True
            _mid_drag["p0"] = (lx, ly); _mid_drag["p1"] = (lx, ly)
        elif event == cv2.EVENT_MOUSEMOVE and _mid_drag["active"]:
            _mid_drag["p1"] = (lx, ly)
        elif event == cv2.EVENT_MBUTTONUP:
            _mid_drag["active"] = False
            if _mid_drag["p0"] is not None:
                _mid_drag["pending_rect"] = (_mid_drag["p0"], (lx, ly))

    def on_table_scroll(event, x, y, flags, param):
        if event == cv2.EVENT_MOUSEWHEEL:
            step = TABLE_ROW_H * 3
            if flags > 0: table_scroll_y[0] = max(0, table_scroll_y[0] - step)
            else:          table_scroll_y[0] += step

    WIN_MAIN = "Radar Live v3 (video)"
    cv2.namedWindow(WIN_MAIN, cv2.WINDOW_AUTOSIZE)
    cv2.moveWindow(WIN_MAIN, mon["left"], mon["top"])
    cv2.setMouseCallback(WIN_MAIN, on_video_mouse)

    cv2.namedWindow("Bang thong tin", cv2.WINDOW_AUTOSIZE)
    cv2.moveWindow("Bang thong tin", mon["left"] + disp_w + 20, mon["top"])
    cv2.setMouseCallback("Bang thong tin", on_table_scroll)

    frame_idx = 0
    frame     = first
    paused    = [False]
    speed_mult = [1.0]
    FRAME_DT   = 1.0 / fps

    print(f"[OK] Phat {fps:.1f} fps (x{speed_mult[0]:.2f}).  Chuot TRAI: phat   "
          f"Shift+Trai: bam muc tieu   Giu+keo Chuot GIUA: dat moc ty le   Delete: xoa muc tieu   "
          f"Chuot PHAI: ID/hen gio   Space: tam dung   [ ]: toc do   -/=: chinh tay ty le   Q/Esc: thoat\n")

    try:
        while True:
            t0 = time.perf_counter()

            if not paused[0]:
                ok, new_frame = cap.read()
                if not ok or new_frame is None:
                    print("\n[OK] Da phat het video.")
                    break
                frame = new_frame
                frame_idx += 1

            if frame_idx % DETECT_EVERY == 0:
                zoom_changed = update_scale_from_reference(frame)
                if zoom_changed:
                    noise_filter.reset()
                blips = detect_blips(frame)
                unmatched = tm.update(frame_idx, blips)
                unmatched = filter_dense_candidates(unmatched)
                unmatched = noise_filter.filter(unmatched)
                auto_confirm_nearby(tm, frame_idx, unmatched)
                table_img = build_table(tm, frame_idx)
                write_live_outputs(tm, frame_idx, fps)
                print(f"\r  frame={frame_idx}/{total_frames}  t={frame_idx/fps:6.1f}s  "
                      f"tracks={len(tm.tracks):3d}  km/px={KM_PX:.4f}", end="", flush=True)

            # ── Chuột TRÁI: button / Shift+Trái bám mục tiêu / Trái phát track ─
            while not _left_click_q.empty():
                lx, ly, shift_held = _left_click_q.get_nowait()
                fw_f = frame.shape[1]
                if fw_f - _BTN_AUTO_W - 4 <= lx <= fw_f - 4 and 0 <= ly <= _BTN_AUTO_H:
                    toggle_global_auto(tm)
                elif fw_f - 2*_BTN_AUTO_W - 8 <= lx <= fw_f - _BTN_AUTO_W - 8 and 0 <= ly <= _BTN_AUTO_H:
                    toggle_global_auto_slow(tm)
                elif shift_held:
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
                lx, ly = _right_click_q.get_nowait()
                hit = find_nearest_blip(lx, ly, tm, frame_idx)
                if hit:
                    show_target_dialog(hit, tm)

            # ── Chuột GIỮA (giữ + kéo): đặt/đặt lại mốc tham chiếu tỉ lệ ─────
            if _mid_drag["pending_rect"] is not None:
                (rx0, ry0), (rx1, ry1) = _mid_drag["pending_rect"]
                _mid_drag["pending_rect"] = None
                set_reference_region(frame, rx0, ry0, rx1, ry1)

            # ── Delete: xoá track đang được chọn ─────────────────────────────
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
            drag_preview = (_mid_drag["p0"], _mid_drag["p1"]) \
                            if _mid_drag["active"] and _mid_drag["p0"] else None
            draw_frame(canvas, frame_idx, tm, cv_mouse[0], cv_mouse[1],
                       source_label=os.path.basename(video_path), paused=paused[0],
                       drag_rect=drag_preview)

            display = cv2.resize(canvas, (disp_w, disp_h), interpolation=cv2.INTER_LINEAR) \
                      if disp_scale != 1.0 else canvas
            cv2.imshow(WIN_MAIN, display)

            _max_s = max(0, table_img.shape[0] - TABLE_WIN_H)
            table_scroll_y[0] = min(table_scroll_y[0], _max_s)
            _view = table_img[table_scroll_y[0] : table_scroll_y[0] + TABLE_WIN_H]
            if _view.shape[0] < TABLE_WIN_H:
                _pad  = np.zeros((TABLE_WIN_H - _view.shape[0], TABLE_W, 3), np.uint8)
                _view = np.vstack([_view, _pad])
            cv2.imshow("Bang thong tin", _view)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):
                break
            elif key == ord(' '):
                paused[0] = not paused[0]
            elif key == ord('['):
                speed_mult[0] = max(0.25, speed_mult[0] / 2)
                print(f"\n[TOC DO] x{speed_mult[0]:.2f}", flush=True)
            elif key == ord(']'):
                speed_mult[0] = min(8.0, speed_mult[0] * 2)
                print(f"\n[TOC DO] x{speed_mult[0]:.2f}", flush=True)
            elif key == ord('-'):
                nudge_km_px(REF_MANUAL_STEP)      # muc tieu ve GAN tam hon
            elif key == ord('='):
                nudge_km_px(1.0 / REF_MANUAL_STEP)  # muc tieu ve XA tam hon

            elapsed   = time.perf_counter() - t0
            target_dt = FRAME_DT / speed_mult[0]
            if elapsed < target_dt:
                time.sleep(target_dt - elapsed)

    except KeyboardInterrupt:
        pass
    finally:
        k_listener.stop()
        cap.release()
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
    print("=== RADAR LIVE v3 — PHAT LAI VIDEO (ho tro zoom/phong to) ===\n")
    video_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_BASE_DIR, DEFAULT_VIDEO)
    if not os.path.exists(video_path):
        print(f"[LOI] Khong tim thay file video: {video_path}")
        return
    run_radar_from_video(video_path)

if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass
    main()
