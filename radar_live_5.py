"""
Radar Live v5 — fork từ radar_live_4.py, GIỮ NGUYÊN toàn bộ pipeline (lọc
nhiễu detect_blips, TrackManager, mốc tỉ lệ ORB/AKAZE, TTS, bảng, JSON/HTML,
OCR số hiệu...), CHỈ thay nguồn khung hình: từ thiết bị USB/HDMI capture card
vật lý (`run_radar_from_capture` của v4) sang MỘT LUỒNG VIDEO QUA MẠNG LAN
(RTSP/HTTP — vd một IP camera chĩa vào màn hình phần mềm ATC, hoặc bộ mã
hoá/chuyển tiếp mạng khác đã có sẵn). Hàm mới `run_radar_from_lan(url)` chỉ
đổi đúng chỗ MỞ NGUỒN (`cv2.VideoCapture(url)` thay vì `cv2.VideoCapture(
device_index, cv2.CAP_DSHOW)`) — phần còn lại của vòng lặp giữ nguyên gần
như 100% từ `run_radar_from_capture`. Đã bỏ phần dò thiết bị DirectShow
(`list_video_capture_devices`/`show_video_device_dialog`/`_wmi_video_names`,
`win32com.client`) vì không liên quan tới nguồn mạng — giữ nguyên
`run_radar_from_video` (phát lại file) cho việc test lại các kịch bản zoom
đã ghi trong CLAUDE.md, cùng lý do v3 từng giữ lại nó khi bỏ phần COM/Serial.

── Yêu cầu "chuyển sang tab khác vẫn xử lý được" ───────────────────────────
Yêu cầu này áp dụng cho máy PHÂN TÍCH (máy chạy chính file này), KHÔNG phải
máy nguồn — khi người dùng ở máy này bấm Alt+Tab / chuyển sang cửa sổ hay
tab khác, việc đọc luồng LAN + detect/track/OCR/TTS vẫn phải tiếp tục chạy
nền bình thường, không dừng/treo dù cửa sổ radar mất focus hoặc bị che khuất.

Kiến trúc kế thừa từ chế độ capture card của v4 ĐÃ đáp ứng đúng yêu cầu này
từ trước, không cần đổi gì thêm ở phần đó:
  • Chuột/phím bắt qua HOOK TOÀN CỤC (`pynput.mouse.Listener` /
    `pynput.keyboard.Listener`) — nhận sự kiện ở cấp hệ điều hành, không phụ
    thuộc cửa sổ nào đang được Windows coi là "active"/"focused". Khác hẳn
    `cv2.setMouseCallback` cục bộ (dùng ở chế độ phát file
    `run_radar_from_video`) vốn chỉ nhận sự kiện khi đúng cửa sổ đó có focus.
  • Vòng lặp chính dùng `cv2.waitKey(1)` — KHÔNG BAO GIỜ chặn (khác
    `waitKey(0)`) — nên đọc frame/detect/track/ghi JSON-HTML/phát TTS vẫn
    chạy đều đặn dù cửa sổ không phải cửa sổ đang active.
  • Mọi luồng nền (audio, OCR, auto-scan) đều là `daemon` thread độc lập với
    vòng lặp hiển thị, không bị ảnh hưởng bởi focus cửa sổ.

Phần DUY NHẤT thực sự MỚI ở bản LAN: mạng có thể RỚT KẾT NỐI tạm thời (khác
thiết bị USB/HDMI vật lý, DirectShow gần như luôn trả frame liên tục trừ khi
rút dây hẳn) — nếu xử lý ẩu (vd chờ kết nối lại bằng 1 lệnh `time.sleep` dài
không bơm cửa sổ), vòng lặp sẽ tự CHẶN CHÍNH NÓ trong lúc chờ, khiến toàn bộ
lý do "không phụ thuộc focus" ở trên trở nên vô nghĩa — cửa sổ "đứng hình"
không phải vì mất focus mà vì chính vòng lặp không chạy tiếp nữa. Fix: đếm
số lần đọc frame lỗi LIÊN TIẾP (`LAN_READ_FAIL_RECONNECT`), sau ngưỡng đó
mới đóng + mở lại kết nối (`_open_lan_capture()`); trong lúc CHỜ backoff
giữa các lần thử, gọi `cv2.waitKey(30)` đều đặn từng đợt ngắn thay vì
`time.sleep()` một cục dài — giữ cửa sổ luôn phản hồi (không bị Windows báo
"Not Responding") và vẫn cho phép bấm Q/Esc thoát ngay cả khi đang mất kết
nối.

── Phần dưới đây (kế thừa nguyên văn từ v4/v3) mô tả các quyết định thiết kế
cũ — vẫn đúng nguyên vẹn cho bản LAN này (mốc tỉ lệ ORB/AKAZE, 3 lớp lọc
nhiễu, OCR...), chỉ nguồn khung hình là khác.
── ──────────────────────────────────────────────────────────────────────

Radar Live v4 — fork từ radar_live_3.py, GIỮ NGUYÊN toàn bộ pipeline (nguồn
video, lọc nhiễu detect_blips, TrackManager, TTS, bảng, JSON/HTML...), CHỈ
thay bộ máy "MỐC THAM CHIẾU TỈ LỆ" (đo KM_PX khi video zoom) từ so khớp mẫu
đa tỉ lệ (`cv2.matchTemplate` quét hàng chục/trăm hệ số k giả định — cách cũ
của v3) sang FEATURE MATCHING (ORB/AKAZE) — xem khối docstring ngay trên
`set_reference_region()` để biết lý do và chi tiết thuật toán mới. Phần dưới
đây (kế thừa nguyên văn từ v3) mô tả bối cảnh bài toán zoom — vẫn đúng ở v4,
chỉ có CÁCH TÍNH k thay đổi, không phải MÔ HÌNH vật lý (tâm cố định, mốc co
giãn theo 1 hệ số k dọc theo 1 tia cố định).

── (kế thừa từ v3) Radar Live v3 — fork từ radar_live_2.py, chuyển nguồn từ
thiết bị capture (HDMI/USB) sang PHÁT LẠI FILE VIDEO đã ghi sẵn (mặc định
`phong_to.mp4`), đồng thời xử lý vấn đề video có PHÓNG TO/THU NHỎ (zoom)
giữa chừng — thứ không xảy ra với capture card (luôn giữ nguyên khung hình
nguồn).

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
from pynput import mouse as pmouse
import mss
import pygame
import tkinter as tk
import tkinter.messagebox

try:
    import easyocr
    _HAS_EASYOCR = True
except ImportError:
    _HAS_EASYOCR = False

try:
    _PIL_FONT    = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf",   18)
    _PIL_FONT_BD = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 18)
except Exception:
    _PIL_FONT = _PIL_FONT_BD = ImageFont.load_default()

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
# Radar calibration — chỉnh lại bằng bước "calibrate" khi chạy (nguồn ngoài đổi tuỳ máy)
CX, CY   = 549, 371
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
# BUG đã sửa: user báo "mục tiêu gần nhau vẫn chưa bắt được" — đo trực tiếp
# trên khung hình thật: 25px LỚN HƠN khoảng cách thật đo được giữa 2 mục
# tiêu KHÁC NHAU đứng gần nhau (vd 13.0px giữa 2 icon CYAN, 14.0px giữa 2
# icon RED trong cùng 1 khung hình) — nghĩa là sau khi đã Shift+click xác
# nhận mục tiêu A, Shift+click vào mục tiêu B đứng ngay cạnh (cách A chỉ
# 13-14px) bị `find_nearest_blip()` hiểu nhầm là "đã có track A gần đó" và
# chỉ CHỌN LẠI A thay vì tạo track mới cho B — B không bao giờ xác nhận
# được bằng Shift+click dù bấm đúng chỗ. Fix: hạ 25 → 10 (cùng biên độ an
# toàn như `BLIP_MERGE_RADIUS`, dưới khoảng cách thật gần nhất đã đo ~13px,
# nhưng vẫn đủ rộng để bỏ qua trường hợp click lại gần đúng tâm 1 icon đã
# xác nhận, icon rộng ~15-17px nên click lệch tâm thường trong ~5-8px).
SHIFT_CLICK_SKIP_RADIUS = 10   # px — nếu đã có track trong bán kính này thì bỏ qua, không tạo mới

DEFAULT_VIDEO = "phong_to.mp4"

TARGET_FPS = 15   # fps giả định khi luồng LAN/file không báo cáo fps hợp lệ

# Nguồn video qua mạng LAN (RTSP/HTTP) — mặc định khi chạy không kèm đường dẫn
# file video. Mạng có thể rớt kết nối tạm thời (khác thiết bị USB/HDMI vật lý)
# nên cần chủ động phát hiện + mở lại kết nối thay vì chỉ chờ tự phục hồi —
# xem docstring đầu file, mục "chuyển tab khác vẫn xử lý được".
LAN_READ_FAIL_RECONNECT = 25          # số lần đọc lỗi LIÊN TIẾP trước khi đóng
                                       # + mở lại kết nối (~5s ở sleep 0.2s/lần)
LAN_RECONNECT_BACKOFF = (0.5, 1, 2, 3, 5)   # giây, tăng dần rồi giữ ở mức cuối
                                             # giữa các lần thử mở lại liên tiếp

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
# GREEN hi-hue siết từ 85 xuống 66 — BUG đã sửa: đo trực tiếp trên nguồn USB
# capture card thật (không phải phong_to.mp4), phần mềm ATC vẽ đường viền
# khu vực bám sát nét đứt bằng 1 sắc xanh lá NGẢ XANH DA TRỜI rõ rệt khác
# với icon mục tiêu — đo hue trung bình từng blob trên 1 khung hình thật:
# icon mục tiêu thật cụm chặt ở hue 51-64 (đỉnh ~57-58, tối đa từng pixel đo
# được 70), đường viền/nhiễu cụm ở hue 74-83 — có KHOẢNG TRỐNG THẬT giữa
# 65-69 không có blob nào rơi vào. Đây chính là nguồn gốc "bắt nhầm đường
# viền" mà lọc theo hình dạng/thời gian (area, solidity, convexity-defect,
# mật độ chữ nhãn lân cận, khoảng cách tới đường Hough) đều KHÔNG tách bạch
# được — vì đó là 2 lớp hoạ đồ có HÌNH DẠNG chồng lấn nhưng MÀU SẮC khác
# nhau rõ ràng, chỉ là bị gộp chung 1 khoảng hue "GREEN" quá rộng (40-85).
# Đã quét hi_hue 60-85 trên dữ liệu thật: 66 là điểm ngay trong khoảng trống,
# giữ đủ CẢ 5 mục tiêu GREEN thật đã xác nhận (giảm tổng blob GREEN 23→12);
# 64 bắt đầu làm rớt 1 mục tiêu thật (icon có hue rìa gần biên).
HSV_RANGES = {
    "RED":     [((0,  80, 80),(14, 255,255)), ((166,80, 80),(180,255,255))],
    "GREEN":   [((40,  70, 80),(66, 255,255))],
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
# GLOBAL KEYBOARD/MOUSE HOOKS (pynput)
# `_delete_key_q`/`_on_key_press` dùng chung cho CẢ 2 chế độ (phím Delete).
# Phần còn lại (`_shift_state`, `_left_click_q_g`, `_right_click_q_g`,
# `_mid_drag_g`, `_on_key_release`, `_on_global_mouse_*`) CHỈ dùng cho chế độ
# nguồn LAN (`run_radar_from_lan`, xem khối docstring đầu file) — cửa sổ chạy
# true fullscreen trên toàn màn hình output nên click phải bắt qua hook TOÀN
# CỤC thay vì cv2.setMouseCallback cục bộ (kế thừa từ radar_live_2.py/v4, xem
# lý do trong file đó — đây cũng CHÍNH LÀ cơ chế đảm bảo xử lý không phụ
# thuộc cửa sổ có đang được focus hay không khi chuyển tab). Chế độ phát lại
# file (`run_radar_from_video`) vẫn dùng cv2.setMouseCallback cục bộ như cũ,
# không đụng tới các biến này.
# ══════════════════════════════════════════════════════════════════════════════
_delete_key_q    = queue.Queue()
_left_click_q_g  = queue.Queue()
_right_click_q_g = queue.Queue()
_shift_state     = {"held": False}
_mid_drag_g      = {"active": False, "p0": None, "p1": None, "pending_rect": None}

_SHIFT_KEYS = (pkeyboard.Key.shift, pkeyboard.Key.shift_l, pkeyboard.Key.shift_r)

def _on_key_press(key):
    if key in _SHIFT_KEYS:
        _shift_state["held"] = True
    elif key == pkeyboard.Key.delete:
        _delete_key_q.put(True)

def _on_key_release(key):
    if key in _SHIFT_KEYS:
        _shift_state["held"] = False

def _on_global_mouse_click(x, y, button, pressed):
    if button == pmouse.Button.left:
        if pressed:
            _left_click_q_g.put((x, y))
    elif button == pmouse.Button.right:
        if pressed:
            _right_click_q_g.put((x, y))
    elif button == pmouse.Button.middle:
        if pressed:
            _mid_drag_g["active"] = True
            _mid_drag_g["p0"] = (x, y); _mid_drag_g["p1"] = (x, y)
        else:
            _mid_drag_g["active"] = False
            if _mid_drag_g["p0"] is not None:
                _mid_drag_g["pending_rect"] = (_mid_drag_g["p0"], (x, y))

def _on_global_mouse_move(x, y):
    if _mid_drag_g["active"]:
        _mid_drag_g["p1"] = (x, y)

# ══════════════════════════════════════════════════════════════════════════════
# AUDIO
# ══════════════════════════════════════════════════════════════════════════════
# BUG đã sửa: "[AUDIO] Invalid audio device ID" in tràn console liên tục —
# pygame.mixer đã init() thành công lúc khởi động, nhưng thiết bị audio mặc
# định của Windows đổi GIỮA CHỪNG lúc app đang chạy (vd tai nghe/loa
# Bluetooth kết nối hoặc ngắt kết nối — máy này có ghép nối "Redmi Buds"/
# "Redmi note 11 pro A2DP" qua Bluetooth, xác nhận qua WMI) khiến stream
# pygame đang giữ THAM CHIẾU tới thiết bị CŨ (đã mất) — mọi lần phát sau đó
# đều ném lỗi GIỐNG HỆT nhau, và code cũ chỉ `print()` rồi thử lại ngay lập
# tức cho clip kế tiếp (thất bại y hệt), gây spam vô hạn không tự phục hồi.
# Fix: (1) giới hạn tần suất in lỗi (1 lần mỗi `_AUDIO_REINIT_COOLDOWN`
# giây, không phải mỗi lần gọi); (2) thử pygame.mixer.quit()+init() lại khi
# gặp lỗi — nếu Windows đã có thiết bị mặc định MỚI hợp lệ, lần init lại
# này sẽ tự khớp đúng thiết bị đó và phục hồi phát âm thanh bình thường mà
# không cần khởi động lại cả ứng dụng.
_AUDIO_REINIT_COOLDOWN = 3.0   # giây — khoảng cách tối thiểu giữa 2 lần thử
                               # khởi tạo lại + in lỗi (tránh spam/hammer)
_audio_last_error_time = [0.0]

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
        now = time.time()
        if now - _audio_last_error_time[0] > _AUDIO_REINIT_COOLDOWN:
            _audio_last_error_time[0] = now
            print(f"\n[AUDIO] Loi phat am thanh ({e}) — dang thu khoi dong lai "
                  f"thiet bi am thanh...", flush=True)
            try:
                pygame.mixer.quit()
                pygame.mixer.init()
                print("[AUDIO] Da khoi dong lai OK", flush=True)
            except Exception as e2:
                print(f"[AUDIO] Khong khoi dong lai duoc: {e2}", flush=True)
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
    global _auto_scan_mode, _discovery_last_time, _discovery_prev_snapshot
    _auto_scan_mode = not any(not info.get("auto", False) for info in tm.tracks.values())
    # Đặt = now (không phải 0) để lần "ảnh chụp" đầu tiên đợi đủ
    # AUTO_DISCOVERY_INTERVAL_SEC giây rồi mới chạy — tránh chạy ngay lập
    # tức lúc StaticNoiseFilter còn chưa kịp loại nhiễu tĩnh thật trong vài
    # giây đầu của chính nó (xem docstring auto_confirm_nearby()).
    _discovery_last_time = time.time()
    _discovery_prev_snapshot = {}

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

# Phát hiện mục tiêu mới cho "Phát tự động" (tự-do-quét) — SO SÁNH 2 "ẢNH
# CHỤP" candidate cách nhau >= AUTO_DISCOVERY_INTERVAL_SEC giây, KHÔNG đếm
# streak mỗi chu kỳ detect nhanh. Lịch sử 2 lần sửa:
# 1) Bản đầu: auto_confirm_nearby() xác nhận NGAY ở lần unmatched ĐẦU TIÊN.
#    Một khối vừa (10-24px, solidity 0.35-0.7) ở CHỖ RẼ/GÓC của đường viền
#    khu vực bám sát nét đứt (đo thực tế trên nguồn USB capture card thật,
#    KHÔNG phải phong_to.mp4) lọt qua lọc hình dạng vì thống kê area/solidity
#    của nó chồng lấn với icon mục tiêu thật — không có ngưỡng đơn giản nào
#    tách bạch được từ 1 khung hình. Một khi được xác nhận, nó "tự khớp lại
#    chính nó" mỗi chu kỳ (đứng yên tuyệt đối, luôn được detect_blips() phát
#    hiện lại đúng chỗ cũ) nên KHÔNG BAO GIỜ còn nằm trong unmatched_blips
#    nữa — StaticNoiseFilter (vốn sinh ra để bắt đúng loại nhiễu này) không
#    bao giờ có cơ hội đánh giá/loại nó vì candidate đã "tốt nghiệp" thành
#    track trước khi bộ lọc đó kịp tích luỹ đủ streak.
# 2) Thử sửa bằng cách bắt candidate "unmatched liên tục N chu kỳ detect
#    NHANH" (streak đếm mỗi chu kỳ ~0.2-0.3s) trước khi xác nhận, TƯỞNG an
#    toàn nếu N đủ lớn — SAI, đã tự phát hiện qua đo đạc thêm (xem bên dưới)
#    trước khi kịp áp dụng cho người dùng: quan sát THỰC TẾ 60 giây liên tục
#    trên nguồn USB capture card cho thấy phần mềm ATC này cập nhật vị trí
#    mục tiêu THEO TỪNG BƯỚC RỜI RẠC mỗi 5-11+ giây (không liên tục) — mục
#    tiêu thật đứng yên TUYỆT ĐỐI (0px, không phải "trôi chậm") suốt mỗi
#    khoảng ~5-11s rồi mới nhảy 1 bước qua vị trí mới. Hệ quả: KHÔNG CÓ
#    ngưỡng N (chu kỳ nhanh) nào đúng cả — N thấp (dưới ~5s) bắt nhầm mục
#    tiêu thật y hệt nhiễu tĩnh thật (cả 2 đều "đứng yên" trong mọi khoảng
#    dưới 5s); N cao (trên ~11s) thì streak của MỤC TIÊU THẬT liên tục bị
#    RESET mỗi lần nó nhảy bước — trước khi kịp tích luỹ đủ — nên KHÔNG BAO
#    GIỜ đạt ngưỡng. Tức là N cao "bảo vệ" mục tiêu thật khỏi bị
#    StaticNoiseFilter loại (đúng mục đích ban đầu của bộ lọc đó, dùng
#    ngưỡng THẤP ~15 chu kỳ/~5s) nhưng lại khiến CHÍNH cơ chế xác-nhận-bằng-
#    streak (mục đích NGƯỢC LẠI — cần đạt ngưỡng để XÁC NHẬN) không bao giờ
#    kích hoạt được cho mục tiêu thật — không thể giải quyết bằng cách chọn
#    số N khác, vì bài toán không đối xứng.
# Fix thật: bỏ hẳn "streak mỗi chu kỳ nhanh", thay bằng SO SÁNH 2 ẢNH CHỤP
# toàn bộ candidate cách nhau >= AUTO_DISCOVERY_INTERVAL_SEC giây (theo mốc
# thời gian thực `time.time()`, kiểm tra ngay trong hàm này — KHÔNG cần
# luồng nền riêng, vì phần so sánh chỉ thực sự chạy 1 lần mỗi >60s nên "nhẹ
# máy", và không có thao tác nào chặn/làm chậm vòng lặp chính nên vẫn "đảm
# bảo trực tuyến" — người dùng đề xuất, xem thảo luận). Tại mỗi lần so sánh
# (cách lần trước >= AUTO_DISCOVERY_INTERVAL_SEC): 1 candidate được xác nhận
# thành track NẾU nó KHÔNG có candidate CÙNG MÀU nào đứng gần
# (AUTO_DISCOVERY_STATIC_TOL_PX) ở ẢNH CHỤP TRƯỚC — nghĩa là nó MỚI xuất
# hiện hoặc ĐÃ DỊCH CHUYỂN kể từ lần trước. Mục tiêu thật luôn cập nhật vị
# trí ít nhất 1 lần trong bất kỳ khoảng 60s+ nào (quan sát thực tế: mỗi
# 5-11s) nên gần như chắc chắn "khác" ảnh chụp trước và được xác nhận; nhiễu
# tĩnh thật (không bao giờ dịch chuyển) luôn "giống hệt" ảnh chụp trước nên
# không bao giờ được xác nhận. Lần so sánh ĐẦU TIÊN (ảnh chụp trước rỗng) xác
# nhận TẤT CẢ candidate hiện có — "khi chạy xong lần đầu, sẽ bám lấy các mục
# tiêu đó" — nên phiên "Phát tự động" mới bật sẽ đợi đúng
# AUTO_DISCOVERY_INTERVAL_SEC giây rồi mới populate loạt đầu (xem
# _start_auto_session() đặt `_discovery_last_time = time.time()`, KHÔNG phải
# 0, để tránh lần chụp đầu tiên chạy ngay lập tức lúc StaticNoiseFilter còn
# chưa kịp loại nhiễu tĩnh thật trong 15 chu kỳ/~5s đầu của chính nó).
AUTO_DISCOVERY_INTERVAL_SEC  = 65   # giây — phải > khoảng cập nhật thực tế
                                    # quan sát được (5-11s) với biên độ an toàn
AUTO_DISCOVERY_STATIC_TOL_PX = 30   # px — coi là "cùng 1 vị trí" giữa 2 lần
                                    # quét nếu cách nhau dưới mức này. Đo thực
                                    # nghiệm trên chuỗi 60s thật (USB capture):
                                    # quét 15-40px, kết quả ổn định (khớp đúng
                                    # số lượng mục tiêu RED thật đếm được thủ
                                    # công) từ 30px trở lên — dưới mức này,
                                    # rung/nhiễu nén nhỏ ở 1 vài blob tĩnh đôi
                                    # khi đủ để trông như "đã dịch chuyển".

_discovery_prev_snapshot = {}   # color -> list[(bx,by)] tại lần quét trước
_discovery_last_time     = 0.0

def auto_confirm_nearby(tm, frame_idx, unmatched_blips):
    """Khi Phát tự động/chậm đang bật VÀ đang ở chế độ tự-do-quét: cứ mỗi
    AUTO_DISCOVERY_INTERVAL_SEC giây, so ảnh chụp candidate hiện tại (trong
    bán kính GLOBAL_RADIUS) với ảnh chụp lần trước — xác nhận (tạo track,
    auto=True) các candidate MỚI xuất hiện hoặc đã dịch chuyển kể từ lần
    trước (xem khối docstring ngay trên). `unmatched_blips` đã được
    StaticNoiseFilter lọc bỏ nền tĩnh (đường bay chấm chấm...) trước khi tới
    đây — xem docstring đầu file."""
    global _discovery_last_time, _discovery_prev_snapshot
    if not (_global_auto_active or _global_auto_slow_active):
        return
    if not _auto_scan_mode:
        return
    now = time.time()
    if now - _discovery_last_time < AUTO_DISCOVERY_INTERVAL_SEC:
        return
    _discovery_last_time = now

    candidates = [b for b in unmatched_blips if b[3] <= GLOBAL_RADIUS]
    prev = _discovery_prev_snapshot
    for blip in candidates:
        bx, by, area, dist, bear, color, dx, dy = blip
        moved_or_new = True
        for (px, py) in prev.get(color, []):
            if abs(bx - px) < AUTO_DISCOVERY_STATIC_TOL_PX and abs(by - py) < AUTO_DISCOVERY_STATIC_TOL_PX:
                moved_or_new = False
                break
        if moved_or_new:
            tm.confirm_candidate(frame_idx, bx, by, color, dx, dy, auto=True)

    new_snapshot = {}
    for bx, by, area, dist, bear, color, dx, dy in candidates:
        new_snapshot.setdefault(color, []).append((bx, by))
    _discovery_prev_snapshot = new_snapshot

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
# BUG đã sửa: user báo "nhiều mục tiêu gần nhau" bị nhầm/mất — đo trực tiếp
# trên 114 khung hình thật (USB capture card): khoảng cách CÙNG MÀU gần nhau
# nhất từng đo được là 16.0px (RED) — THẤP HƠN ngưỡng gộp mảnh-vỡ-icon cũ
# (18px), nghĩa là ít nhất 1 lần 2 mục tiêu RED thật đứng đủ gần để bị GỘP
# NHẦM thành 1 blip (mất hẳn 1 mục tiêu khỏi detect_blips() ngay tại bước
# này, trước cả khi tới track-matching). Ngoài ra có tới 337 lượt (mọi màu)
# rơi vào khoảng biên 18-30px — đủ gần để rung/nén nhẹ có thể đẩy qua lại
# ngưỡng 18px, gây chớp tắt (mục tiêu "biến mất" 1-2 chu kỳ rồi lại hiện) mỗi
# khi 2 mục tiêu thật bay sát nhau. Mục đích BAN ĐẦU của ngưỡng này là gộp 2
# MẢNH VỠ của CÙNG 1 icon (do nén/mờ làm icon bị đứt đoạn thành 2 blob) —
# nhưng 1 icon chỉ rộng ~15-17px, nên mảnh vỡ của nó luôn rất gần (< ~10px),
# không cần ngưỡng rộng tới 18px. Fix: hạ xuống BLIP_MERGE_RADIUS=10 — vẫn
# đủ gộp mảnh vỡ cùng icon, nhưng có biên độ an toàn ~6px dưới khoảng cách
# gần nhất giữa 2 mục tiêu THẬT đo được (16px) — không còn gộp nhầm 2 mục
# tiêu khác nhau đứng sát nhau trong đội hình/khu vực đông đúc.
BLIP_MERGE_RADIUS   = 10    # px — bán kính gộp blip CÙNG MÀU (mảnh vỡ 1 icon)
BLIP_DENSITY_RADIUS = 35    # px — bán kính đếm "hàng xóm" cùng màu
# BUG đã sửa: user báo "mục tiêu gần nhau vẫn chưa bắt được" (Phát tự động)
# — đo trên chuỗi 80 khung hình thật (USB capture card): với
# BLIP_DENSITY_MAX_NB=1 cũ, filter_dense_candidates() loại nhầm 18-23% tổng
# số candidate RED/GREEN thật (319/1743 RED, 240/1036 GREEN) — vì đội hình
# thật chỉ cần 2 mục tiêu đứng trong bán kính 35px đã đủ vượt ngưỡng "> 1
# hàng xóm". Quét MAX_NB=1..4 trên cùng dữ liệu: MAX_NB=2 đã đưa tỉ lệ loại
# nhầm xuống 0% cho MỌI màu (kể cả CYAN/nhiễu bờ biển — hoá ra cũng không
# tụ thành cụm >2 trong bán kính này) — giữ MAX_NB=2 (thay vì bỏ hẳn bộ lọc
# bằng 1 số rất lớn) để bộ lọc vẫn có tác dụng nếu gặp 1 chuỗi chấm nền THẬT
# (nhiều hơn 2-3 chấm liên tiếp, như thiết kế ban đầu), chỉ không còn loại
# nhầm đội hình nhỏ 2-3 mục tiêu thật bay sát nhau nữa.
BLIP_DENSITY_MAX_NB = 2     # > ngưỡng này hàng xóm cùng màu gần đó trong 1 khung
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

    # Gộp các blip CÙNG MÀU quá gần nhau (< BLIP_MERGE_RADIUS) — mảnh vỡ của
    # cùng 1 icon bị đứt đoạn do ảnh mờ/nén. Khác màu KHÔNG được gộp dù đứng
    # sát nhau. Xem giải thích đầy đủ ở khối docstring trên BLIP_MERGE_RADIUS.
    raw.sort(key=lambda x: x[3])
    merged, used = [], set()
    for i, b in enumerate(raw):
        if i in used:
            continue
        grp = [b]
        for j, b2 in enumerate(raw):
            if j <= i or j in used:
                continue
            if b[5] == b2[5] and abs(b[0]-b2[0]) < BLIP_MERGE_RADIUS and abs(b[1]-b2[1]) < BLIP_MERGE_RADIUS:
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
# BUG đã sửa: user báo "Phát tự động không bắt đủ mục tiêu thật" ngay cả sau
# khi sửa auto_confirm_nearby() (xem docstring ngay trên hàm đó) — nguyên
# nhân KHÔNG nằm ở auto_confirm_nearby() mà ở CHÍNH bộ lọc này chạy TRƯỚC nó:
# đo thực tế 60s liên tục trên nguồn USB capture card thật cho thấy phần mềm
# ATC cập nhật vị trí mục tiêu THEO TỪNG BƯỚC RỜI RẠC mỗi 5-11+ giây — mục
# tiêu thật đứng yên TUYỆT ĐỐI (0px) suốt mỗi khoảng đó. Với STATIC_HIT_LIMIT
# cũ = 15 chu kỳ (~5s @ 15fps), StaticNoiseFilter coi NHẦM các mục tiêu thật
# này là nền tĩnh và loại khỏi candidate list VĨNH VIỄN (tới khi zoom lại) —
# auto_confirm_nearby() không bao giờ có cơ hội thấy chúng nữa, bất kể logic
# xác nhận của nó đúng hay sai. Khác với auto_confirm_nearby() (dùng streak
# để XÁC NHẬN — ngưỡng cao khiến mục tiêu thật liên tục reset streak trước
# khi đạt được, nên KHÔNG BAO GIỜ xác nhận — đã bỏ cách này), bộ lọc NÀY dùng
# streak để LOẠI — ngưỡng cao có tác dụng NGƯỢC LẠI và AN TOÀN: mục tiêu thật
# (luôn tự reset streak mỗi 5-11s do bản chất cập nhật rời rạc) sẽ KHÔNG BAO
# GIỜ đạt ngưỡng cao nên không bao giờ bị loại nhầm, trong khi nhiễu tĩnh
# THẬT (không bao giờ tự reset, đứng yên vô hạn) vẫn chắc chắn đạt ngưỡng —
# chỉ chậm hơn (~30-40s thay vì ~5s), hoàn toàn chấp nhận được vì nhiễu nền
# không "hết hạn" theo thời gian.
STATIC_HIT_LIMIT  = 120  # ~30-40s @ 15-30fps — CAO HƠN HẲN khoảng cập nhật
                          # thực tế 5-11s (biên độ an toàn ~3-4 lần) để không
                          # loại nhầm mục tiêu thật cập nhật rời rạc, nhưng
                          # vẫn chắc chắn loại được nhiễu tĩnh vĩnh viễn (chỉ
                          # chậm hơn, không ảnh hưởng vì nhiễu nền là vô hạn).
                          # (track thật một khi đã được xác nhận sẽ không còn
                          # là candidate nữa nên không bao giờ tự đạt ngưỡng này)
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

    def is_static(self, color, x, y):
        """True nếu (color,x,y) rơi vào 1 ô đã được xác nhận là nền tĩnh lâu
        dài (đã tích luỹ đủ STATIC_HIT_LIMIT chu kỳ liên tục là candidate).
        Dùng để CẢNH BÁO (không chặn) khi Shift+click thủ công trúng đúng 1
        vị trí đã biết là bờ biển/đảo/lưới tĩnh — xem
        `SHIFT_CLICK_SKIP_RADIUS`/`_shift_state` nơi gọi."""
        return (color, x // STATIC_BIN_PX, y // STATIC_BIN_PX) in self.static_set

# ══════════════════════════════════════════════════════════════════════════════
# MỐC THAM CHIẾU TỈ LỆ — chọn 1 VÙNG cố định (không phải điểm) để suy ra
# KM_PX khi video zoom.
#
# (Lịch sử điểm-click / đọc chữ "Tầm quan sát" phần mềm, và lý do chốt cách
# chọn 1 VÙNG bằng CHUỘT GIỮA: xem CLAUDE.md — mô hình vật lý của bài toán
# KHÔNG đổi ở v4 so với v3 (tâm radar cố định, mốc co giãn theo 1 hệ số k
# dọc theo 1 tia cố định từ tâm), CHỈ đổi CÁCH TÍNH k.)
#
# ── v3 (matchTemplate đa tỉ lệ) → v4 (feature matching ORB/AKAZE) ──────────
# v3 phải TỰ GIẢ ĐỊNH một lưới hệ số k rồi resize mẫu/vùng cắt về cùng kích
# thước để so khớp pixel-đối-pixel (`cv2.matchTemplate`) tại TỪNG k — đúng
# kiểu "dò mù": không biết trước k nên phải quét rất nhiều điểm (dò quanh +
# dò toàn dải + tinh chỉnh nhiều vòng), và vì so khớp pixel thô nên rất nhạy
# với sai khác đường nét do phần mềm VẼ LẠI khung hình ở tỉ lệ mới (khác
# line-width/khử răng cưa) — thực tế đo được trên phong_to.mp4: điểm khớp
# tại ĐÚNG tỉ lệ sau 1 lần zoom thật chỉ ~0.15-0.35, không bao giờ vượt
# ngưỡng 0.6, phải vá bằng danh sách tỉ lệ "thường gặp" mới nhận diện được
# zoom thật (xem CLAUDE.md).
#
# ORB/AKAZE giải quyết đúng gốc rễ đó: cả 2 đều xây kim tự tháp đa tỉ lệ BÊN
# TRONG bộ dò đặc trưng (ORB: pyramid ảnh theo scaleFactor/nlevels; AKAZE:
# không gian tỉ lệ phi tuyến theo octave) — 1 đặc trưng phát hiện ở tỉ lệ
# này vẫn khớp được với đúng đặc trưng đó ở tỉ lệ khác MÀ KHÔNG CẦN mình tự
# giả định trước hệ số k. Quy trình mới:
#   1. Đặt mốc (`set_reference_region`): dò đặc trưng (keypoint + mô tả nhị
#      phân) trong đúng vùng người dùng chọn, lưu toạ độ keypoint QUY VỀ TÂM
#      VÙNG (để tái sử dụng khi ước lượng phép biến đổi affine ở bước 3).
#   2. Mỗi chu kỳ detect: cắt 1 vùng cửa sổ QUANH vị trí dự kiến (theo k ước
#      lượng gần nhất — chỉ để giới hạn phạm vi tính toán/tránh khớp nhầm
#      sang chỗ khác có hoạ tiết lặp lại, KHÔNG PHẢI để ép đúng tỉ lệ như
#      matchTemplate), dò đặc trưng trong vùng đó rồi khớp với mô tả của
#      mốc bằng BFMatcher (Hamming) + Lowe ratio test.
#   3. Từ các cặp khớp "tốt", ước lượng phép biến đổi đồng dạng (xoay + co
#      giãn + tịnh tiến) bằng `cv2.estimateAffinePartial2D` (RANSAC, tự loại
#      outlier). Hệ số co giãn của phép biến đổi CHÍNH LÀ tỉ lệ k cần tìm —
#      không cần quét bất kỳ giả thuyết k nào.
#   4. Lớp phòng vệ chống khớp nhầm (thay cho "so đỉnh tốt-nhì" của v3, vốn
#      không còn ý nghĩa khi không dò theo lưới k): so khớp về SỐ LƯỢNG (đủ
#      inlier + tỉ lệ inlier/tổng số khớp) VÀ về HÌNH HỌC — mô hình vật lý
#      buộc tâm vùng biến đổi phải nằm ĐÚNG trên tia cố định từ tâm radar
#      tại k vừa tính ra; nếu phép biến đổi RANSAC "đẹp" (nhiều inlier)
#      nhưng tâm biến đổi lệch xa tia đó, vẫn bị từ chối — dấu hiệu khớp
#      nhầm sang 1 cụm đặc trưng khác (vd hoạ tiết lưới lặp lại).
# Mẫu tham chiếu vẫn TỰ LÀM MỚI mỗi khi khớp đủ tin cậy (giữ nguyên lý do từ
# v3: tránh phải bắc cầu 1 bước xa từ mẫu rất cũ khi zoom đi xa dần), và
# danh sách tỉ lệ "thường gặp" (`KNOWN_KM_PX`, đo trực tiếp trên
# phong_to.mp4 — xem CLAUDE.md) vẫn giữ nguyên làm ứng viên dự phòng cuối
# cùng khi dò trực tiếp thất bại, chỉ đổi cách khớp từng ứng viên sang
# feature matching thay vì matchTemplate.
# ══════════════════════════════════════════════════════════════════════════════
REF_FEATURE_ALGO    = "ORB"    # "ORB" (nhanh, mac dinh) hoac "AKAZE" (cham hon,
                                # khong gian ty le phi tuyen, co the on dinh hon
                                # tren man radar net manh/it texture) - doi 1
                                # dong nay de thu thuat toan khac.
REF_ORB_NFEATURES   = 1200
REF_AKAZE_THRESHOLD = 0.0006   # AKAZE mac dinh (0.001) qua chat cho man radar
                                # nen den/net manh - ha xuong de co du keypoint.

def _create_feature_detector():
    if REF_FEATURE_ALGO == "AKAZE":
        if hasattr(cv2, "AKAZE_create"):
            return cv2.AKAZE_create(threshold=REF_AKAZE_THRESHOLD)
        return cv2.xfeatures2d.AKAZE_create(threshold=REF_AKAZE_THRESHOLD)  # build khac
    return cv2.ORB_create(nfeatures=REF_ORB_NFEATURES)

_feature_detector = _create_feature_detector()
_feature_matcher  = cv2.BFMatcher(cv2.NORM_HAMMING)   # ORB va AKAZE(MLDB) deu la mo ta nhi phan

def _detect_features(gray, mask=None):
    return _feature_detector.detectAndCompute(gray, mask)

def _radar_mask(shape):
    """Mat na hinh tron ~vong 300km, dung khi do TOAN KHUNG HINH (fallback) de
    tranh dinh dac trung vao panel thong tin/chu o ngoai vung radar."""
    h, w = shape[:2]
    m = np.zeros((h, w), np.uint8)
    cv2.circle(m, (CX, CY), int(R_300KM * 1.05), 255, -1)
    return m

REF_RATIO_TEST        = 0.75   # nguong Lowe's ratio test (knnMatch k=2)
REF_MIN_TEMPLATE_KP   = 6      # duoi muc nay coi nhu khong the khop, tu choi dat moc
REF_WARN_TEMPLATE_KP  = 20     # duoi muc nay van nhan nhung canh bao truoc
REF_MIN_MATCHES       = 8      # so cap khop qua ratio test toi thieu de thu RANSAC
REF_MIN_INLIERS       = 6      # so inlier RANSAC toi thieu de xem xet chap nhan
REF_MIN_INLIER_RATIO  = 0.35   # ty le inlier/so khop toi thieu
REF_POS_TOL_FACTOR    = 0.6    # sai so vi tri toi da (x kich thuoc mau hien tai) giua
                                # tam mau bien doi qua affine va tia CX->offset0 du
                                # kien tai k tinh duoc - lop phong ve hinh hoc, xem
                                # giai thich o khoi docstring tren.

REF_SEARCH_MARGIN  = 2.0    # vung cat de do "quanh uoc luong gan nhat" rong gap may
                             # lan kich thuoc mau du kien - khong can dung tuyet doi
                             # (khac matchTemplate) vi ban than ORB/AKAZE da co kim tu
                             # thap ty le, vung cat chi de gioi han pham vi tinh/tranh
                             # khop nham noi khac co hoa tiet lap lai.
REF_SEARCH_MIN_DIM = 80
REF_SEARCH_MAX_DIM = 800

REF_TEMPLATE_MIN_DIM      = 20    # px - khong lam moi neu mau moi se qua nho
REF_TEMPLATE_MAX_DIM      = 480   # px - khong lam moi neu mau moi se qua lon (ORB/AKAZE
                                   # tren 1 crop ~480x480 van rat re, nen cho phep mau lon
                                   # hon muc 320 cua ban matchTemplate cu de mo rong dai
                                   # zoom con bam duoc truoc khi cham "tran" kim tu thap
                                   # ty le cua bo do dac trung)
# (Da bo REF_REFRESH_MIN_INLIERS/REF_REFRESH_INLIER_RATIO — truoc day lam moi
# mau doi hoi nguong CHAT HON nguong chap nhan thuong, nhung do thuc te tren
# zoom THAT (khong phai warpAffine tong hop): 1 lan zoom THAT co the chi cho
# 1-2 chu ky detect voi diem vua du nguong chap nhan (vd 50-55%, 6-7 inlier)
# truoc khi video zoom tiep sang muc khac — khong bao gio du "dep" de dat
# nguong lam moi rieng. He qua: mau KHONG kip lam moi trong luc zoom nhanh
# qua nhieu muc lien tiep (vd 360->180->90 trong <1s that o phong_to.mp4),
# roi khi toi muc cuoi phai bac cau 1 buoc GAP TO (vd 4x) tu mau CU thay vi
# GAP NHO (vd 2x) tu mau da lam moi — that bai hoan toan, "mat bam vinh vien"
# dung nhu bao cao thuc te. Fix: LAM MOI NGAY MOI LAN CHAP NHAN 1 ket qua (du
# qua nhanh/via_known), khong doi diem cao hon nua — lop phong ve hinh hoc
# (REF_POS_TOL_FACTOR) da dam bao ket qua chap nhan la dung vi tri, nen lam
# moi ngay khong lam tang rui ro khop sai, chi giup buoc nhay ke tiep LUON
# gan hon.

REF_K_MIN      = 0.05   # he so co gian nho nhat so voi luc dat moc (zoom in manh)
REF_K_MAX      = 20.0   # he so co gian lon nhat so voi luc dat moc (zoom out manh)
REF_JUMP_RATIO = 1.15   # ty le km/px doi > 15% giua 2 lan cap nhat => coi la video vua zoom

# ── Ty le km/px "thuong gap" — do truc tiep tren phong_to.mp4 bang thuoc ti
# le co san cua phan mem (xem CLAUDE.md de biet chi tiet cach do): 360 Km ->
# 0.6803 km/px, 180 Km -> 0.3401 km/px, 90 Km -> 0.1701 km/px. Dung nhu 1
# "diem neo" khi ket qua do moc truc tiep roi vao GAN 1 trong 3 muc nay -
# KHONG thay the co che moc (van la fallback cho moi truong hop/muc zoom
# khac chua do duoc).
KNOWN_KM_PX     = [0.6803, 0.3401, 0.1701]
KNOWN_KM_PX_TOL = 0.08

def _snap_known_km_px(value):
    for k in KNOWN_KM_PX:
        if abs(value / k - 1.0) < KNOWN_KM_PX_TOL:
            return k
    return value

# Nguong rieng cho "ung vien da biet" (KNOWN_KM_PX) — THAP hon
# REF_MIN_INLIERS/REF_MIN_INLIER_RATIO thuong vi day la fallback cuoi cung,
# chi can du de PHAN BIET GIUA CAC UNG VIEN VOI NHAU (danh sach rat ngan, 3
# gia tri) — khong can chinh xac tuyet doi nhu dò truc tiep.
KNOWN_CANDIDATE_MIN_INLIERS = 5
KNOWN_CANDIDATE_MARGIN      = 0.08   # chenh ty le inlier toi thieu voi ung vien tot-nhi

_ref = {"active": False, "kp_local": None, "des": None, "template_size": None,
        "template_k": 1.0, "offset0": None, "real_km": None, "k_est": 1.0,
        "last_score": 0.0, "last_margin": 0.0, "manual": False, "via_known": False}

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
    nhiều chi tiết càng nhiều keypoint/khớp chắc chắn, tránh chọn mảng trơn/
    chỉ có lưới (dò đặc trưng trên mảng trơn gần như không ra keypoint nào,
    khác matchTemplate cũ vẫn "khớp" được dù mập mờ)."""
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
    region = gray[y0:y1, x0:x1]
    region_mask = _non_blip_mask(frame)[y0:y1, x0:x1]
    kp, des = _detect_features(region, region_mask)
    n_kp = 0 if kp is None else len(kp)
    if des is None or n_kp < REF_MIN_TEMPLATE_KP:
        print(f"\n[MOC] Vung chon qua it dac trung ({n_kp} keypoint, can >= "
              f"{REF_MIN_TEMPLATE_KP}) — khong the dat moc, chon vung co net/hinh "
              "dang ro hon (bo bien, dao, chu...).", flush=True)
        return False
    if n_kp < REF_WARN_TEMPLATE_KP:
        print(f"\n[MOC] CANH BAO: vung chon it dac trung ({n_kp} keypoint) — de mat "
              "dau khi zoom manh, nen chon vung lon hon/nhieu chi tiet hon neu co the.",
              flush=True)
    rw, rh = x1 - x0, y1 - y0
    rcx, rcy = rw / 2.0, rh / 2.0
    kp_local = np.array([[p.pt[0] - rcx, p.pt[1] - rcy] for p in kp], dtype=np.float32)
    _ref = {
        "active": True, "kp_local": kp_local, "des": des, "template_size": (rw, rh),
        "template_k": 1.0, "offset0": (cx_sel - CX, cy_sel - CY),
        "real_km": dist_px * KM_PX, "k_est": 1.0, "last_score": 1.0, "last_margin": float(n_kp),
        "manual": False, "via_known": False,
    }
    print(f"\n[MOC] Da dat moc vung ({x0},{y0})-({x1},{y1})  {n_kp} dac trung "
          f"({REF_FEATURE_ALGO})  tam vung cach tam {dist_px:.0f}px = "
          f"{_ref['real_km']:.1f}km  (ty le hien tai {KM_PX:.4f} km/px)", flush=True)
    return True

