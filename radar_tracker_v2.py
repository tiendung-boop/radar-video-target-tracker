"""
radar_tracker_v2.py  — rewrite từ đầu theo pipeline chuẩn
  1. Tiền xử lý     — CLAHE + unsharp mask để tăng tương phản số nhỏ
  2. Detect blip    — YOLOv8 (nếu có model) hoặc color contour (fallback)
  3. Crop + upscale — 3-4× INTER_CUBIC hoặc DNN super-resolution
  4. OCR nhãn       — EasyOCR (tốt hơn Tesseract trên ảnh radar nhiễu)
  5. Tracking       — Hungarian matching + Kalman filter
  6. Output         — video annotated + JSON
"""
import cv2
import numpy as np
import json
import os
import re
from PIL import Image, ImageDraw, ImageFont
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def linear_sum_assignment(cost):
    """Greedy nearest-neighbor matching — scipy-free, đủ tốt cho n < 50 tracks."""
    pairs = sorted(
        [(cost[r, c], r, c)
         for r in range(cost.shape[0])
         for c in range(cost.shape[1])],
    )
    used_r, used_c, row_ind, col_ind = set(), set(), [], []
    for _, r, c in pairs:
        if r not in used_r and c not in used_c:
            row_ind.append(r)
            col_ind.append(c)
            used_r.add(r)
            used_c.add(c)
    return row_ind, col_ind


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
VIDEO_PATH  = r"c:\Users\ygost\radar\thucte.mp4"
OUTPUT_PATH = r"c:\Users\ygost\radar\output_v2.mp4"

# Model YOLOv8 detect blip — để trống → dùng color contour fallback
DETECT_MODEL_PATH = ""

# Radar calibration — KHÔNG thay đổi (set_tam_radar.py)
CX, CY   = 772, 522
R_300KM  = 438
KM_PX    = 300.0 / R_300KM   # ~0.6849 km/px

# Preprocessing
CLAHE_CLIP     = 2.0
CLAHE_GRID     = (8, 8)
UNSHARP_SIGMA  = 3.0
UNSHARP_AMOUNT = 1.5

# Contour blip detection (fallback)
MIN_BLOB_AREA  = 15
MAX_BLOB_AREA  = 2500
MAX_ASPECT     = 8
YOLO_CONF      = 0.45

# OCR
OCR_EVERY      = 5           # chạy detect+OCR mỗi N frames
CROP_PAD       = 55          # px bán kính crop quanh blip
UPSCALE_FACTOR = 3           # upscale INTER_CUBIC trước OCR
# DNN super-resolution — để trống nếu không có file .pb
# Tải model tại: https://github.com/Saafke/EDSR_Tensorflow/tree/master/models
SR_MODEL_PATH  = ""          # e.g. r"c:\...\EDSR_x4.pb"
SR_SCALE       = 4

# Tracking
MAX_LOST_SEC   = 4.0
HUNGARIAN_DIST = 40          # px: ngưỡng ghép blip ↔ track
TAIL_LEN       = 30
PRED_SEC       = 30

# Colors (BGR)
COLOR_MAP = {
    "RED":     (60,  60,  255),
    "GREEN":   (60,  220,  60),
    "YELLOW":  (0,   220, 220),
    "CYAN":    (220, 200,  30),
    "MAGENTA": (220,  60, 220),
}
UNKNOWN_COL = (160, 160, 160)

try:
    _FONT    = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf",   17)
    _FONT_BD = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 17)
except Exception:
    _FONT = _FONT_BD = ImageFont.load_default()

mouse_x, mouse_y = 0, 0
def on_mouse(event, x, y, flags, param):
    global mouse_x, mouse_y
    mouse_x, mouse_y = x, y


# ─────────────────────────────────────────────────────────────────────────────
# KHỞI TẠO MODEL (một lần duy nhất)
# ─────────────────────────────────────────────────────────────────────────────
_detect_model = None
if DETECT_MODEL_PATH and os.path.exists(DETECT_MODEL_PATH):
    from ultralytics import YOLO
    _detect_model = YOLO(DETECT_MODEL_PATH)
    print(f"YOLO detect model: {DETECT_MODEL_PATH}")
else:
    print("Không có YOLO detect model → dùng color contour fallback.")