# ══════════════════════════════════════════════════════════════════════════════
# TỰ ĐỘNG CHỌN MỐC THAM CHIẾU — quét các vùng cửa sổ ứng viên trong bán kính
# `AUTO_REF_RADIUS_KM` quanh tâm radar, LOẠI các vùng dính nhiều màu icon mục
# tiêu (HSV_RANGES) vì đó là vật CHUYỂN ĐỘNG chứ không phải chi tiết cố định
# — mốc phải là bờ biển/đảo/chữ nhãn... đứng yên, không phải máy bay — rồi
# trong số các ứng viên còn đủ đặc trưng ORB/AKAZE (`AUTO_REF_MIN_KP`), CHỌN
# ỨNG VIÊN NHIỀU ĐẶC TRƯNG NHẤT.
#
# Vì sao 50km là bán kính hợp lý: nhỏ đủ để LUÔN nằm sâu trong vòng radar ở
# MỌI mức zoom thực tế của phần mềm (90/180/360 Km — xem KNOWN_KM_PX) — không
# bao giờ chạm biên khung hình hay panel thông tin bên phải (chỉ xuất hiện ở
# x lớn, xa tâm hơn nhiều so với 50km ngay cả khi zoom vào sâu), nên không
# cần thêm luật loại trừ riêng cho panel như khi chọn tay.
#
# ── Điều tra "mất bám khi phóng to và thu nhỏ" (user báo lại sau khi thêm
# tự động chọn mốc) — ĐÃ SỬA MỘT PHẦN, còn 1 giới hạn CHƯA giải quyết được ──
# Tái hiện bằng test trên khung hình THẬT của `phong_to.mp4` qua 2 lần chuyển
# zoom thật (360→180→90 và 90→180→360, mỗi lần chỉ cách nhau vài giây, dừng
# rất ngắn ở mức 180 — đúng kiểu "zoom dồn dập" mà CLAUDE.md mục lịch sử v3
# từng ghi nhận là CHƯA kiểm chứng):
#   • Zoom VÀO (360→180→90): đã XÁC NHẬN SỬA ĐƯỢC — xem "Fix: LÀM MỚI mẫu
#     ngay khi CHẤP NHẬN" ở dưới (nguyên nhân là mẫu không kịp làm mới trong
#     khoảng zoom trung gian rất ngắn, phải bắc cầu 1 bước xa quá khả năng).
#   • Zoom RA (90→180→360): VẪN mất bám ở bước chuyển đầu tiên dù đã có fix
#     trên. Thử giả thuyết "mốc quá gần tâm bị nhiễu bởi lưới tia hội tụ dày"
#     (xác nhận bằng so sánh trực quan 2 khung hình thật tại ĐÚNG 1 vị trí:
#     cùng 1 vùng nhỏ có RẤT nhiều tia lưới cắt qua khi zoom ra, ít tia khi
#     zoom vào — vì lưới là các tia toả đều góc từ tâm, càng gần tâm càng
#     hội tụ dày trên 1 diện tích nhỏ) bằng cách đổi tiêu chí auto-pick sang
#     ưu tiên ứng viên XA TÂM NHẤT thay vì nhiều đặc trưng nhất — kết quả
#     THỰC NGHIỆM không nhất quán: có ứng viên xa tâm cải thiện chút ít (số
#     inlier trong lúc chuyển tăng, dù vẫn chưa đủ ngưỡng), nhưng có ứng viên
#     KHÁC lại chỉ toàn lưới + máy bay (gần như không có chi tiết bờ biển
#     thật), tệ hơn hẳn — và tệ nhất, áp dụng lại vào ĐÚNG kịch bản zoom VÀO
#     đã sửa ở trên thì lại chọn trúng 1 vị trí xa tâm nhưng theo dõi tệ hơn,
#     gây "mất bám" MỚI ở đúng chỗ trước đó đã ổn. Kết luận: ưu tiên khoảng
#     cách là 1 heuristic GIÁN TIẾP và không đáng tin cậy bằng ưu tiên số
#     lượng đặc trưng (phản ánh TRỰC TIẾP có chi tiết thật hay không) — ĐÃ
#     REVERT về ưu tiên nhiều đặc trưng nhất như thiết kế gốc.
# Nghi vấn còn lại (chưa kiểm chứng, chỉ ghi nhận): phần mềm map có thể áp
# dụng ĐỘ RỘNG NÉT VẼ TỐI THIỂU cố định theo pixel màn hình cho các đường
# mảnh (bờ biển...) bất kể mức zoom — nếu đúng, khi zoom RA, nét vẽ không co
# lại đúng tỉ lệ hình học như mô hình co giãn đều mà toàn bộ hệ mốc đang giả
# định, khiến nội dung LỆCH khỏi 1 phép biến đổi đồng dạng thuần tuý theo
# đúng hướng zoom ra — có thể là giới hạn VẬT LÝ của cách phần mềm vẽ lại,
# không phải lỗi thuật toán khớp. Lối thoát thực dụng hiện có (giống hệt các
# giới hạn zoom đã ghi nhận ở v3): giữ CHUỘT GIỮA đặt lại mốc, hoặc bấm
# '-'/'=' chỉnh tay, ngay khi thanh trạng thái báo "không chắc chắn" kéo dài
# sau 1 lần zoom ra.
# ══════════════════════════════════════════════════════════════════════════════
AUTO_REF_RADIUS_KM     = 50.0  # ban kinh quet ung vien moc, tinh tu tam radar
AUTO_REF_MIN_DIST_PX   = 45    # khoang cach toi thieu tu tam - giu du "don bay"
                                # de uoc luong k chinh xac (giong tinh than kiem
                                # tra dist_px<20 luc chon tay o set_reference_region)
AUTO_REF_WIN_SIZES     = (220, 160, 120)  # thu kich thuoc LON truoc (nhieu chi
                                           # tiet hon = khop chac hon), nho dan
                                           # neu khong vung nao du dac trung
AUTO_REF_STEP_FRAC     = 0.6   # buoc luoi quet = kich thuoc cua so * he so nay
AUTO_REF_MIN_KP        = 40    # so keypoint toi thieu de chap nhan 1 ung vien -
                                # cao hon REF_WARN_TEMPLATE_KP vi tu dong chon
                                # nen doi hoi chat luong tot ngay tu dau
                                # giai thich o tren, XA TAM moi la tieu chi chinh)

def _blip_color_mask(frame):
    """Mặt nạ hợp toàn bộ pixel thuộc màu icon mục tiêu quy định (HSV_RANGES)
    trong khung hình."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    m = np.zeros(frame.shape[:2], np.uint8)
    for ranges in HSV_RANGES.values():
        for lo, hi in ranges:
            m = cv2.bitwise_or(m, cv2.inRange(hsv, np.array(lo), np.array(hi)))
    return m

def _non_blip_mask(frame):
    """Mặt nạ 255 ở MỌI nơi TRỪ pixel màu icon mục tiêu (đảo ngược của
    `_blip_color_mask`) — dùng làm mask cho `_detect_features()` để KHÔNG BAO
    GIỜ đặt 1 keypoint nào lên icon máy bay (vật chuyển động), dù vùng chọn
    (tay hoặc tự động) có vô tình trùm lên 1 phần icon. Tổng quát hơn cách cũ
    (loại cả 1 vùng cửa sổ nếu tỉ lệ pixel màu icon vượt ngưỡng): chỉ loại
    ĐÚNG pixel dính icon, giữ lại toàn bộ chi tiết tĩnh còn lại trong cùng
    cửa sổ."""
    return cv2.bitwise_not(_blip_color_mask(frame))

def auto_pick_reference_region(frame, radius_km=AUTO_REF_RADIUS_KM):
    """Tự động quét các vùng cửa sổ ứng viên trong bán kính `radius_km` quanh
    tâm radar, chấm điểm bằng số lượng đặc trưng ORB/AKAZE, loại ứng viên
    dính nhiều màu icon mục tiêu, rồi đặt mốc tham chiếu tại ứng viên tốt
    nhất bằng `set_reference_region()`. Trả về True nếu tìm được và đặt
    thành công, False nếu không có ứng viên nào đủ tốt trong bán kính này
    (nên fallback sang hướng dẫn người dùng tự chọn bằng CHUỘT GIỮA)."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    non_blip = _non_blip_mask(frame)
    h, w = gray.shape[:2]
    radius_px = radius_km / KM_PX

    best = None   # (dist, n_kp, x0, y0, x1, y1)
    for win in AUTO_REF_WIN_SIZES:
        half = win / 2.0
        # Buoc luoi phai du NHO so voi ban kinh (khong chi so voi kich thuoc cua
        # so) — neu khong, khi radius_km nho hon nua kich thuoc cua so (vd 50km
        # ~vai chuc px trong khi cua so 220px), luoi qua thua co the chi roi
        # dung vao 4 GOC cua hop bao (cach tam xa hon ca ban kinh, do
        # sqrt(2)*radius) va khong bao gio lot vao trong hinh tron — dam bao
        # it nhat ~8 buoc chia doc theo duong kinh de luoi thuc su quet duoc
        # phan trong cua hinh tron.
        step = max(4, min(int(win * AUTO_REF_STEP_FRAC), max(int(radius_px / 4), 4)))
        gx_lo, gx_hi = int(max(half, CX - radius_px)), int(min(w - half, CX + radius_px))
        gy_lo, gy_hi = int(max(half, CY - radius_px)), int(min(h - half, CY + radius_px))
        for gy in range(gy_lo, gy_hi + 1, step):
            for gx in range(gx_lo, gx_hi + 1, step):
                d = np.hypot(gx - CX, gy - CY)
                if d > radius_px or d < AUTO_REF_MIN_DIST_PX:
                    continue
                x0, y0 = int(gx - half), int(gy - half)
                x1, y1 = int(gx + half), int(gy + half)
                if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
                    continue
                kp, des = _detect_features(gray[y0:y1, x0:x1], non_blip[y0:y1, x0:x1])
                n_kp = 0 if des is None else len(kp)
                if n_kp < AUTO_REF_MIN_KP:
                    continue
                # Uu tien ung vien NHIEU dac trung nhat (khong phai xa tam
                # nhat — da THU uu tien xa tam de tranh nhieu luoi gan tam,
                # nhung kiem chung thuc te tren zoom that cho ket qua LAN LON
                # (co luc tot hon, co luc lai chon nham 1 vung gan nhu trong,
                # chi co luoi + may bay, KEM hon ca chon theo nhieu dac trung
                # — xem lich su sua doi phia tren). So luong dac trung phan
                # anh TRUC TIEP viec co chi tiet THAT (bo bien/dao) hay khong,
                # dang tin cay hon 1 heuristic gian tiep nhu khoang cach.
                if best is None or n_kp > best[1]:
                    best = (d, n_kp, x0, y0, x1, y1)
        if best is not None:
            break   # da tim duoc o kich thuoc lon nhat co the - khong can thu nho hon
    if best is None:
        print(f"\n[MOC-TU-DONG] Khong tim duoc vung nao du dac trung trong {radius_km:.0f}km "
              "quanh tam - hay giu CHUOT GIUA keo chon vung thu cong.", flush=True)
        return False
    d, n_kp, x0, y0, x1, y1 = best
    print(f"\n[MOC-TU-DONG] Tim thay vung {x1-x0}x{y1-y0}px ({n_kp} dac trung, cach tam "
          f"{d:.0f}px) trong {radius_km:.0f}km quanh tam.", flush=True)
    return set_reference_region(frame, x0, y0, x1, y1)