_sr = None
if SR_MODEL_PATH and os.path.exists(SR_MODEL_PATH):
    _sr = cv2.dnn_superres.DnnSuperResImpl_create()
    _sr.readModel(SR_MODEL_PATH)
    _sr.setModel("edsr", SR_SCALE)
    print(f"Super-resolution model: {SR_MODEL_PATH} (x{SR_SCALE})")


# ─────────────────────────────────────────────────────────────────────────────
# 1. TIỀN XỬ LÝ — CLAHE + UNSHARP MASK
# ─────────────────────────────────────────────────────────────────────────────
_radar_mask = None

def _build_radar_mask(h, w):
    global _radar_mask
    _radar_mask = np.zeros((h, w), np.uint8)
    cv2.circle(_radar_mask, (CX, CY), R_300KM, 255, -1)

def _preprocess_for_ocr(crop):
    """CLAHE + unsharp mask + upscale một crop nhỏ trước khi đưa vào OCR."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop.copy()
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=(4, 4))
    gray = clahe.apply(gray)
    blur = cv2.GaussianBlur(gray, (0, 0), UNSHARP_SIGMA)
    gray = cv2.addWeighted(gray, 1 + UNSHARP_AMOUNT, blur, -UNSHARP_AMOUNT, 0)
    if _sr is not None:
        color = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        upsampled = _sr.upsample(color)
        return cv2.cvtColor(upsampled, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, None, fx=UPSCALE_FACTOR, fy=UPSCALE_FACTOR,
                      interpolation=cv2.INTER_CUBIC)


# ─────────────────────────────────────────────────────────────────────────────
# 2A. SWEEP BEAM EXCLUSION
# ─────────────────────────────────────────────────────────────────────────────
_last_sweep_angle = None

def _make_sweep_mask(frame, h, w):
    g = frame[:, :, 1].astype(np.float32)
    r = frame[:, :, 2].astype(np.float32)
    b = frame[:, :, 0].astype(np.float32)
    beam = ((g > 180) & (g > r * 2.5) & (g > b * 2.5)).astype(np.uint8) * 255
    if _radar_mask is not None:
        beam = cv2.bitwise_and(beam, _radar_mask)
    return cv2.dilate(beam, np.ones((5, 5), np.uint8), iterations=2)

def detect_sweep_angle(frame):
    global _last_sweep_angle
    h, w = frame.shape[:2]
    beam = _make_sweep_mask(frame, h, w)
    if np.sum(beam > 0) < 200:
        return _last_sweep_angle
    lines = cv2.HoughLinesP(beam, 1, np.pi/180,
                            threshold=40, minLineLength=80, maxLineGap=20)
    if lines is None:
        return _last_sweep_angle
    best_len, best_angle = 0, None
    for x1, y1, x2, y2 in lines[:, 0]:
        dx = x2 - x1; dy = y2 - y1
        length = float(np.sqrt(dx**2 + dy**2))
        if length > best_len:
            best_len = length
            best_angle = float(np.degrees(np.arctan2(dx, -dy)) % 360)
    if best_angle is not None:
        _last_sweep_angle = best_angle
    return _last_sweep_angle


# ─────────────────────────────────────────────────────────────────────────────
# 2B. PHÁT HIỆN BLIP
# ─────────────────────────────────────────────────────────────────────────────
_COLOR_HSV = {
    "RED":     [((0,  165, 155), (12, 255, 255)), ((165, 165, 155), (180, 255, 255))],
    "GREEN":   [((50, 185, 175), (80, 255, 255))],
    "YELLOW":  [((22, 155, 175), (36, 255, 255))],
    "CYAN":    [((87, 140, 155), (105, 255, 255))],
    "MAGENTA": [((130, 120, 155), (166, 255, 255))],
}

def _classify_color(frame, cx, cy, r=14):
    h, w = frame.shape[:2]
    x1, x2 = max(0, cx-r), min(w, cx+r)
    y1, y2 = max(0, cy-r), min(h, cy+r)
    patch = frame[y1:y2, x1:x2]
    if patch.size == 0:
        return "?"
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    counts = {}
    for name, rngs in _COLOR_HSV.items():
        m = np.zeros(hsv.shape[:2], np.uint8)
        for lo, hi in rngs:
            m = cv2.bitwise_or(m, cv2.inRange(hsv, lo, hi))
        counts[name] = int(np.sum(m > 0))
    best = max(counts, key=counts.get)
    return best if counts[best] > 12 else "?"

def _geo(bx, by):
    dx = (bx - CX) * KM_PX
    dy = (CY - by) * KM_PX
    dist = float(np.sqrt(dx**2 + dy**2))
    bearing = float(np.degrees(np.arctan2(dx, dy)) % 360)
    return dx, dy, dist, bearing

def _merge_nearby(blips, thresh=22):
    blips = sorted(blips, key=lambda b: b[2], reverse=True)
    merged, used = [], set()
    for i, b in enumerate(blips):
        if i in used:
            continue
        used.add(i)
        merged.append(b)
        for j, b2 in enumerate(blips):
            if j not in used and abs(b[0]-b2[0]) < thresh and abs(b[1]-b2[1]) < thresh:
                used.add(j)
    return merged

def detect_blips_yolo(frame):
    """Dùng YOLO detect model để tìm blip."""
    preds = _detect_model(frame, verbose=False, conf=YOLO_CONF)[0]
    blips = []
    for box in preds.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        bx = int((x1 + x2) / 2)
        by = int((y1 + y2) / 2)
        area = (x2 - x1) * (y2 - y1)
        dx, dy, dist, bearing = _geo(bx, by)
        if dist > 305:
            continue
        color = _classify_color(frame, bx, by)
        blips.append((bx, by, float(area), dist, bearing, color, dx, dy))
    return _merge_nearby(blips)

def detect_blips_color(frame):
    """Fallback: phát hiện blip theo màu HSV + contour."""
    h, w = frame.shape[:2]
    if _radar_mask is None:
        _build_radar_mask(h, w)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    sweep = _make_sweep_mask(frame, h, w)
    sweep_dilated = cv2.dilate(sweep, np.ones((15, 15), np.uint8))
    valid = cv2.bitwise_and(cv2.bitwise_not(sweep_dilated), _radar_mask)

    all_blips = []
    for color_name, color_rngs in _COLOR_HSV.items():
        mask = np.zeros((h, w), np.uint8)
        for lo, hi in color_rngs:
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lo, hi))
        mask = cv2.bitwise_and(mask, valid)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  np.ones((2, 2), np.uint8))
        _, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
        for i in range(1, stats.shape[0]):
            x0, y0, bw_c, bh_c, area = stats[i]
            if area < MIN_BLOB_AREA or area > MAX_BLOB_AREA:
                continue
            if max(bw_c, bh_c) / max(min(bw_c, bh_c), 1) > MAX_ASPECT:
                continue
            bx = int(centroids[i][0])
            by = int(centroids[i][1])
            dx, dy, dist, bearing = _geo(bx, by)
            if dist > 305:
                continue
            all_blips.append((bx, by, float(area), dist, bearing, color_name, dx, dy))

    return _merge_nearby(all_blips)

def detect_blips(frame):
    if _detect_model is not None:
        return detect_blips_yolo(frame)
    return detect_blips_color(frame)


# ─────────────────────────────────────────────────────────────────────────────
# 3 & 4. CROP + UPSCALE + EASYOCR
# ─────────────────────────────────────────────────────────────────────────────
_TESS_CFG = "--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789"

def ocr_near_blip(frame, bx, by):
    """Tìm nhãn số gần blip: crop → CLAHE + unsharp + upscale → pytesseract."""
    h, w = frame.shape[:2]
    GAP, WW, WH = 12, 60, 44
    regions = [
        (bx+GAP,     bx+GAP+WW, by-WH,    by+4),
        (bx-GAP-WW,  bx-GAP,    by-WH,    by+4),
        (bx-WW//2,   bx+WW//2,  by-WH-16, by-12),
        (bx+GAP,     bx+GAP+WW, by-4,     by+WH),
        (bx-GAP-WW,  bx-GAP,    by-4,     by+WH),
    ]
    for x1, x2, y1, y2 in regions:
        x1, x2 = max(0, x1), min(w, x2)
        y1, y2 = max(0, y1), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            continue
        crop = frame[y1:y2, x1:x2]
        if cv2.mean(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))[0] < 20:
            continue
        processed = _preprocess_for_ocr(crop)
        text = pytesseract.image_to_string(processed, config=_TESS_CFG).strip()
        m = re.search(r'\d{3,5}', text)
        if m:
            return m.group(0)
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# 5. KALMAN FILTER — constant-velocity, pixel space
# ─────────────────────────────────────────────────────────────────────────────
class KalmanTrack:
    def __init__(self, px, py, dt=1/30):
        self.dt = dt
        self.x  = np.array([[px], [py], [0.0], [0.0]])
        self.P  = np.eye(4) * 200.0
        q = 0.5
        r = 6.0
        self.Q = np.diag([q, q, q*4, q*4])
        self.R = np.diag([r*r, r*r])
        self.F = np.array([[1,0,dt,0],[0,1,0,dt],[0,0,1,0],[0,0,0,1]], dtype=float)
        self.H = np.array([[1,0,0,0],[0,1,0,0]], dtype=float)

    def predict(self):
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return int(self.x[0,0]), int(self.x[1,0])

    def update(self, px, py):
        z = np.array([[px], [py]], dtype=float)
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P

    def pos_px(self):
        return int(self.x[0,0]), int(self.x[1,0])

    def vel_km_s(self):
        return float(self.x[2,0]) * KM_PX, float(-self.x[3,0]) * KM_PX


# ─────────────────────────────────────────────────────────────────────────────
# 5. TRACK MANAGER — Hungarian matching + Kalman
# ─────────────────────────────────────────────────────────────────────────────
class TrackManager:
    def __init__(self, fps):
        self.fps    = fps
        self.dt     = 1.0 / fps
        self.tracks = {}   # tid → {kf, color, history, last_t, last_frame}
        self._anon  = 0

    def _new_anon(self):
        self._anon += 1
        return f"?{self._anon}"

    def update(self, frame_idx, blips, ocr_results):
        t_sec = frame_idx / self.fps

        # Xóa track lỗi thời
        self.tracks = {
            tid: info for tid, info in self.tracks.items()
            if t_sec - info["last_t"] <= MAX_LOST_SEC
        }

        # Dự đoán vị trí tất cả track
        preds     = {tid: info["kf"].predict() for tid, info in self.tracks.items()}
        track_ids = list(self.tracks.keys())

        if not blips:
            return

        # Hungarian cost matrix
        matched_blip = set()
        if track_ids:
            cost = np.full((len(track_ids), len(blips)), 9999.0)
            for i, tid in enumerate(track_ids):
                px, py = preds[tid]
                for j, (bx, by, *_) in enumerate(blips):
                    d = float(np.sqrt((px-bx)**2 + (py-by)**2))
                    if d < HUNGARIAN_DIST:
                        cost[i, j] = d
            row_ind, col_ind = linear_sum_assignment(cost)
            for r, c in zip(row_ind, col_ind):
                if cost[r, c] < HUNGARIAN_DIST:
                    self._absorb(track_ids[r], frame_idx, t_sec,
                                 blips[c], ocr_results[c])
                    matched_blip.add(c)

        # Blip chưa ghép → track mới
        for j, (blip, tid_ocr) in enumerate(zip(blips, ocr_results)):
            if j in matched_blip:
                continue
            bx, by = blip[0], blip[1]
            tid = tid_ocr.strip() if tid_ocr.strip() else self._new_anon()
            if tid not in self.tracks:
                self.tracks[tid] = {
                    "kf":         KalmanTrack(bx, by, self.dt),
                    "color":      blip[5],
                    "history":    [],
                    "last_t":     t_sec,
                    "last_frame": frame_idx,
                }
            self._absorb(tid, frame_idx, t_sec, blip, tid_ocr)

    def _absorb(self, tid, frame_idx, t_sec, blip, tid_ocr):
        bx, by, area, dist, bearing, color, dx, dy = blip
        info = self.tracks[tid]
        info["kf"].update(bx, by)
        info["color"]      = color
        info["last_t"]     = t_sec
        info["last_frame"] = frame_idx
        info["history"].append((t_sec, dx, dy, bx, by))
        if len(info["history"]) > 300:
            info["history"] = info["history"][-300:]
        # Nâng cấp track ẩn danh nếu OCR tìm được ID
        if tid.startswith("?") and tid_ocr.strip():
            new_id = tid_ocr.strip()
            if new_id not in self.tracks:
                self.tracks[new_id] = self.tracks.pop(tid)

    def speed_kmh(self, tid):
        info = self.tracks.get(tid)
        if not info:
            return None
        vx, vy = info["kf"].vel_km_s()
        spd = float(np.sqrt(vx**2 + vy**2)) * 3600
        return spd if spd < 5000 else None


# ─────────────────────────────────────────────────────────────────────────────
# DRAW
# ─────────────────────────────────────────────────────────────────────────────
HOVER_RADIUS = 22

def draw_frame(canvas, frame_idx, tm, fps, sweep_angle, mx=0, my=0):
    t_sec   = frame_idx / fps
    hovered = None

    for tid, info in tm.tracks.items():
        if t_sec - info["last_t"] > MAX_LOST_SEC * 1.5:
            continue
        hist  = info["history"]
        color = COLOR_MAP.get(info["color"], UNKNOWN_COL)
        if not hist:
            continue
        kf = info["kf"]
        px, py = kf.pos_px()

        # Đuôi quỹ đạo
        for k in range(1, min(TAIL_LEN, len(hist))):
            alpha = k / TAIL_LEN
            c  = tuple(int(v * alpha * 0.7) for v in color)
            p1 = (hist[-(k+1)][3], hist[-(k+1)][4])
            p2 = (hist[-k][3],     hist[-k][4])
            cv2.line(canvas, p1, p2, c, 1)

        # Đường dự đoán tuyến tính (PRED_SEC giây)
        vx_px = float(kf.x[2,0])
        vy_px = float(kf.x[3,0])
        steps = 12
        pts = []
        for s in range(1, steps + 1):
            t_frames = s * (PRED_SEC / steps) * fps
            pts.append((int(px + vx_px * t_frames), int(py + vy_px * t_frames)))
        for s in range(len(pts) - 1):
            if s % 2 == 0:
                cv2.line(canvas, pts[s], pts[s+1], color, 1)
        if len(pts) >= 2:
            cv2.arrowedLine(canvas, pts[-2], pts[-1], color, 1, tipLength=0.4)

        # Biểu tượng blip
        cv2.circle(canvas, (px, py), 9, color, 2)
        cv2.line(canvas, (px-5, py), (px+5, py), color, 1)
        cv2.line(canvas, (px, py-5), (px, py+5), color, 1)

        display_id = tid if not tid.startswith("?") else "???"
        cv2.putText(canvas, display_id, (px+11, py+5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)

        if (mx - px)**2 + (my - py)**2 <= HOVER_RADIUS**2:
            hovered = tid

    # Chỉ hướng sweep
    if sweep_angle is not None:
        rad = np.radians(sweep_angle)
        ex  = int(CX + np.sin(rad) * (R_300KM - 10))
        ey  = int(CY - np.cos(rad) * (R_300KM - 10))
        cv2.line(canvas, (CX, CY), (ex, ey), (0, 40, 0), 1)

    # Tooltip
    if hovered and hovered in tm.tracks:
        _draw_tooltip(canvas, hovered, tm.tracks[hovered], tm, mx, my)

    n_named = sum(1 for t in tm.tracks
                  if t_sec - tm.tracks[t]["last_t"] <= MAX_LOST_SEC and not t.startswith("?"))
    n_total = sum(1 for t in tm.tracks
                  if t_sec - tm.tracks[t]["last_t"] <= MAX_LOST_SEC)
    sweep_str = f"  |  Sweep: {sweep_angle:.0f}°" if sweep_angle else ""
    bar = f"  t={t_sec:.1f}s  |  {n_named}/{n_total} muc tieu{sweep_str}"
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 22), (0, 0, 0), -1)
    cv2.putText(canvas, bar, (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 220), 1)
    return hovered

def _draw_tooltip(canvas, tid, info, tm, mx, my):
    hist = info["history"]
    if not hist:
        return
    _, xkm, ykm, _, _ = hist[-1]
    dist  = float(np.sqrt(xkm**2 + ykm**2))
    bear  = float(np.degrees(np.arctan2(xkm, ykm)) % 360)
    spd   = tm.speed_kmh(tid)
    color = COLOR_MAP.get(info["color"], UNKNOWN_COL)
    did   = tid if not tid.startswith("?") else "???"
    _LOAI = {"RED":"Quân sự","GREEN":"Quá cảnh","YELLOW":"Chưa rõ",
              "CYAN":"Địch","MAGENTA":"Quốc tế"}
    lines = [
        (f"ID: {did}",                              (220, 220, 220), _FONT),
        (f"Loại: {_LOAI.get(info['color'], info['color'])}",
                                                    color,           _FONT_BD),
        (f"Cự ly:     {dist:.0f} km",               (220, 220, 220), _FONT),
        (f"Phương vị: {bear:.0f}°",                 (220, 220, 220), _FONT),
        (f"Tốc độ:    {spd:.0f} km/h" if spd else "Tốc độ:    ---",
                                                    (200, 200, 150), _FONT),
    ]
    LH, PAD, W = 24, 8, 220
    H = len(lines) * LH + PAD * 2
    h, w = canvas.shape[:2]
    bx = mx + 24 if mx + 24 + W < w else mx - W - 24
    by = max(4, min(my - H // 2, h - H - 4))
    cv2.rectangle(canvas, (bx-2, by-2), (bx+W+2, by+H+2), color, 2)
    cv2.rectangle(canvas, (bx, by), (bx+W, by+H), (10, 10, 10), -1)
    pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    drw = ImageDraw.Draw(pil)
    for i, (text, tcol, fnt) in enumerate(lines):
        drw.text((bx+PAD, by+PAD+i*LH), text, font=fnt,
                 fill=(tcol[2], tcol[1], tcol[0]))
    np.copyto(canvas, cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR))


# ─────────────────────────────────────────────────────────────────────────────
# BẢNG THÔNG TIN
# ─────────────────────────────────────────────────────────────────────────────
TW, TWH, TTH, TRH, THH = 520, 320, 36, 26, 28
_CDIV = [0, 42, 130, 200, 292, 385, TW]
_CHDR = ["STT", "Màu", "ID", "Cự ly(km)", "GPV(°)", "Tốc(km/h)"]
table_scroll = 0

def build_table(tm, t_sec):
    active = [(tid, info) for tid, info in tm.tracks.items()
              if t_sec - info["last_t"] <= MAX_LOST_SEC]
    active.sort(key=lambda x: (x[0].startswith("?"), x[0]))
    n = max(len(active), 1)
    H = TTH + THH + n * TRH + 4
    img = np.full((H, TW, 3), (20, 20, 20), np.uint8)
    cv2.rectangle(img, (0, 0), (TW, TTH), (0, 55, 55), -1)
    n_named = sum(1 for t, _ in active if not t.startswith("?"))
    cv2.putText(img, "DANH SACH MUC TIEU", (10, TTH-9),
                cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 230, 230), 2)
    cv2.putText(img, f"{n_named}/{len(active)}", (TW-60, TTH-9),
                cv2.FONT_HERSHEY_SIMPLEX, 0.46, (150, 200, 150), 1)
    hy = TTH
    cv2.rectangle(img, (0, hy), (TW, hy+THH), (38, 38, 38), -1)
    for j, name in enumerate(_CHDR):
        cv2.putText(img, name, (_CDIV[j]+5, hy+THH-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 210, 210), 1)
    cv2.line(img, (0, hy+THH), (TW, hy+THH), (90, 90, 90), 1)
    for i, (tid, info) in enumerate(active):
        ry  = TTH + THH + i * TRH
        bg  = (32, 32, 32) if i % 2 == 0 else (22, 22, 22)
        cv2.rectangle(img, (0, ry), (TW, ry+TRH), bg, -1)
        hist  = info["history"]
        color = COLOR_MAP.get(info["color"], UNKNOWN_COL)
        did   = tid if not tid.startswith("?") else "???"
        d_str = s_str = b_str = "---"
        if hist:
            _, xkm, ykm, _, _ = hist[-1]
            d_str = f"{np.sqrt(xkm**2 + ykm**2):.0f}"
            b_str = f"{np.degrees(np.arctan2(xkm, ykm)) % 360:.0f}"
        spd = tm.speed_kmh(tid)
        if spd is not None:
            s_str = f"{spd:.0f}"
        ty    = ry + TRH - 7
        cells = [(str(i+1), (180, 180, 180)), (info["color"], color),
                 (did, color), (d_str, (215, 215, 215)),
                 (b_str, (215, 215, 215)), (s_str, (215, 215, 215))]
        for (text, tcol), cx in zip(cells, _CDIV):
            cv2.putText(img, text, (cx+5, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.48, tcol, 1)
        cv2.line(img, (0, ry+TRH), (TW, ry+TRH), (48, 48, 48), 1)
    for x in _CDIV[1:-1]:
        cv2.line(img, (x, TTH), (x, H-1), (60, 60, 60), 1)
    cv2.rectangle(img, (0, 0), (TW-1, H-1), (80, 80, 80), 1)
    return img

def on_table_scroll(event, x, y, flags, param):
    global table_scroll
    if event == cv2.EVENT_MOUSEWHEEL:
        table_scroll = max(0, table_scroll + (TRH*3 if flags < 0 else -TRH*3))


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
cap   = cv2.VideoCapture(VIDEO_PATH)
FPS   = cap.get(cv2.CAP_PROP_FPS)
TOTAL = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
W     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
H     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"Video: {W}x{H}  {FPS:.1f}fps  {TOTAL} frames ({TOTAL/FPS:.0f}s)")

writer = cv2.VideoWriter(OUTPUT_PATH, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
if not writer.isOpened():
    OUTPUT_PATH = OUTPUT_PATH.replace(".mp4", ".avi")
    writer = cv2.VideoWriter(OUTPUT_PATH, cv2.VideoWriter_fourcc(*"MJPG"), FPS, (W, H))
    print("Fallback → .avi")

_build_radar_mask(H, W)
tm = TrackManager(FPS)

cv2.namedWindow("Radar v2", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Radar v2", W, H)
cv2.setMouseCallback("Radar v2", on_mouse)
cv2.namedWindow("Bang thong tin v2", cv2.WINDOW_AUTOSIZE)
cv2.setMouseCallback("Bang thong tin v2", on_table_scroll)

frame_idx   = 0
sweep_angle = None
table_img   = build_table(tm, 0.0)

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        t_sec = frame_idx / FPS

        if frame_idx % OCR_EVERY == 0:
            blips       = detect_blips(frame)
            sweep_angle = detect_sweep_angle(frame)

            ocr_results = [ocr_near_blip(frame, b[0], b[1]) for b in blips]

            tm.update(frame_idx, blips, ocr_results)
            table_img = build_table(tm, t_sec)

            n_t = sum(1 for x in tm.tracks
                      if t_sec - tm.tracks[x]["last_t"] <= MAX_LOST_SEC)
            pct = frame_idx / TOTAL * 100
            sweep_str = f"  sweep={sweep_angle:.0f}°" if sweep_angle else ""
            print(f"\r  {pct:5.1f}%  [{frame_idx}/{TOTAL}]  blips={len(blips)}"
                  f"  tracks={n_t}{sweep_str}", end="", flush=True)

        canvas = frame.copy()
        draw_frame(canvas, frame_idx, tm, FPS, sweep_angle, mouse_x, mouse_y)
        writer.write(canvas)
        cv2.imshow("Radar v2", canvas)

        _max_s = max(0, table_img.shape[0] - TWH)
        table_scroll = min(table_scroll, _max_s)
        view = table_img[table_scroll:table_scroll + TWH]
        if view.shape[0] < TWH:
            pad  = np.zeros((TWH - view.shape[0], TW, 3), np.uint8)
            view = np.vstack([view, pad])
        cv2.imshow("Bang thong tin v2", view)

        if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
            break
        frame_idx += 1

finally:
    print()
    cap.release()
    writer.release()
    cv2.destroyAllWindows()

# ─── Lưu JSON ────────────────────────────────────────────────────────────────
out = {}
for tid, info in tm.tracks.items():
    out[tid] = {
        "color":   info["color"],
        "history": [
            {"t":        h[0],
             "dx_km":    round(h[1], 1),
             "dy_km":    round(h[2], 1),
             "dist_km":  round(float(np.sqrt(h[1]**2 + h[2]**2)), 1),
             "bearing":  round(float(np.degrees(np.arctan2(h[1], h[2])) % 360), 1)}
            for h in info["history"]
        ],
    }
with open(r"c:\Users\ygost\radar\tracks_v2.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

named = [k for k in tm.tracks if not k.startswith("?")]
print(f"\nDone! Output: {OUTPUT_PATH}")
print(f"Tracks: {len(tm.tracks)} total, {len(named)} named: {sorted(named)}")