def _crop_bounds_for_k(k, shape):
    """Vùng cửa sổ dự kiến cần đặt 1 vật có kích thước mẫu tại hệ số k, nới
    rộng hơn (REF_SEARCH_MARGIN) để chịu được bước nhảy k giữa 2 chu kỳ
    detect — KHÔNG cần chính xác tuyệt đối như matchTemplate vì ORB/AKAZE tự
    nó đã có kim tự tháp tỉ lệ, vùng cắt chỉ để giới hạn phạm vi tính/tránh
    khớp nhầm nơi khác có hoạ tiết lặp lại."""
    ox0, oy0 = _ref["offset0"]
    tw, th = _ref["template_size"]
    pcx, pcy = CX + ox0 * k, CY + oy0 * k
    rel = k / _ref["template_k"]
    ew = min(max(tw * rel, REF_SEARCH_MIN_DIM) * REF_SEARCH_MARGIN, REF_SEARCH_MAX_DIM)
    eh = min(max(th * rel, REF_SEARCH_MIN_DIM) * REF_SEARCH_MARGIN, REF_SEARCH_MAX_DIM)
    h, w = shape[:2]
    return (max(0, pcx - ew / 2), max(0, pcy - eh / 2),
            min(w, pcx + ew / 2), min(h, pcy + eh / 2))

def _ref_match(gray, x0, y0, x1, y1, mask=None):
    """Dò đặc trưng trong vùng (x0,y0)-(x1,y1), khớp với mô tả của mốc bằng
    BFMatcher + Lowe ratio test, rồi ước lượng phép biến đổi đồng dạng
    (RANSAC) từ các cặp khớp tốt. Trả về dict {k, scale_rel, inliers,
    matches, ratio, center} hoặc None nếu không đủ dữ liệu để ước lượng."""
    h, w = gray.shape[:2]
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(w, int(x1)), min(h, int(y1))
    if x1 - x0 < REF_TEMPLATE_MIN_DIM or y1 - y0 < REF_TEMPLATE_MIN_DIM or _ref["des"] is None:
        return None
    crop = gray[y0:y1, x0:x1]
    crop_mask = mask[y0:y1, x0:x1] if mask is not None else None
    kp, des = _detect_features(crop, crop_mask)
    if des is None or len(kp) < 2:
        return None
    matches = _feature_matcher.knnMatch(_ref["des"], des, k=2)
    good = []
    for pair in matches:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < REF_RATIO_TEST * n.distance:
            good.append(m)
    if len(good) < REF_MIN_MATCHES:
        return None
    ref_pts = np.float32([_ref["kp_local"][m.queryIdx] for m in good]).reshape(-1, 1, 2)
    cur_pts = np.float32([(kp[m.trainIdx].pt[0] + x0, kp[m.trainIdx].pt[1] + y0)
                           for m in good]).reshape(-1, 1, 2)
    M, inlier_mask = cv2.estimateAffinePartial2D(ref_pts, cur_pts, method=cv2.RANSAC,
                                                  ransacReprojThreshold=4.0, confidence=0.99)
    if M is None or inlier_mask is None:
        return None
    inliers = int(inlier_mask.sum())
    if inliers < 3:
        return None
    scale = float(np.hypot(M[0, 0], M[1, 0]))
    if scale <= 0:
        return None
    return {
        "k": scale * _ref["template_k"], "scale_rel": scale,
        "inliers": inliers, "matches": len(good), "ratio": inliers / len(good),
        "center": (float(M[0, 2]), float(M[1, 2])),
    }

def _ref_evaluate(result):
    """Chấp nhận 1 kết quả từ `_ref_match` hay không: đủ CẢ VỀ SỐ LƯỢNG
    (inlier + tỉ lệ inlier/tổng số khớp) LẪN VỀ HÌNH HỌC (tâm mẫu biến đổi
    phải nằm GẦN tia CX→offset0 tại k vừa tính — ràng buộc vật lý của bài
    toán zoom quanh 1 tâm cố định; nếu lệch xa, nghi khớp nhầm sang 1 cụm
    đặc trưng khác dù inlier "đẹp"). Trả về (ok: bool, ratio: float)."""
    if result is None:
        return False, 0.0
    if result["inliers"] < REF_MIN_INLIERS or result["ratio"] < REF_MIN_INLIER_RATIO:
        return False, result["ratio"]
    ox0, oy0 = _ref["offset0"]
    k = result["k"]
    pred_cx, pred_cy = CX + ox0 * k, CY + oy0 * k
    cur_cx, cur_cy = result["center"]
    pos_err = float(np.hypot(cur_cx - pred_cx, cur_cy - pred_cy))
    tw, th = _ref["template_size"]
    tol = REF_POS_TOL_FACTOR * max(tw, th) * result["scale_rel"]
    if pos_err > tol:
        return False, result["ratio"]
    return True, result["ratio"]

def _ref_refresh_template(gray, k, mask=None):
    """Chụp lại keypoint/mô tả MỚI ngay tại vị trí/tỉ lệ hiện tại (`k`) — giữ
    mẫu luôn "bám sát" tỉ lệ gần nhất vừa xác nhận được, tránh phải so 1
    bước nhảy xa từ mẫu rất cũ/rất khác tỉ lệ khi video zoom đi xa dần (lý
    do giống hệt v3, xem docstring khối trên). `mask` (nếu có, xem
    `_non_blip_mask`) loại pixel màu icon mục tiêu khỏi mẫu mới, tránh mẫu
    dính vào 1 máy bay đang đứng gần đúng vị trí mốc lúc làm mới."""
    ox0, oy0 = _ref["offset0"]
    tw0, th0 = _ref["template_size"]
    rel = k / _ref["template_k"]
    new_w, new_h = tw0 * rel, th0 * rel
    if not (REF_TEMPLATE_MIN_DIM <= new_w <= REF_TEMPLATE_MAX_DIM and
            REF_TEMPLATE_MIN_DIM <= new_h <= REF_TEMPLATE_MAX_DIM):
        return
    ncx, ncy = CX + ox0 * k, CY + oy0 * k
    nx0, ny0 = int(round(ncx - new_w / 2)), int(round(ncy - new_h / 2))
    nx1, ny1 = int(round(ncx + new_w / 2)), int(round(ncy + new_h / 2))
    h, w = gray.shape[:2]
    if not (0 <= nx0 and 0 <= ny0 and nx1 <= w and ny1 <= h and
            nx1 - nx0 >= REF_TEMPLATE_MIN_DIM and ny1 - ny0 >= REF_TEMPLATE_MIN_DIM):
        return
    region = gray[ny0:ny1, nx0:nx1]
    region_mask = mask[ny0:ny1, nx0:nx1] if mask is not None else None
    kp, des = _detect_features(region, region_mask)
    if des is None or len(kp) < REF_MIN_TEMPLATE_KP:
        return   # giu mau cu, khong du dac trung de lam moi
    rw, rh = nx1 - nx0, ny1 - ny0
    rcx, rcy = rw / 2.0, rh / 2.0
    _ref["kp_local"]      = np.array([[p.pt[0] - rcx, p.pt[1] - rcy] for p in kp], dtype=np.float32)
    _ref["des"]           = des
    _ref["template_size"] = (rw, rh)
    _ref["template_k"]    = k

def update_scale_from_reference(frame):
    """Dò lại vùng mốc bằng feature matching (xem khối docstring phía trên):
    ưu tiên tìm quanh ước lượng k gần nhất trước (vùng cắt rộng, không phải
    lưới k như v3), mở rộng dò TOÀN KHUNG HÌNH (masked theo vòng radar) khi
    lân cận thất bại, rồi thử các tỉ lệ "thường gặp" (KNOWN_KM_PX) khi cả 2
    bước trên đều thất bại. Chỉ chấp nhận khi đủ tin cậy (`_ref_evaluate`).
    Cập nhật KM_PX toàn cục, trả về True nếu tỉ lệ vừa đổi ĐÁNG KỂ (video vừa
    zoom) — nơi gọi cần reset StaticNoiseFilter."""
    global KM_PX
    if not _ref["active"] or _ref["manual"]:
        return False
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Loai pixel mau icon muc tieu khoi ca dò lan lam moi mau — 1 may bay dang
    # bay ngang qua vung mốc khong duoc phep gop keypoint gia vao ket qua
    # khop (xem _non_blip_mask).
    non_blip = _non_blip_mask(frame)

    # 1) Do QUANH uoc luong k gan nhat truoc (zoom that doi dan qua nhieu chu
    # ky, khong nhay coc) — 1 lan do duy nhat la du, khong can quet nhieu gia
    # thuyet k nhu matchTemplate (xem docstring khoi tren).
    x0, y0, x1, y1 = _crop_bounds_for_k(_ref["k_est"], gray.shape)
    result = _ref_match(gray, x0, y0, x1, y1, mask=non_blip)
    ok, ratio = _ref_evaluate(result)
    via_known = False

    # 2) Mo rong TOAN KHUNG HINH (masked theo vong radar) — mat dau / moi dat moc.
    if not ok:
        h, w = gray.shape[:2]
        wide_mask = cv2.bitwise_and(non_blip, _radar_mask(gray.shape))
        wide = _ref_match(gray, 0, 0, w, h, mask=wide_mask)
        wide_ok, wide_ratio = _ref_evaluate(wide)
        if wide is not None and (result is None or wide["inliers"] > result["inliers"]):
            result, ok, ratio = wide, wide_ok, wide_ratio

    # 3) Ung vien ty le "thuong gap" — giong tinh than co che matchTemplate cu
    # nhung khop bang dac trung: khoanh vung quanh vi tri du kien cua TUNG gia
    # tri KNOWN_KM_PX roi khop rieng, chi chap nhan khi ung vien tot nhat VUOT
    # RO ung vien tot-nhi TRONG CHINH DANH SACH DA BIET (khong so voi ket qua
    # o buoc 1/2 — danh sach nay rat ngan (3 gia tri), so voi dò tu do la
    # khap khieng, giong ly do da ghi nhan o v3).
    if not ok:
        dist_px_capture = float(np.hypot(*_ref["offset0"]))
        kk = []
        for kmpx in KNOWN_KM_PX:
            if kmpx <= 0:
                continue
            k_theory = _ref["real_km"] / (dist_px_capture * kmpx)
            if not (REF_K_MIN <= k_theory <= REF_K_MAX):
                continue
            bx0, by0, bx1, by1 = _crop_bounds_for_k(k_theory, gray.shape)
            r = _ref_match(gray, bx0, by0, bx1, by1, mask=non_blip)
            if r is None or r["inliers"] < KNOWN_CANDIDATE_MIN_INLIERS:
                continue
            r_ok, _r_ratio = _ref_evaluate(r)
            kk.append((r["ratio"], r, kmpx, r_ok))
        kk.sort(key=lambda t: t[0], reverse=True)
        if kk:
            best_ratio, best_r, best_kmpx, best_ok = kk[0]
            second_ratio = kk[1][0] if len(kk) >= 2 else -1.0
            if best_ok and (best_ratio - second_ratio) >= KNOWN_CANDIDATE_MARGIN:
                result, ok, ratio, via_known = best_r, True, best_ratio, True
                print(f"\r[MOC] Nhan dien ty le thuong gap ({best_kmpx:.4f} km/px, "
                      f"inlier={best_r['inliers']} ty le={best_ratio*100:.0f}% "
                      f"chenh ung vien con lai={best_ratio - second_ratio:.2f})          ",
                      end="", flush=True)

    _ref["last_score"]  = ratio
    _ref["last_margin"] = float(result["inliers"]) if result else 0.0
    _ref["via_known"]   = via_known

    if not ok or result is None:
        print("\r[MOC] Dang tim lai moc...                                   ", end="", flush=True)
        return False

    _ref["k_est"] = float(result["k"])

    # Làm mới mẫu tham chiếu ngay khi CHẤP NHẬN 1 kết quả (không đòi ngưỡng
    # riêng cao hơn nữa — xem lý do ở khối docstring trên REF_TEMPLATE_MAX_DIM):
    # giữ mẫu luôn "bám sát" tỉ lệ vừa xác nhận, để bước nhảy kế tiếp (nếu
    # video zoom tiếp ngay) luôn XUẤT PHÁT GẦN, không phải bắc cầu xa từ mẫu cũ.
    _ref_refresh_template(gray, result["k"], mask=non_blip)

    dist_px_capture = float(np.hypot(*_ref["offset0"]))
    new_dist_px = dist_px_capture * result["k"]
    if new_dist_px < 5 or KM_PX <= 0:
        return False
    new_km_px = _snap_known_km_px(_ref["real_km"] / new_dist_px)
    ratio_change = new_km_px / KM_PX
    KM_PX = new_km_px

    if not via_known:
        print(f"\r[MOC] OK  inlier={result['inliers']}/{result['matches']} "
              f"({result['ratio']*100:.0f}%)  k={result['k']:.2f}          ", end="", flush=True)

    return not (1 / REF_JUMP_RATIO < ratio_change < REF_JUMP_RATIO)

# ══════════════════════════════════════════════════════════════════════════════
# NHẬN DIỆN SỐ HIỆU (ID) MỤC TIÊU — đọc nhãn số trắng cạnh icon bằng EasyOCR
# ══════════════════════════════════════════════════════════════════════════════
# User yêu cầu: đọc số hiệu (ID) thật của từng mục tiêu — phần mềm ATC vẽ 1
# nhãn số nhỏ màu TRẮNG (không phải màu icon) cạnh mỗi icon mục tiêu (vd
# "027", "14128", "620 (B)"...), khớp đúng số hiệu trong bảng "Số hiệu" bên
# trái màn hình.
#
# Đã thử 3 hướng, chốt hướng 3:
# 1. Model YOLOv8 đã train sẵn trong project (`runs/ocr/weights/best.pt`,
#    dùng bởi infer_ocr.py cho mục đích khác trước đây) — test trực tiếp
#    trên nhãn thật của nguồn USB capture card: đọc SAI hoàn toàn ("027"
#    → "916") — model train trên font/nguồn khác (có thể thucte.mp4), không
#    tổng quát được sang font của phần mềm ATC này.
# 2. Tự xây bộ so khớp mẫu (template matching) cho từng chữ số 0-9, cắt trực
#    tiếp từ nhãn thật (đo được font là MONOSPACE, ~5.8-6px/ký tự — xác nhận
#    bằng cách đo tỉ lệ độ rộng nhãn/số ký tự trên nhiều nhãn khác nhau, luôn
#    ra cùng 1 hằng số). Test trên dữ liệu thật: độ chính xác THẤP VÀ KHÔNG
#    ỔN ĐỊNH (0-4/9 đúng tuỳ đợt) dù đã tăng số lượng mẫu train từ 1-6 lên
#    2-14 mẫu/chữ số — cho thấy nút thắt không phải "thiếu dữ liệu" mà là
#    GIỚI HẠN ĐỘ PHÂN GIẢI thật sự: mỗi ký tự chỉ ~5-8px sau nén tín hiệu
#    capture card, không đủ chi tiết để tự xây bộ so khớp đáng tin cậy.
# 3. **EasyOCR** (model tổng quát đã huấn luyện sẵn, cài qua pip — máy đã có
#    sẵn cache model ở `~/.EasyOCR` từ trước) — test cùng bộ dữ liệu thật:
#    6-7/13 đúng HOÀN TOÀN tuỳ tham số crop/upscale (tốt nhất đo được:
#    pad=12px, phóng to 6 lần trước khi đưa vào EasyOCR — dùng ảnh MÀU gốc,
#    KHÔNG nhị phân hoá bằng mask trắng/đen trước, vì mất chi tiết
#    anti-alias mà EasyOCR tận dụng được: đã đo, nhị phân hoá làm giảm từ
#    6/13 xuống 3/13). Các lần "sai" đa số vẫn RẤT GẦN đáp án đúng (thiếu 1
#    ký tự, hoặc dư 1 ký tự ở đầu) — khác hẳn kiểu sai "ngẫu nhiên hoàn
#    toàn" của bộ tự xây. MỘT SỐ lỗi lặp lại CÓ HỆ THỐNG cho 1 số cặp ký tự
#    cụ thể (vd "6"→"0"), nghĩa là lấy đa số phiếu qua nhiều lần đọc (xem
#    dưới) sẽ KHÔNG sửa được các lỗi này — đây là giới hạn đã biết, không
#    phải bug.
#
# EasyOCR chạy TRÊN CPU mất ~350ms/lần đọc — QUÁ CHẬM để chạy mỗi chu kỳ
# detect (166-333ms) trong vòng lặp chính, nên chạy trong LUỒNG NỀN RIÊNG
# (giống `_global_auto_worker`): lần lượt đọc thử nhãn của từng track CHƯA
# "chốt" được ID, tích luỹ số phiếu đọc TRÙNG NHAU (`_ocr_votes`), chốt khi 1
# kết quả đạt `OCR_VOTE_CONFIRM` phiếu (giúp lọc bớt sai số ngẫu nhiên qua
# nhiều lần đọc độc lập — nhưng KHÔNG sửa được lỗi đọc sai có hệ thống nêu
# trên). Vị trí nhãn KHÔNG cố định 1 hướng so với icon (phần mềm tự đặt nhãn
# tránh chồng lấn) nên mỗi lần đọc phải tự dò cụm chữ trắng gần icon nhất
# trong bán kính `OCR_SEARCH_RADIUS`, không giả định 1 offset cố định.
OCR_SEARCH_RADIUS    = 45    # px — bán kính quanh icon để tìm cụm chữ trắng
OCR_CROP_PAD         = 12    # px — đệm quanh nhãn trước khi upscale (đo tốt nhất)
OCR_UPSCALE          = 6     # hệ số phóng to trước khi đưa vào EasyOCR
OCR_VOTE_CONFIRM     = 3     # số phiếu đọc TRÙNG NHAU tối thiểu để "chốt" ID
# BUG đã sửa: user báo "không thấy nhận diện được ID" sau khi chạy thật — đo
# lại bằng test end-to-end thật (luồng nền chạy song song với TrackManager
# thật, không chỉ gọi hàm rời rạc): với ~20-50 track (thực tế đo được:
# "Tổng 26" mục tiêu + track tạm auto-scan), 1 VÒNG quét hết tất cả track
# mất RẤT LÂU vì `OCR_ATTEMPT_INTERVAL=0.4` cũ là THỜI GIAN NGHỈ THÊM sau
# mỗi lần đọc — CỘNG DỒN vào ~350ms EasyOCR đã tốn sẵn, thành ~750ms/track
# thay vì 400ms như dự tính (hiểu nhầm: tưởng 0.4s đã BAO GỒM luôn thời gian
# đọc, thực ra là nghỉ THÊM sau đó). Với 26 track: 1 vòng ≈ 26×0.75s ≈ 19.5s
# — cần ÍT NHẤT 3 vòng liên tiếp mới có cơ hội chốt 1 track (nếu đọc trúng
# liên tục, thực tế cần nhiều vòng hơn vì độ chính xác ~50%/lần), tức là
# HÀNG PHÚT mới thấy ID đầu tiên xuất hiện — dễ hiểu lầm là "không hoạt
# động". Fix: hạ xuống 0.05s (chỉ đủ nhường CPU cho luồng chính, không cộng
# dồn đáng kể vào ~350ms đã có sẵn của chính lệnh gọi EasyOCR) — 1 vòng 26
# track còn ≈ 26×0.4s ≈ 10.4s, nhanh hơn ~2 lần.
OCR_ATTEMPT_INTERVAL = 0.05  # giây nghỉ giữa 2 lần đọc (CHỈ để nhường CPU —
                             # bản thân mỗi lần gọi EasyOCR đã mất ~350ms rồi)

_ocr_reader           = None
_ocr_votes            = {}   # tid -> {text: so_phieu}
_ocr_confirmed        = {}   # tid -> text đã chốt
_latest_frame_for_ocr = [None]

def display_id(tid):
    """ID hiển thị: ưu tiên số hiệu ĐÃ ĐỌC ĐƯỢC qua OCR (nếu có), nếu không
    thì theo quy tắc cũ (tid do user đặt tên, hoặc '???' nếu track auto chưa
    đặt tên)."""
    ocr_id = _ocr_confirmed.get(tid)
    if ocr_id:
        return ocr_id
    return tid if not tid.startswith("?") else "???"

def _white_text_mask(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, np.array([0, 0, 80]), np.array([180, 100, 255]))

def _find_label_near(frame, cx, cy, radius=OCR_SEARCH_RADIUS):
    """Tìm cụm chữ trắng (nghi là nhãn số hiệu) gần (cx,cy) nhất trong bán
    kính `radius` quanh vị trí icon — trả về hộp bao (x0,y0,x1,y1) trong toạ
    độ khung hình gốc, hoặc None nếu không thấy cụm nào đủ lớn (>=2 ký tự)."""
    h, w = frame.shape[:2]
    x0s, x1s = max(0, cx - radius), min(w, cx + radius)
    y0s, y1s = max(0, cy - radius), min(h, cy + radius)
    if x1s <= x0s or y1s <= y0s:
        return None
    region = _white_text_mask(frame)[y0s:y1s, x0s:x1s]
    dilated = cv2.dilate(region, np.ones((2, 2), np.uint8), iterations=1)
    n, _lbl, stats, centroids = cv2.connectedComponentsWithStats(dilated, 8)
    chars = []
    for i in range(1, n):
        bx0, by0, bw, bh, area = stats[i]
        if area < 3 or area > 400:
            continue
        # BUG đã sửa: các chữ số trong 1 nhãn hay DÍNH LIỀN thành 1 component
        # duy nhất sau dilate (đo thực tế: nhãn "027" luôn ra 2 component,
        # không phải 3, vì 2 chữ số dính nhau) — ngưỡng bw cũ (14px, nghĩ là
        # "1 ký tự đơn lẻ") loại bỏ NHẦM cả nhãn đã dính liền thành 1 khối
        # rộng ~19-32px (3-5 chữ số). Nới bw lên 45 (đủ chứa 1 nhãn 5 chữ số
        # dính liền hoàn toàn) — hàm này chỉ cần XÁC ĐỊNH VÙNG nhãn để cắt
        # cho EasyOCR đọc cả cụm, không cần tách riêng từng ký tự như lúc
        # xây template thủ công.
        if bw > 45 or bh > 16 or bw < 2 or bh < 4:
            continue
        chars.append((bx0, by0, bw, bh, int(centroids[i][0]), int(centroids[i][1])))
    if not chars:
        return None
    chars.sort(key=lambda c: (c[5], c[4]))
    used = [False] * len(chars)
    groups = []
    for i in range(len(chars)):
        if used[i]:
            continue
        grp = [chars[i]]; used[i] = True
        changed = True
        while changed:
            changed = False
            for j in range(len(chars)):
                if used[j]:
                    continue
                for g in grp:
                    if abs(chars[j][4] - g[4]) < 15 and abs(chars[j][5] - g[5]) < 8:
                        grp.append(chars[j]); used[j] = True; changed = True
                        break
        # Chấp nhận cả cụm chỉ có 1 component NẾU nó đủ rộng (>=8px — nhiều
        # khả năng là cả nhãn đã dính liền thành 1 khối, không phải 1 chấm
        # nhiễu lẻ loi) — xem giải thích ở đoạn lọc `chars` phía trên.
        if len(grp) >= 2 or grp[0][2] >= 8:
            groups.append(grp)
    if not groups:
        return None
    local_cx, local_cy = cx - x0s, cy - y0s
    def grp_center(g):
        xs = [c[0] for c in g] + [c[0]+c[2] for c in g]
        ys = [c[1] for c in g] + [c[1]+c[3] for c in g]
        return (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    best = min(groups, key=lambda g: sum(v*v for v in
               (grp_center(g)[0]-local_cx, grp_center(g)[1]-local_cy)))
    xs = [c[0] for c in best] + [c[0]+c[2] for c in best]
    ys = [c[1] for c in best] + [c[1]+c[3] for c in best]
    return (x0s+min(xs), y0s+min(ys), x0s+max(xs), y0s+max(ys))

def _ocr_read_bbox(frame, bbox):
    global _ocr_reader
    if _ocr_reader is None:
        _ocr_reader = easyocr.Reader(['en'], gpu=False)
    x0, y0, x1, y1 = bbox
    h, w = frame.shape[:2]
    pad = OCR_CROP_PAD
    cx0, cy0 = max(0, x0-pad), max(0, y0-pad)
    cx1, cy1 = min(w, x1+pad), min(h, y1+pad)
    crop = frame[cy0:cy1, cx0:cx1]
    if crop.size == 0:
        return None
    big = cv2.resize(crop, (crop.shape[1]*OCR_UPSCALE, crop.shape[0]*OCR_UPSCALE),
                      interpolation=cv2.INTER_CUBIC)
    try:
        result = _ocr_reader.readtext(big, allowlist="0123456789")
    except Exception:
        return None
    text = "".join(r[1] for r in result)
    return text if text else None

OCR_MAX_ATTEMPTS = 8    # số lần đọc tối đa trước khi CHỐT TẠM theo đa số
                        # phiếu hiện có (dù chưa đạt OCR_VOTE_CONFIRM) — nếu
                        # không, 1 track có phiếu rải rác đều (không lần nào
                        # trùng đủ OCR_VOTE_CONFIRM) sẽ bị đọc MÃI MÃI không
                        # bao giờ chốt, tốn tài nguyên vô ích và không bao
                        # giờ hiển thị ID dù đã đọc rất nhiều lần.
_ocr_attempts = {}     # tid -> tổng số lần đã thử đọc (kể cả không ra chữ)

def _id_ocr_worker(stop_evt, tm_ref):
    """Luồng nền: lần lượt thử đọc nhãn số hiệu của từng track CHƯA chốt ID.
    Không chạy trong vòng lặp chính vì EasyOCR quá chậm (~350ms/lần trên CPU)."""
    while not stop_evt.is_set():
        frame = _latest_frame_for_ocr[0]
        if frame is None:
            stop_evt.wait(1.0)
            continue
        pending = [(tid, info) for tid, info in list(tm_ref.tracks.items())
                   if tid not in _ocr_confirmed]
        if not pending:
            stop_evt.wait(1.0)
            continue
        for tid, info in pending:
            if stop_evt.is_set():
                break
            hist = info.get("history")
            if not hist:
                continue
            _, xkm, ykm, _, _ = hist[-1]
            cx, cy = to_px(xkm, ykm)
            bbox = _find_label_near(frame, cx, cy)
            votes = _ocr_votes.setdefault(tid, {})
            if bbox is not None:
                text = _ocr_read_bbox(frame, bbox)
                # Lọc "hợp lý": mọi số hiệu thật quan sát được trên phần
                # mềm này đều dài 3 hoặc 5 ký tự (025-029/611-623/881-885 và
                # mã 14xxx) — loại ngay các chuỗi quá dài/quá ngắn (vd
                # "1445088", "88", "61") thay vì cho vào vòng bầu chọn, vì
                # đó gần như chắc chắn là đọc dính sang nhãn/hoạ tiết khác
                # bên cạnh chứ không phải 1 số hiệu thật bị đọc lệch vài ký
                # tự — tránh "chốt chắc chắn" 1 kết quả rõ ràng vô lý.
                if text and len(text) in (3, 5):
                    votes[text] = votes.get(text, 0) + 1
            _ocr_attempts[tid] = _ocr_attempts.get(tid, 0) + 1
            best_text, best_n = (None, 0)
            for t, n in votes.items():
                if n > best_n:
                    best_text, best_n = t, n
            if best_n >= OCR_VOTE_CONFIRM or _ocr_attempts[tid] >= OCR_MAX_ATTEMPTS:
                if best_text:
                    _ocr_confirmed[tid] = best_text
                    tag = "chac chan" if best_n >= OCR_VOTE_CONFIRM else "tam (het luot doc)"
                    print(f"\n[OCR] {tid}: so hieu = {best_text} ({tag}, {best_n}/{_ocr_attempts[tid]} phieu)",
                          flush=True)
                else:
                    # Chưa từng đọc ra chữ nào sau đủ số lượt — bỏ cuộc,
                    # tránh luồng nền cứ quay lại thử vô ích mỗi vòng.
                    _ocr_confirmed[tid] = ""
            stop_evt.wait(OCR_ATTEMPT_INTERVAL)

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
    did   = display_id(tid)

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
        _ref_ok = (_ref["last_score"] >= REF_MIN_INLIER_RATIO and
                   _ref["last_margin"] >= REF_MIN_INLIERS)
        mcol = (0, 255, 180) if (_ref["via_known"] or _ref_ok) else (0, 120, 255)
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
        ref_txt = (f"MOC: {KM_PX:.4f} km/px  (ty le thuong gap, inlier={int(_ref['last_margin'])} "
                   f"ty le khop={_ref['last_score']*100:.0f}%)")
        ref_col = (0,200,255)
    elif _ref["last_score"] >= REF_MIN_INLIER_RATIO and _ref["last_margin"] >= REF_MIN_INLIERS:
        ref_txt = (f"MOC: {KM_PX:.4f} km/px  (inlier={int(_ref['last_margin'])} "
                   f"ty le khop={_ref['last_score']*100:.0f}%)")
        ref_col = (0,200,255)
    else:
        ref_txt = (f"MOC: khong chac chan (inlier={int(_ref['last_margin'])} "
                   f"ty le khop={_ref['last_score']*100:.0f}%) — km/px cu: {KM_PX:.4f}  "
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
        did   = display_id(tid)
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
                   "named": not tid.startswith("?"),
                   "display_id": display_id(tid),
                   "ocr_id": _ocr_confirmed.get(tid)}
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
        did   = display_id(tid)
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
# NGUỒN LAN — mở luồng RTSP/HTTP, và hỏi địa chỉ nếu không truyền qua dòng lệnh
# ══════════════════════════════════════════════════════════════════════════════
def _open_lan_capture(url):
    """Mở luồng LAN qua backend FFMPEG trước (chuẩn cho rtsp://, http://...);
    một số luồng MJPEG/HTTP đơn giản chỉ mở được bằng backend mặc định của
    OpenCV nên fallback lại nếu FFMPEG không mở được."""
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(url)
    return cap

def _prompt_lan_url():
    """Hỏi địa chỉ luồng LAN qua dialog tkinter đơn giản. Trả về chuỗi rỗng
    nếu người dùng huỷ."""
    root = tk.Tk()
    root.title("Nhập địa chỉ luồng LAN")
    root.geometry("560x170")
    root.configure(bg="#111")
    root.attributes("-topmost", True)

    tk.Label(root, text="Địa chỉ luồng video qua mạng LAN (RTSP/HTTP):",
             bg="#111", fg="#00dddd", font=("Consolas", 11, "bold")).pack(anchor="w", padx=14, pady=(16, 4))
    tk.Label(root, text="vd: rtsp://192.168.1.50:8554/radar  hoặc  http://192.168.1.50:8080/video",
             bg="#111", fg="#888888", font=("Consolas", 9)).pack(anchor="w", padx=14)

    entry_var = tk.StringVar()
    entry = tk.Entry(root, textvariable=entry_var, width=58, font=("Consolas", 10),
                      bg="#1a1a1a", fg="#dddddd", insertbackground="#dddddd")
    entry.pack(padx=14, pady=12, fill="x")
    entry.focus_set()

    result = {"value": ""}

    def on_ok(_event=None):
        result["value"] = entry_var.get().strip()
        root.destroy()

    def on_cancel():
        root.destroy()

    entry.bind("<Return>", on_ok)
    btn_frame = tk.Frame(root, bg="#111")
    btn_frame.pack(fill="x", padx=14, pady=(0, 14))
    tk.Button(btn_frame, text="Kết nối", width=12, bg="#005555", fg="#ffffff",
              font=("Consolas", 10), relief="flat", command=on_ok).pack(side="right", padx=4)
    tk.Button(btn_frame, text="Huỷ", width=12, bg="#553300", fg="#ffffff",
              font=("Consolas", 10), relief="flat", command=on_cancel).pack(side="right", padx=4)

    root.mainloop()
    return result["value"]

# ══════════════════════════════════════════════════════════════════════════════
# CHUYỂN TỌA ĐỘ CLICK TOÀN CỤC (pynput, toạ độ màn hình vật lý) → FRAME SPACE
# ══════════════════════════════════════════════════════════════════════════════
def click_to_frame(sx, sy, fs_mon, frame_shape):
    fh, fw = frame_shape[:2]
    fl, ft = fs_mon["left"], fs_mon["top"]
    fw_d, fh_d = fs_mon["width"], fs_mon["height"]
    if fl <= sx < fl + fw_d and ft <= sy < ft + fh_d:
        return int((sx - fl) * fw / fw_d), int((sy - ft) * fh / fh_d)
    return None

# ══════════════════════════════════════════════════════════════════════════════
# CHẠY PIPELINE RADAR TỪ LUỒNG MẠNG LAN (RTSP/HTTP) — thay cho thiết bị
# USB/HDMI capture card vật lý của v4 (`run_radar_from_capture`). Giữ lại
# toàn bộ pipeline nâng cao (mốc tỉ lệ ORB/AKAZE tự-làm-mới, 3 lớp lọc
# nhiễu) — vì nguồn thật (phần mềm ATC) qua LAN vẫn có thể đổi tầm quan sát
# (zoom) giữa chừng giống hệt phong_to.mp4/capture card.
#
# Click chuột bắt qua HOOK TOÀN CỤC (pynput) thay vì cv2.setMouseCallback cục
# bộ: cửa sổ chạy true fullscreen (`cv2.WINDOW_FULLSCREEN`) trên đúng monitor
# xuất hình ra ngoài — kế thừa nguyên nhân từ radar_live_2.py (bấm chuột lúc
# cửa sổ ở chế độ này không phải lúc nào Qt/HighGUI cũng chuyển sự kiện click
# về đúng callback cục bộ). Đây CŨNG CHÍNH LÀ cơ chế đảm bảo xử lý không phụ
# thuộc cửa sổ có đang được OS focus hay không khi người dùng chuyển sang
# tab/cửa sổ khác trên máy phân tích (xem docstring đầu file). Vị trí con trỏ
# (để hiện tooltip khi rê chuột, không cần bấm) vẫn dùng cv2.setMouseCallback
# bình thường — chỉ MOVE mới cần, không phải click, nên không gặp vấn đề trên.
#
# Khác biệt DUY NHẤT so với `run_radar_from_capture`: nguồn là 1 URL mạng nên
# có thể rớt kết nối tạm thời — vòng lặp chính đếm số lần đọc lỗi LIÊN TIẾP,
# chủ động đóng + mở lại kết nối sau ngưỡng `LAN_READ_FAIL_RECONNECT`, và
# trong lúc chờ backoff giữa các lần thử vẫn bơm cửa sổ (`cv2.waitKey(30)`
# từng đợt ngắn) để không bị Windows coi là "Not Responding" và vẫn nhận
# được phím Q/Esc để thoát.
# ══════════════════════════════════════════════════════════════════════════════
def run_radar_from_lan(url):
    device_label = f"LAN: {url}"
    cap = _open_lan_capture(url)
    if not cap.isOpened():
        print(f"[LOI] Khong mo duoc luong LAN: {url}")
        return
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 1 or fps > 120:
        fps = float(TARGET_FPS)

    ok, first = cap.read()
    if not ok or first is None:
        print("[LOI] Khong doc duoc khung hinh dau tien tu luong LAN.")
        cap.release()
        return
    actual_h, actual_w = first.shape[:2]
    print(f"[OK] Nguon: {device_label}  {actual_w}x{actual_h}  ~{fps:.0f}fps bao cao")

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
        f"Nguồn mới ({device_label}) có thể có bố cục khác — "
        f"nếu không chắc, bấm Không để chỉnh lại.",
        parent=_root,
    )
    _root.destroy()

    if not _keep:
        calibrate_radar_center(first, fs_mon)

    # ── Mốc tỉ lệ (zoom): thử TỰ ĐỘNG chọn trước (quét trong AUTO_REF_RADIUS_KM
    # quanh tâm, xem auto_pick_reference_region()) — chỉ hỏi người dùng tự
    # chọn bằng CHUỘT GIỮA nếu tự động không tìm được vùng nào đủ đặc trưng.
    _auto_ok = auto_pick_reference_region(first)

    _root = tk.Tk(); _root.withdraw(); _root.attributes("-topmost", True)
    if _auto_ok:
        tkinter.messagebox.showinfo(
            "Mốc tỉ lệ (zoom)",
            f"Đã TỰ ĐỘNG chọn 1 mốc tham chiếu tỉ lệ (trong {AUTO_REF_RADIUS_KM:.0f}km "
            "quanh tâm radar, xem dấu X + đường nối trên màn hình).\n\n"
            "Nếu nguồn này cũng đổi tầm quan sát (zoom) giữa chừng — hệ thống sẽ tự "
            "tính lại tỉ lệ km/px mỗi khi cảnh zoom, dựa trên mốc này.\n\n"
            "Nếu thấy mốc không chắc chắn (thanh trạng thái dưới màn hình báo), "
            "hoặc muốn đổi sang 1 chi tiết khác: giữ CHUỘT GIỮA và KÉO ra 1 vùng "
            "mới quanh chi tiết cố định khác (bờ biển, đảo, chữ nhãn...) — không "
            "phải máy bay — rồi thả chuột để xác nhận.\n\n"
            "NẾU TỰ ĐỘNG VẪN SAI: bấm phím '-' hoặc '=' để CHỈNH TAY tỉ lệ km/px "
            "trực tiếp (mỗi lần bấm nhích ±3%) — vừa bấm vừa quan sát mục tiêu đã "
            "xác nhận trên màn có khớp đúng vị trí blip thật không. Một khi đã "
            "chỉnh tay, hệ thống tự động sẽ TẮT (không tự ghi đè nữa) cho tới khi "
            "đặt mốc mới.",
            parent=_root)
    else:
        tkinter.messagebox.showinfo(
            "Mốc tỉ lệ (zoom)",
            f"Không tự động tìm được vùng nào đủ đặc trưng trong "
            f"{AUTO_REF_RADIUS_KM:.0f}km quanh tâm — cần chọn TAY.\n\n"
            "Giữ CHUỘT GIỮA và KÉO ra một VÙNG quanh 1 chi tiết CỐ ĐỊNH (bờ biển, "
            "đảo, chữ nhãn...) — không phải máy bay — rồi thả chuột để xác nhận. "
            "Chọn vùng càng lớn/càng nhiều chi tiết rõ càng khớp chắc chắn; tránh "
            "vùng chỉ có nền trơn hoặc chỉ có lưới.\n\n"
            "Hệ thống sẽ tự tính lại tỉ lệ km/px nếu nguồn này đổi tầm quan sát "
            "giữa chừng. Có thể giữ CHUỘT GIỮA kéo chọn lại bất cứ lúc nào nếu "
            "thấy mốc không chắc chắn (thanh trạng thái dưới màn hình sẽ báo).\n\n"
            "NẾU TỰ ĐỘNG VẪN SAI: bấm phím '-' hoặc '=' để CHỈNH TAY tỉ lệ km/px "
            "trực tiếp (mỗi lần bấm nhích ±3%).",
            parent=_root)
    _root.destroy()

    # Audio
    try:
        pygame.mixer.init()
        print("[AUDIO] OK")
    except Exception as e:
        print(f"[AUDIO] Lỗi: {e}")
    threading.Thread(target=_audio_worker, daemon=True).start()

    # pynput — hook toàn cục cho chuột + phím (cửa sổ chạy true fullscreen)
    m_listener = pmouse.Listener(on_click=_on_global_mouse_click, on_move=_on_global_mouse_move)
    m_listener.start()
    k_listener = pkeyboard.Listener(on_press=_on_key_press, on_release=_on_key_release)
    k_listener.start()
    print("[INPUT] Mouse + keyboard listener OK")

    tm             = TrackManager(fps)
    noise_filter   = StaticNoiseFilter()
    table_img      = build_table(tm, 0)
    table_scroll_y = [0]
    _selected_tid  = [None]
    cv_mouse       = [0, 0]

    _ocr_stop = threading.Event()
    if _HAS_EASYOCR:
        threading.Thread(target=_id_ocr_worker, args=(_ocr_stop, tm), daemon=True).start()
        print("[OCR] Luong doc so hieu chay nen OK")
    else:
        print("[OCR] Khong co easyocr — bo qua nhan dien so hieu (pip install easyocr)")

    def on_cv_mouse(event, x, y, flags, param):
        cv_mouse[0], cv_mouse[1] = x, y

    def on_table_scroll(event, x, y, flags, param):
        if event == cv2.EVENT_MOUSEWHEEL:
            step = TABLE_ROW_H * 3
            if flags > 0: table_scroll_y[0] = max(0, table_scroll_y[0] - step)
            else:          table_scroll_y[0] += step

    WIN_MAIN = "Radar Live v5 (LAN)"
    cv2.namedWindow(WIN_MAIN, cv2.WINDOW_NORMAL)
    cv2.moveWindow(WIN_MAIN, fs_mon["left"], fs_mon["top"])
    cv2.setWindowProperty(WIN_MAIN, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback(WIN_MAIN, on_cv_mouse)

    cv2.namedWindow("Bang thong tin", cv2.WINDOW_AUTOSIZE)
    cv2.moveWindow("Bang thong tin", tbl_mon["left"] + 10, tbl_mon["top"] + 10)
    cv2.setMouseCallback("Bang thong tin", on_table_scroll)

    frame_idx = 0
    FRAME_DT  = 1.0 / fps
    fail_count        = 0   # so lan doc frame loi LIEN TIEP tu lan ket noi/doc tot gan nhat
    reconnect_attempt = 0   # so lan da thu mo lai ket noi lien tiep (chon backoff tang dan)

    print(f"[OK] Chay {fps:.1f} fps.  Chuot TRAI: phat   Shift+Trai: bam muc tieu   "
          f"Giu+keo Chuot GIUA: dat moc ty le   Delete: xoa muc tieu   "
          f"Chuot PHAI: ID/hen gio   -/=: chinh tay ty le   Q/Esc: thoat\n")

    _quit = False
    try:
        while True:
            t0 = time.perf_counter()

            ok, frame = cap.read()
            if not ok or frame is None:
                fail_count += 1
                print(f"\r[CANH BAO] Mat tin hieu tu LAN, dang thu lai... (loi lien tiep {fail_count})",
                      end="", flush=True)
                if fail_count >= LAN_READ_FAIL_RECONNECT:
                    backoff = LAN_RECONNECT_BACKOFF[min(reconnect_attempt, len(LAN_RECONNECT_BACKOFF) - 1)]
                    reconnect_attempt += 1
                    fail_count = 0
                    cap.release()
                    print(f"\n[LAN] Dang mo lai ket noi (cho {backoff:.1f}s)...", flush=True)
                    _t_backoff = time.perf_counter()
                    while time.perf_counter() - _t_backoff < backoff:
                        # Van bom cua so + nhan phim Q/Esc trong luc cho, khong dung
                        # 1 lenh time.sleep dai — neu khong, vong lap tu chan chinh
                        # no va cua so se bi Windows bao "Not Responding" du van
                        # dang "xu ly" (dang cho ket noi lai), khong lien quan gi
                        # toi viec cua so co dang focus hay khong.
                        if (cv2.waitKey(30) & 0xFF) in (ord('q'), 27):
                            _quit = True
                            break
                        time.sleep(0.01)
                    if _quit:
                        break
                    cap = _open_lan_capture(url)
                else:
                    if (cv2.waitKey(1) & 0xFF) in (ord('q'), 27):
                        _quit = True
                        break
                    time.sleep(0.2)
                continue
            fail_count = 0
            reconnect_attempt = 0
            frame_idx += 1
            _latest_frame_for_ocr[0] = frame.copy()

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
                print(f"\r  frame={frame_idx}  tracks={len(tm.tracks):3d}  km/px={KM_PX:.4f}", end="", flush=True)

            # ── Chuột TRÁI: button / Shift+Trái bám mục tiêu / Trái phát track ─
            while not _left_click_q_g.empty():
                sx, sy = _left_click_q_g.get_nowait()
                coords = click_to_frame(sx, sy, fs_mon, frame.shape)
                if coords:
                    lx, ly = coords
                    fw_f = frame.shape[1]
                    if fw_f - _BTN_AUTO_W - 4 <= lx <= fw_f - 4 and 0 <= ly <= _BTN_AUTO_H:
                        toggle_global_auto(tm)
                    elif fw_f - 2*_BTN_AUTO_W - 8 <= lx <= fw_f - _BTN_AUTO_W - 8 and 0 <= ly <= _BTN_AUTO_H:
                        toggle_global_auto_slow(tm)
                    elif _shift_state["held"]:
                        color = classify_color_at(frame, lx, ly)
                        if color:
                            nearby = find_nearest_blip(lx, ly, tm, frame_idx,
                                                        radius_mult=SHIFT_CLICK_SKIP_RADIUS / HOVER_RADIUS)
                            if nearby is None:
                                if noise_filter.is_static(color, lx, ly):
                                    print(f"\n[CANH BAO] Vi tri ({lx},{ly}) mau {color} da duoc nhan "
                                          f"dien la nen tinh lau dai (bo bien/dao/luoi) — van tao track "
                                          f"theo yeu cau, kiem tra lai neu day khong phai muc tieu that.",
                                          flush=True)
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
            while not _right_click_q_g.empty():
                sx, sy = _right_click_q_g.get_nowait()
                coords = click_to_frame(sx, sy, fs_mon, frame.shape)
                if coords:
                    lx, ly = coords
                    hit = find_nearest_blip(lx, ly, tm, frame_idx)
                    if hit:
                        show_target_dialog(hit, tm)

            # ── Chuột GIỮA (giữ + kéo): đặt/đặt lại mốc tham chiếu tỉ lệ ─────
            if _mid_drag_g["pending_rect"] is not None:
                (sx0, sy0), (sx1, sy1) = _mid_drag_g["pending_rect"]
                _mid_drag_g["pending_rect"] = None
                c0 = click_to_frame(sx0, sy0, fs_mon, frame.shape)
                c1 = click_to_frame(sx1, sy1, fs_mon, frame.shape)
                if c0 and c1:
                    set_reference_region(frame, c0[0], c0[1], c1[0], c1[1])

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
            drag_preview = None
            if _mid_drag_g["active"] and _mid_drag_g["p0"] is not None:
                c0 = click_to_frame(_mid_drag_g["p0"][0], _mid_drag_g["p0"][1], fs_mon, frame.shape)
                c1 = click_to_frame(_mid_drag_g["p1"][0], _mid_drag_g["p1"][1], fs_mon, frame.shape)
                if c0 and c1:
                    drag_preview = (c0, c1)
            draw_frame(canvas, frame_idx, tm, cv_mouse[0], cv_mouse[1],
                       source_label=device_label, paused=False, drag_rect=drag_preview)

            cv2.imshow(WIN_MAIN, canvas)

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
            elif key == ord('-'):
                nudge_km_px(REF_MANUAL_STEP)      # muc tieu ve GAN tam hon
            elif key == ord('='):
                nudge_km_px(1.0 / REF_MANUAL_STEP)  # muc tieu ve XA tam hon

            elapsed = time.perf_counter() - t0
            if elapsed < FRAME_DT:
                time.sleep(FRAME_DT - elapsed)

    except KeyboardInterrupt:
        pass
    finally:
        m_listener.stop()
        k_listener.stop()
        _ocr_stop.set()
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

    # ── Mốc tỉ lệ (zoom): thử TỰ ĐỘNG chọn trước (quét trong AUTO_REF_RADIUS_KM
    # quanh tâm, xem auto_pick_reference_region()) — chỉ hỏi người dùng tự
    # chọn bằng CHUỘT GIỮA nếu tự động không tìm được vùng nào đủ đặc trưng.
    _auto_ok = auto_pick_reference_region(first)

    _root = tk.Tk(); _root.withdraw(); _root.attributes("-topmost", True)
    if _auto_ok:
        tkinter.messagebox.showinfo(
            "Mốc tỉ lệ (zoom)",
            f"Đã TỰ ĐỘNG chọn 1 mốc tham chiếu tỉ lệ (trong {AUTO_REF_RADIUS_KM:.0f}km "
            "quanh tâm radar, xem dấu X + đường nối trên màn hình).\n\n"
            "Video này có thể phóng to/thu nhỏ giữa chừng — hệ thống sẽ tự tính "
            "lại tỉ lệ km/px mỗi khi cảnh zoom, dựa trên mốc này.\n\n"
            "Nếu thấy mốc không chắc chắn (thanh trạng thái dưới màn hình báo), "
            "hoặc muốn đổi sang 1 chi tiết khác: giữ CHUỘT GIỮA và KÉO ra 1 vùng "
            "mới quanh chi tiết cố định khác (bờ biển, đảo, chữ nhãn...) — không "
            "phải máy bay — rồi thả chuột để xác nhận.\n\n"
            "NẾU TỰ ĐỘNG VẪN SAI: bấm phím '-' hoặc '=' để CHỈNH TAY tỉ lệ km/px "
            "trực tiếp (mỗi lần bấm nhích ±3%) — vừa bấm vừa quan sát mục tiêu đã "
            "xác nhận trên màn có khớp đúng vị trí blip thật không. Một khi đã "
            "chỉnh tay, hệ thống tự động sẽ TẮT (không tự ghi đè nữa) cho tới khi "
            "đặt mốc mới.",
            parent=_root)
    else:
        tkinter.messagebox.showinfo(
            "Mốc tỉ lệ (zoom)",
            f"Không tự động tìm được vùng nào đủ đặc trưng trong "
            f"{AUTO_REF_RADIUS_KM:.0f}km quanh tâm — cần chọn TAY.\n\n"
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

    _ocr_stop = threading.Event()
    if _HAS_EASYOCR:
        threading.Thread(target=_id_ocr_worker, args=(_ocr_stop, tm), daemon=True).start()
        print("[OCR] Luong doc so hieu chay nen OK")
    else:
        print("[OCR] Khong co easyocr — bo qua nhan dien so hieu (pip install easyocr)")

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

    WIN_MAIN = "Radar Live v5 (video)"
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
                _latest_frame_for_ocr[0] = frame.copy()

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
                            if noise_filter.is_static(color, lx, ly):
                                print(f"\n[CANH BAO] Vi tri ({lx},{ly}) mau {color} da duoc nhan "
                                      f"dien la nen tinh lau dai (bo bien/dao/luoi) — van tao track "
                                      f"theo yeu cau, kiem tra lai neu day khong phai muc tieu that.",
                                      flush=True)
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
        _ocr_stop.set()
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
    print("=== RADAR LIVE v5 (nguon LAN) ===\n")

    # Truyen duong dan file video qua tham so dong lenh de phat lai file test
    # (vd de test lai voi phong_to.mp4, giu nguyen tu v4) — truyen 1 dia chi
    # URL (rtsp://, http://...) de ket noi thang toi luong LAN do, khong can
    # qua dialog. Khong truyen gi ca -> hoi dia chi LAN qua dialog tkinter.
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if os.path.exists(arg):
            run_radar_from_video(arg)
            return
        run_radar_from_lan(arg)
        return

    url = _prompt_lan_url()
    if not url:
        print("[HUY] Nguoi dung khong nhap dia chi LAN.")
        return
    run_radar_from_lan(url)

if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass
    main()
