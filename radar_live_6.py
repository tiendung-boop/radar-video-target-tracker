"""
Radar Live v6 (tên ứng dụng/hiển thị: RadarVRS) — fork từ radar_live_4.py,
GIỮ NGUYÊN 100% pipeline của v4
(gồm cả các fix mới nhất: `t_sec` đồng hồ thật thay vì frame_idx/fps, lớp
phòng vệ chống mập mờ trong TrackManager.update(), 2 tối ưu hiệu năng nhỏ,
và "Phát tự động" đọc ngay không chờ Enter) — CHỈ khác đúng 1 điểm: bảng ID
góc trên-trái (`_id_panel`) KHÔNG còn tự động bật lên mỗi khi có mục tiêu
auto-scan mới nữa (trước đây `_global_auto_worker` tự đẩy track vào
`_id_panel_queue`, khiến operator luôn phải gõ/Enter mới "thoát" được bảng
dù âm thanh đã đọc xong) — bảng giờ CHỈ mở khi operator chủ động Shift+Click
hoặc chuột phải vào 1 mục tiêu (`open_id_panel()`, không đổi). Theo yêu cầu
user: giữ `radar_live_4.py` NGUYÊN VẸN làm bản tham chiếu, đưa thay đổi này
vào file fork riêng — xem mục lịch sử tương ứng trong CLAUDE.md.

--- Docstring gốc kế thừa từ v4 (áp dụng y hệt ở đây) ---

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
import math
import threading
import queue
import os
import sys
import subprocess
import time
from PIL import Image, ImageDraw, ImageFont
from pynput import keyboard as pkeyboard
from pynput import mouse as pmouse
import mss
import win32com.client
import pygame
import tkinter as tk
from tkinter import ttk
import tkinter.messagebox

# Ep stdout/stderr sang UTF-8, khong crash neu console dang o code page khac
# (vd cp1251) khong bieu dien duoc dau tieng Viet — da gap that: ban .exe
# chay tu 1 thu muc/console khac thoat ngang giua chung voi UnicodeEncodeError
# ngay o dong print co dau (vd "Tổng tracks") chi vi code page cua console do
# khong ho tro ky tu do. errors="replace" giu app chay tiep, chi in sai/mat
# 1 vai ky tu thay vi crash toan bo tien trinh.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# BUG đã sửa (thay hẳn engine OCR): EasyOCR (PyTorch, deep learning) đã hoạt
# động đúng trên máy dev (8 nhân) và cả 1 PC mini yếu (Wyse 5070) lúc tải
# thấp — nhưng user báo lại: "Phát tự động" tạo ra hàng chục track cùng lúc
# trên PC mini này, sau ĐÚNG 30 PHÚT không đọc được ID nào (kể cả kết quả
# "tạm" sau OCR_MAX_ATTEMPTS=8), đồng thời vòng lặp chính cũng chậm hẳn đi —
# nghi vấn: CPU của PC mini này (Celeron/Pentium, khả năng thiếu tập lệnh
# vector hoá AVX2 mà PyTorch tận dụng nhiều) khiến suy luận mạng neural
# chậm hơn máy dev KHÔNG PHẢI VÀI LẦN mà có thể hàng CHỤC LẦN — không chỉ
# chậm, mà gần như không khả thi khi số track tăng lên. User yêu cầu: đọc ID
# tự động là YÊU CẦU CỐT LÕI, cần tìm hướng THAY THẾ thay vì tắt hẳn.
# Đã thử Tesseract OCR (engine cổ điển, không cần PyTorch/mạng neural lớn —
# LSTM nhỏ, đã tối ưu nhiều năm để chạy tốt trên CPU yếu) — đo trực tiếp
# trên `phong_to.mp4` (máy dev, so sánh CÔNG BẰNG cùng 1 loại nhãn nhỏ
# ~5-8px/ký tự đã dùng để test EasyOCR trước đây): ~137ms/lần đọc (so với
# ~300-700ms của EasyOCR trên CÙNG máy — nhanh hơn ít nhất 2-5 lần ngay cả
# trên phần cứng THUẬN LỢI cho EasyOCR; chênh lệch trên CPU yếu, thiếu AVX2,
# nhiều khả năng còn LỚN HƠN vì Tesseract không phụ thuộc các tập lệnh đó),
# và đọc ra nhiều số hợp lý khớp mẫu số hiệu thật đã biết trước đây (611,
# 025, 617, 14126...) — đủ triển vọng để thay thế. Tesseract chạy `tesseract.exe`
# như 1 TIẾN TRÌNH HỆ ĐIỀU HÀNH RIÊNG mỗi lần gọi (qua `pytesseract`), không
# cùng process/GIL với vòng lặp chính — không cần giới hạn thread như
# `torch.set_num_threads(1)` đã làm cho EasyOCR trước đây.
try:
    import pytesseract
    _HAS_TESSERACT = True
except ImportError:
    _HAS_TESSERACT = False

# BUG đã sửa (đo bằng số liệu THẬT, không suy đoán) — user gửi log
# `[DO-THOI-GIAN]` (build có `ocr_lan_doc=`, xem CLAUDE.md) từ Wyse 5070: so
# `doc_xuly` (đọc frame + chu kỳ detect + phím/chuột — KHÔNG liên quan trực
# tiếp tới OCR) tại CÙNG số track, cửa sổ có `ocr_lan_doc` cao (3-5, luồng
# OCR đang tích cực đọc) LUÔN CAO HƠN ~12ms so với cửa sổ `ocr_lan_doc=0`
# (đối chiếu 4 mức track 20-23, mẫu 8-52 cửa sổ mỗi mức — chênh lệch NHẤT
# QUÁN, không phải nhiễu ngẫu nhiên) — xác nhận đúng giả thuyết tranh chấp
# CPU: mỗi lần đọc, `tesseract.exe` chạy như 1 TIẾN TRÌNH HĐH RIÊNG (không
# cùng process/GIL với vòng lặp chính) ở CÙNG mức ưu tiên NORMAL mặc định
# của Windows như tiến trình chính — trên máy ít nhân (Wyse 5070), tiến
# trình con này tranh CPU trực tiếp với luồng đọc/vẽ/hiển thị chính.
# Fix: hạ mức ưu tiên HĐH của MỖI tiến trình `tesseract.exe` con xuống
# BELOW_NORMAL (không phải IDLE — vẫn được cấp CPU bình thường khi máy rảnh,
# chỉ NHƯỜNG lại khi có tranh chấp thật với luồng NORMAL khác) — `pytesseract`
# có tham số `nice` nhưng CHỈ hoạt động trên POSIX (`if not_windows and nice
# != 0` trong `pytesseract.pytesseract.run_tesseract()` — kiểm tra trực tiếp
# trong mã nguồn, Windows luôn bỏ qua). Vá `subprocess_args()` (hàm nội bộ
# `pytesseract` trả về dict kwargs truyền thẳng cho `subprocess.Popen()`
# trong `run_tesseract()`) để thêm `creationflags=BELOW_NORMAL_PRIORITY_CLASS`
# — đủ để hạ ưu tiên MỌI lệnh gọi Tesseract sau đó mà không cần viết lại
# toàn bộ phần gọi tiến trình con (đọc/ghi file tạm, dựng dòng lệnh...) của
# chính `pytesseract`.
if _HAS_TESSERACT and sys.platform == "win32":
    _orig_pytesseract_subprocess_args = pytesseract.pytesseract.subprocess_args
    def _low_priority_subprocess_args(*_args, **_kwargs):
        kw = _orig_pytesseract_subprocess_args(*_args, **_kwargs)
        kw["creationflags"] = kw.get("creationflags", 0) | subprocess.BELOW_NORMAL_PRIORITY_CLASS
        return kw
    pytesseract.pytesseract.subprocess_args = _low_priority_subprocess_args

try:
    _PIL_FONT    = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf",   18)
    _PIL_FONT_BD = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 18)
    # Tiêu đề bảng ID (_draw_id_panel) — chữ Việt CÓ DẤU (vd "ĐỊCH") không
    # thể vẽ bằng cv2.putText (font Hershey không có dấu tiếng Việt, đúng lý
    # do toàn bộ chữ còn lại trong app viết không dấu) — dùng PIL như
    # draw_tooltip() đã làm, cỡ chữ +2px so với _PIL_FONT_BD theo yêu cầu.
    _PIL_FONT_BD_20 = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 20)
except Exception:
    _PIL_FONT = _PIL_FONT_BD = _PIL_FONT_BD_20 = ImageFont.load_default()

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
# BUG đã sửa: user báo "lâu lâu lại tự mất" — điều tra bằng dữ liệu THẬT từ
# USB capture card (chạy TrackManager.update() thật liên tục 90-150s, log mỗi
# lần 1 track không khớp được blip nào dù cùng màu có mặt gần đó). Xác nhận
# NGUYÊN NHÂN CHÍNH (77/94 ≈ 82% số lần mất khớp có dữ liệu): mục tiêu thật
# trên phần mềm này cập nhật vị trí THEO TỪNG BƯỚC RỜI RẠC mỗi 5-11+ giây
# (đã ghi nhận từ trước, xem StaticNoiseFilter/OCR) — trong lúc đứng yên,
# `get_velocity()` fit ra vận tốc ≈0 (đúng), nên `_predict_pixel_pos()` dự
# đoán = vị trí cũ; nhưng ngay khi mục tiêu NHẢY sang vị trí mới, dự đoán vẫn
# "đóng băng" ở vị trí CŨ (vì chưa có điểm lịch sử mới để fit lại) — nếu
# khoảng nhảy vượt `ASSOC_DIST=30px` thì mất khớp NGAY, và vì dự đoán không
# tự cập nhật khi vẫn mất khớp, nó tiếp tục mất khớp mọi chu kỳ sau đó tới
# khi chạm `MAX_LOST` và bị XOÁ HẲN — đúng triệu chứng "tự mất". Đo khoảng
# cách thật (77 mẫu, USB capture card, nhiều màu): min=30 p25=35.6 median=54.5
# p75=88.7 **p90=124.8 max=131.5**px — ASSOC_DIST=30 quá hẹp so với bước
# nhảy thật. Fix: thêm `ASSOC_DIST_WIDE` — vòng dự phòng CÙNG MÀU bán kính
# rộng hơn hẳn, chỉ áp dụng cho track đã trượt ÍT NHẤT 1 chu kỳ đầy đủ (dùng
# lại đúng guard đã có cho vòng dự phòng khác màu — 1 lần mất khớp thoáng qua
# do nhiễu/che khuất không nên lập tức nhảy xa). Chọn 150px (> p90 đo được,
# gần max) — vẫn nhỏ hơn khoảng cách tối thiểu giữa 2 mục tiêu THẬT khác nhau
# từng đo được trong đội hình đông (xem BLIP_MERGE_RADIUS/SHIFT_CLICK_SKIP_RADIUS
# — dù có thể gần hơn 150px trong trường hợp cực đoan, thuật toán "global
# nearest-pair" vẫn ưu tiên cặp gần nhau nhất nên rủi ro khớp nhầm chỉ tăng
# nhẹ, đổi lại tránh được phần lớn (82%) trường hợp mất track thật).
ASSOC_DIST_WIDE = 150

# BUG đã báo (user, phiên sau): "báo ID 616 nhưng điểm bám lạc chỗ khác" —
# đúng triệu chứng đã nghi ngờ trước đây (xem [TRACK-MATCH-RONG-CHAN-DOAN],
# đã gỡ log đo thời gian nhưng GIỮ LẠI log chẩn đoán này) — track hiện đúng
# tên/ID (không đổi, vì display_id() độc lập với vị trí) NHƯNG marker
# (px_last = to_px() của hist[-1]) vẽ SAI CHỖ vì `TrackManager.update()` đã
# ghép NHẦM 1 blip khác (không phải mục tiêu thật của track đó) vào lịch sử —
# xảy ra ở CHÍNH 2 vòng dự phòng (khác màu hẹp, cùng màu rộng
# ASSOC_DIST_WIDE) vì cả 2 chỉ kích hoạt khi track đã "trượt" (dự đoán đóng
# băng, kém tin cậy hơn hẳn vòng 1) — trong đội hình đông (đo được: 2 mục
# tiêu thật có thể cách nhau chỉ ~13-16px, xem BLIP_MERGE_RADIUS), bán kính
# rộng 150px của vòng 3 có thể trùm nhiều blip cùng màu cùng lúc; thuật toán
# "global nearest-pair" vẫn gán track cho blip GẦN NHẤT dù blip đó KHÔNG
# THỰC SỰ rõ ràng hơn hẳn 1 blip khác gần đó — dễ "đoán nhầm" mà không có
# cách nào tự biết đã đoán nhầm.
# Fix: thêm lớp phòng vệ chống mập mờ (cùng tinh thần "so đỉnh tốt-nhì" đã
# dùng cho mốc tỉ lệ ORB/AKAZE) — CHỈ áp dụng cho 2 vòng dự phòng (không đụng
# vòng 1, vốn đã đủ tin cậy vì dự đoán còn "tươi"): 1 cặp (blip,track) chỉ
# được coi là đủ rõ ràng nếu KHÔNG có track nào khác cạnh tranh đúng blip đó,
# LẪN KHÔNG có blip nào khác cạnh tranh đúng track đó, với khoảng cách gần
# tương đương — nếu mập mờ, THÀ track tạm "đứng hình" (giữ marker ở vị trí
# CŨ, thử khớp lại chu kỳ sau) CÒN HƠN nhảy sang đúng 1 mục tiêu khác trong
# khi vẫn hiển thị ID cũ (gây hiểu lầm nguy hiểm hơn hẳn trong "tác chiến").
ROUND_AMBIG_MARGIN_PX = 20    # px — chênh lệch tuyệt đối tối thiểu với ứng
                               # viên gần-nhì để coi là KHÔNG mập mờ. Nhỏ hơn
                               # ASSOC_DIST_WIDE=150 nhiều nhưng LỚN HƠN
                               # khoảng cách tối thiểu đo được giữa 2 mục
                               # tiêu thật khác nhau (~13-16px) — chỉ từ chối
                               # khi 2 ứng viên THỰC SỰ ở gần nhau kiểu hình
                               # học, không từ chối oan khi chúng chỉ tình cờ
                               # cùng lọt vào bán kính rộng nhưng cách xa nhau.
ROUND_AMBIG_MIN_RATIO = 1.3   # hoặc ứng viên gần-nhì phải xa hơn ÍT NHẤT 30%

def _filter_ambiguous_pairs(pairs):
    """Loại (d, bi, tid) khỏi 1 vòng khớp DỰ PHÒNG nếu có ứng viên KHÁC
    trong CHÍNH danh sách `pairs` này cạnh tranh (cùng bi hoặc cùng tid) ở
    khoảng cách gần tương đương — xem docstring trên ROUND_AMBIG_MARGIN_PX.
    Chỉ dùng cho vòng 2/3 (không dùng cho vòng 1, xem lý do trên)."""
    dists_by_bi, dists_by_tid = {}, {}
    for d, bi, tid in pairs:
        dists_by_bi.setdefault(bi, []).append(d)
        dists_by_tid.setdefault(tid, []).append(d)
    for lst in dists_by_bi.values():
        lst.sort()
    for lst in dists_by_tid.values():
        lst.sort()

    def _unambiguous(d, lst):
        if len(lst) < 2:
            return True
        second = lst[1] if abs(lst[0] - d) < 1e-9 else lst[0]
        return (second - d) >= ROUND_AMBIG_MARGIN_PX or second >= d * ROUND_AMBIG_MIN_RATIO

    return [(d, bi, tid) for d, bi, tid in pairs
            if _unambiguous(d, dists_by_bi[bi]) and _unambiguous(d, dists_by_tid[tid])]

TAIL_LEN     = 25
PRED_SEC     = 30
HOVER_RADIUS  = 22
GLOBAL_RADIUS = 150      # km — bán kính cho "Phát tự động"

# Vòng tròn NHẠT quanh mục tiêu ĐÃ XÁC NHẬN (reviewed=True) — LỊCH SỬ: từng bị
# bỏ HẲN qua nhiều lần chỉnh (xem docstring trong draw_frame(), khối "Lịch sử
# vòng khoanh màu") vì vòng tròn cũ vẽ ĐÚNG màu track full-saturation
# (COLOR_MAP), same solid color as chính icon bên dưới → "che đi màu mục
# tiêu"/"lấn áp" (chữ dùng của user). User yêu cầu THÊM LẠI, nhưng lần này
# pha LOÃNG màu track về phía trắng (không phải 1 màu cố định chung cho mọi
# track) — giữ được tín hiệu "đây là track màu gì" nhưng đủ nhạt để KHÔNG che
# lấp icon/màu thật bên dưới, khác hẳn phiên bản cũ đã gây rối mắt.
RING_RADIUS_PX  = 13   # px — nhỏ hơn HOVER_RADIUS, đủ ôm quanh icon (~15-24px)
RING_LIGHTEN    = 0.55 # 0..1 — tỉ lệ pha về trắng (0=giữ nguyên màu track,
                        # 1=trắng hoàn toàn)
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

# User gửi log THẬT (nhiều `[AUTO-CONFIRM-CHAN-DOAN] ... CANH BAO: track KHAC
# MAU`) cho thấy dedup CÙNG MÀU (`SHIFT_CLICK_SKIP_RADIUS`, ngay trên) không
# đủ — 6/~20 lần xác nhận trong 1 đoạn log có 1 track MÀU KHÁC đứng RẤT gần
# (3.6px, 5.0px, 7.8px, 11.4px, 14.0px, 22.5px). Đối chiếu với khoảng cách
# TỐI THIỂU THẬT đo được giữa 2 MỤC TIÊU KHÁC NHAU (~13-16px, dùng để hiệu
# chỉnh `SHIFT_CLICK_SKIP_RADIUS`/`BLIP_MERGE_RADIUS` từ trước) — các ca dưới
# ~10px (3.6/5.0/7.8px) KHÔNG THỂ là 2 mục tiêu thật khác nhau (dưới hẳn
# khoảng cách tối thiểu đã đo), chắc chắn là 2 track cho CÙNG 1 vật (thật hay
# nhiễu) — an toàn để chặn tạo trùng lặp ở khoảng cách NÀY mà KHÔNG lặp lại
# rủi ro đã cân nhắc trước đây khi cố tình KHÔNG dedup theo mọi màu (rủi ro
# đó chỉ áp dụng cho khoảng cách ~13-16px+, nơi 2 mục tiêu thật khác màu có
# thể đứng gần nhau hợp lệ — xem lịch sử "2 bug đã sửa gây bám mất định kỳ").
# Dùng CHUNG giá trị 10px với SHIFT_CLICK_SKIP_RADIUS/BLIP_MERGE_RADIUS (cùng
# biên độ an toàn đã kiểm chứng, dưới hẳn 13-16px) — chỉ áp dụng cho candidate
# KHÁC MÀU với track hiện có (dedup CÙNG MÀU vẫn dùng SHIFT_CLICK_SKIP_RADIUS
# như cũ, không đổi).
CROSS_COLOR_DEDUP_RADIUS_PX = 10

DEFAULT_VIDEO = "phong_to.mp4"

# Nguồn USB/HDMI capture card (mặc định khi chạy không kèm đường dẫn video) —
# lấy NGUYÊN khung hình gốc của thiết bị, không crop/scale, giống radar_live_2.py
TARGET_FPS      = 15     # fps giả định khi thiết bị không báo cáo fps hợp lệ
MAX_VIDEO_PROBE = 6      # số index tối đa dò tìm thiết bị video capture
CAPTURE_W, CAPTURE_H = 1920, 1080   # yêu cầu độ phân giải cao khi mở thiết bị
                                     # (DirectShow mặc định 640x480 nếu không set,
                                     # chỉ lấy 1 góc/crop nhỏ của màn nguồn) — dùng
                                     # làm giá trị dự phòng nếu _auto_pick_capture_resolution()
                                     # thất bại hoàn toàn (không đọc được frame nào).

# User báo "nhận diện kém và mờ quá" trên nguồn USB capture thật (Wyse 5070)
# — nghi vấn: ép cứng CAPTURE_W/CAPTURE_H=1920x1080 cho MỌI thiết bị có thể
# khiến driver phải NỘI SUY PHÓNG TO từ 1 tín hiệu gốc có độ phân giải THẤP
# HƠN thực tế thiết bị hỗ trợ (khác hẳn trường hợp cũ đã ghi nhận — webcam
# tích hợp máy chỉ nhận 1280x720 dù ép 1920x1080 — TỪ CHỐI thẳng chứ không
# âm thầm nội suy; nhưng capture card RẺ TIỀN nhiều loại lại ÂM THẦM CHẤP
# NHẬN mọi yêu cầu, tự scale nội bộ, khiến `cap.get()` báo cáo lại ĐÚNG con
# số đã yêu cầu dù ảnh thật đã bị mờ do nội suy — không thể phát hiện chỉ
# bằng cách đọc lại CAP_PROP_FRAME_WIDTH/HEIGHT như code cũ làm).
# Vì không có capture card thật ở máy dev để xác nhận trực tiếp, KHÔNG đoán
# mù mà đo bằng 1 tín hiệu khách quan: độ SẮC NÉT thật của ảnh (Laplacian
# variance) ở TỪNG mức độ phân giải — ảnh bị nội suy phóng to sẽ luôn có độ
# nét THẤP HƠN HẲN so với ảnh capture thật ở đúng độ phân giải gốc, dù cùng
# số pixel danh nghĩa. `click_to_frame()`/chế độ `cv2.WINDOW_FULLSCREEN`
# hiện tại ĐÃ tự tính lại theo `frame_shape` thực tế (không hard-code
# 1920x1080) nên đổi độ phân giải capture ở đây AN TOÀN, không cần sửa thêm
# logic ánh xạ toạ độ click.
CAPTURE_RES_CANDIDATES = [(1920, 1080), (1600, 900), (1280, 720),
                           (960, 540), (800, 600), (640, 480)]
CAPTURE_RES_SHARPNESS_TOL = 0.75   # chọn độ phân giải YÊU CẦU CAO NHẤT có độ
                                    # nét >= 75% đỉnh cao nhất đo được trong
                                    # toàn bộ CAPTURE_RES_CANDIDATES — tránh
                                    # chọn nhầm 1 mức bị nội suy phóng to (nét
                                    # kém hẳn) chỉ vì số pixel danh nghĩa lớn
                                    # hơn. CHƯA kiểm chứng trên capture card
                                    # thật (không có thiết bị ở máy dev) — có
                                    # thể cần chỉnh ngưỡng này sau khi có số
                                    # liệu [DO-PHAN-GIAI] thật từ user.

def _capture_sharpness(frame):
    """Laplacian variance trên vùng TRUNG TÂM khung hình (tránh viền/panel
    UI cố định, chỉ đo phần nội dung radar) — độ nét càng cao thì variance
    càng lớn, vì đạo hàm bậc 2 chỉ bắt được biên độ lớn ở CHI TIẾT TẦN SỐ
    CAO thật sự tồn tại trong ảnh; ảnh bị nội suy phóng to từ nguồn thấp hơn
    không có chi tiết tần số cao thật (mọi nét đã bị làm mượt khi scale)."""
    h, w = frame.shape[:2]
    y0, y1 = h // 4, h - h // 4
    x0, x1 = w // 4, w - w // 4
    gray = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())

def _auto_pick_capture_resolution(cap):
    """Thử lần lượt CAPTURE_RES_CANDIDATES, đo độ nét THẬT ở mỗi mức, chọn
    độ phân giải YÊU CẦU cao nhất mà độ nét không tụt xa so với đỉnh cao
    nhất đo được (xem CAPTURE_RES_SHARPNESS_TOL) — dấu hiệu đây là mức GẦN
    ĐÚNG độ phân giải gốc thiết bị hỗ trợ, không phải bị nội suy phóng to.
    Luôn để `cap` ở trạng thái ĐÃ SET đúng lựa chọn cuối cùng trước khi trả
    về. Trả về (w, h) đã chọn."""
    print("[DO-PHAN-GIAI] Dang do do net that o tung muc phan giai de tranh anh bi mo do noi suy...")
    results = []
    for w, h in CAPTURE_RES_CANDIDATES:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame = None
        for _ in range(3):   # bo qua vai khung dau de driver on dinh sau khi doi res
            ok, frame = cap.read()
        if not ok or frame is None:
            print(f"[DO-PHAN-GIAI] {w}x{h} -> khong doc duoc frame, bo qua")
            continue
        score = _capture_sharpness(frame)
        results.append((w, h, actual_w, actual_h, score))
        print(f"[DO-PHAN-GIAI] yeu cau {w}x{h} -> thiet bi bao cao {actual_w}x{actual_h}  do_net={score:.1f}")

    if not results:
        print(f"[DO-PHAN-GIAI] Khong do duoc o muc nao — giu nguyen mac dinh {CAPTURE_W}x{CAPTURE_H}.")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAPTURE_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_H)
        return CAPTURE_W, CAPTURE_H

    best_score = max(r[4] for r in results)
    good = [r for r in results if r[4] >= best_score * CAPTURE_RES_SHARPNESS_TOL]
    w, h, actual_w, actual_h, score = max(good, key=lambda r: r[0] * r[1])
    print(f"[DO-PHAN-GIAI] Chon: yeu cau {w}x{h} (bao cao {actual_w}x{actual_h}, "
          f"do_net={score:.1f}, dinh do net do duoc={best_score:.1f})")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    return w, h

# Thư mục gốc của app: cạnh file .exe khi đã đóng gói (PyInstaller), cạnh file
# .py khi chạy trực tiếp bằng Python.
_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
            else os.path.dirname(os.path.abspath(__file__))

# Audio
SPEAK_DIR     = os.path.join(_BASE_DIR, "speak")

# Tesseract OCR đóng gói sẵn cạnh .exe (thư mục con "tesseract_bin", bản đã
# rút gọn — chỉ tesseract.exe + DLL cần thiết + tessdata/eng.traineddata,
# bỏ các công cụ training/docs không cần lúc chạy — xem CLAUDE.md) — chạy
# offline, không cần cài Tesseract trên máy đích. Chạy từ source (dev, chưa
# đóng gói) mà KHÔNG có thư mục này: giữ nguyên hành vi mặc định của
# `pytesseract` (dò `tesseract.exe` qua PATH hệ thống) — không bắt buộc dev
# phải copy thư mục `tesseract_bin/` vào working dir để test.
_TESSERACT_BUNDLED_EXE  = os.path.join(_BASE_DIR, "tesseract_bin", "tesseract.exe")
_TESSERACT_BUNDLED_DATA = os.path.join(_BASE_DIR, "tesseract_bin", "tessdata")
if _HAS_TESSERACT and os.path.isfile(_TESSERACT_BUNDLED_EXE):
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_BUNDLED_EXE
    os.environ["TESSDATA_PREFIX"] = _TESSERACT_BUNDLED_DATA

_audio_queue  = queue.Queue()
_audio_cancel = threading.Event()

# Calibration tâm radar đã lưu từ lần chạy trước, RIÊNG cho bản đóng gói
# (.exe) — bản .exe không có file .py thật trên đĩa để ghi đè lại (mã nguồn
# nằm gọn trong chính exe), nên không thể dùng cách "ghi thẳng vào file này"
# như khi chạy từ source (xem _persist_calibration_to_file). Ghi/đọc
# calibration.json cạnh exe thay thế, chỉ áp dụng cho chế độ đóng gói.
_CALIB_JSON_PATH = os.path.join(_BASE_DIR, "calibration.json")

def _load_calibration_override():
    global CX, CY, R_300KM, KM_PX
    if not os.path.isfile(_CALIB_JSON_PATH):
        return
    try:
        with open(_CALIB_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        CX, CY, R_300KM = int(data["CX"]), int(data["CY"]), int(data["R_300KM"])
        KM_PX = 300.0 / max(R_300KM, 1)
        print(f"[CALIB] Da nap tam radar tu calibration.json: CX={CX} CY={CY} "
              f"R_300KM={R_300KM} KM_PX={KM_PX:.4f}")
    except Exception as e:
        print(f"[CALIB] Loi doc calibration.json: {e}")

_load_calibration_override()

# ══════════════════════════════════════════════════════════════════════════════
# VÙNG LOẠI TRỪ "PHÁT TỰ ĐỘNG" — user báo (kèm ảnh log thật) 3 ca "Phát tự
# động" tự xác nhận nhầm CÁC VẬT CỐ ĐỊNH trên bản đồ/giao diện phần mềm ATC
# (không phải máy bay): 1 dấu chấm than cảnh báo cạnh 1 mục tiêu lục thật bị
# nhận thành RED, 1 mũi biển ngay tâm bị nhận thành CYAN ("xanh dương"), 1
# đoạn đường viền khu vực bám sát (nét đứt lục) vẫn thỉnh thoảng lọt qua 2
# lớp lọc nhiễu tĩnh (StaticNoiseFilter/StaticBackgroundMask, dù đã tăng độ
# kiên nhẫn — xem CLAUDE.md) và còn "mượn" được ID OCR của mục tiêu thật đứng
# gần. Cả 3 đều là VẬT CỐ ĐỊNH TRÊN BẢN ĐỒ (không phải nhiễu ngẫu nhiên) —
# thay vì cố phân biệt hoàn hảo bằng thuật toán (đã biết RẤT khó, từng bó tay
# với "CYAN lẫn bờ biển" trong lịch sử project), cho phép operator ĐÁNH DẤU
# THỦ CÔNG 1 lần, nhớ VĨNH VIỄN (ghi ra file, không mất khi tắt app) — xem
# `Shift+Delete` ở phần xử lý phím Delete.
#
# Lưu theo TOẠ ĐỘ KM TỪ TÂM (dx,dy), KHÔNG lưu pixel thô — đúng nguyên tắc đã
# áp dụng xuyên suốt file này (tâm cố định nhưng tỉ lệ km/px đổi bất cứ lúc
# nào do zoom, xem "Vì tâm không dịch..." ở đầu file) — 1 vùng loại trừ đặt
# lúc đang zoom XX vẫn phải đúng vị trí THẬT trên bản đồ sau khi zoom đổi.
#
# BUG/THIẾT KẾ đã sửa (2 phần) — user phản hồi sau khi dùng thử: "Shift+Delete
# vẫn không ổn, thà nói là bỏ phần nhận diện tại đường viền (kể cả mục tiêu
# trên đường viền, ý là tại đó kh nhận) nghe còn hợp lý hơn". Đúng — vòng tròn
# nhỏ (AUTO_EXCLUDE_RADIUS_PX=10px) quanh TỪNG điểm click rời rạc không đủ để
# che phủ 1 đường viền DÀI/CONG — giữa 2 lần Shift+Delete cách nhau vài chục
# px vẫn còn khe hở lọt candidate mới. Đồng thời đường viền này đã bị quan sát
# lẫn với NHIỀU màu khác nhau tại các thời điểm khác nhau (RED/GREEN/MAGENTA/
# CYAN tuỳ khung hình — bản chất là 1 VẬT CỐ ĐỊNH, màu chỉ là kết quả phân
# loại HSV thoáng qua của từng lần detect, không phải thuộc tính thật của vật
# đó) nên loại trừ theo ĐÚNG 1 màu ban đầu không đáng tin.
# Fix (KHÔNG cần thêm thao tác chuột/phím mới — vẫn dùng Shift+Delete như cũ):
#   1. Loại trừ giờ ÁP DỤNG CHO MỌI MÀU tại vị trí đã đánh dấu (không còn lọc
#      theo `zone["color"]` — field này vẫn lưu lại chỉ để tham khảo/gỡ lỗi).
#      Đúng ý "bỏ phần nhận diện tại đó" — không phân biệt màu.
#   2. NỐI các điểm loại trừ ĐỦ GẦN NHAU (trong bán kính hiện tại
#      `AUTO_EXCLUDE_CHAIN_LINK_PX`) thành ĐOẠN THẲNG, loại trừ luôn candidate
#      nằm trong dải quanh đoạn đó (không chỉ 2 đầu mút) — operator chỉ cần
#      Shift+Delete vài điểm RẢI DỌC theo đường viền (thao tác y hệt cũ), hệ
#      thống tự "nối liền" thành 1 DẢI liên tục thay vì để hở giữa các vòng
#      tròn rời rạc. Điểm loại trừ ĐƠN LẺ (không có điểm nào khác đủ gần, vd
#      dấu chấm than/mũi biển) vẫn hoạt động như vòng tròn nhỏ, không đổi.
_AUTO_EXCLUDE_JSON_PATH = os.path.join(_BASE_DIR, "auto_exclude.json")
_auto_exclude_zones = []   # list of {"color": str, "dx": float, "dy": float}
                           # "color" chỉ để tham khảo/gỡ lỗi — KHÔNG còn dùng
                           # để lọc lúc kiểm tra loại trừ, xem _is_auto_excluded().
AUTO_EXCLUDE_RADIUS_PX = 10   # px — cùng độ an toàn đã kiểm chứng như
                               # SHIFT_CLICK_SKIP_RADIUS/BLIP_MERGE_RADIUS
                               # (dưới khoảng cách tối thiểu thật đo được
                               # giữa 2 mục tiêu khác nhau, ~13-16px) — chỉ
                               # loại trừ đúng vật đã đánh dấu, không lỡ loại
                               # trừ 1 mục tiêu thật đứng gần đó sau này. Cũng
                               # là bề rộng (nửa dải) của đoạn nối giữa 2 điểm.
AUTO_EXCLUDE_CHAIN_LINK_PX = 40   # px — 2 điểm loại trừ cách nhau (theo pixel
                               # HIỆN TẠI, đổi theo zoom) trong khoảng này được
                               # coi là "liền nhau", nối thành 1 đoạn — đủ rộng
                               # để bắc qua khe hở giữa các lần click dọc 1
                               # đường cong (thường vài chục px), đủ hẹp để
                               # không nối nhầm 2 vật KHÔNG liên quan đứng xa
                               # nhau (dưới hẳn ASSOC_DIST_WIDE=150px).

def _load_auto_exclude_zones():
    global _auto_exclude_zones
    if not os.path.isfile(_AUTO_EXCLUDE_JSON_PATH):
        return
    try:
        with open(_AUTO_EXCLUDE_JSON_PATH, "r", encoding="utf-8") as f:
            _auto_exclude_zones = json.load(f)
        print(f"[LOAI-TRU] Da nap {len(_auto_exclude_zones)} vung loai tru tu auto_exclude.json")
    except Exception as e:
        print(f"[LOAI-TRU] Loi doc auto_exclude.json: {e}")

def _save_auto_exclude_zones():
    try:
        with open(_AUTO_EXCLUDE_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(_auto_exclude_zones, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[LOAI-TRU] Loi ghi auto_exclude.json: {e}")

def _add_auto_exclude_zone(color, dx, dy):
    _auto_exclude_zones.append({"color": color, "dx": float(dx), "dy": float(dy)})
    _save_auto_exclude_zones()

def _point_seg_dist(px, py, ax, ay, bx, by):
    """Khoảng cách từ điểm (px,py) tới đoạn thẳng (ax,ay)-(bx,by)."""
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 <= 1e-9:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * vx + (py - ay) * vy) / L2
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * vx, ay + t * vy
    return math.hypot(px - cx, py - cy)

def _is_auto_excluded(color, bx, by):
    """True nếu (bx,by) [toạ độ PIXEL hiện tại] rơi vào 1 vùng/đoạn đã được
    operator đánh dấu loại trừ vĩnh viễn (Shift+Delete) — quy đổi lại pixel
    HIỆN TẠI từ (dx,dy) km đã lưu, đúng nguyên tắc to_px() dùng xuyên suốt
    file này (không dùng lại pixel cũ, luôn tính lại theo KM_PX hiện tại).
    Áp dụng cho MỌI MÀU (tham số `color` giữ lại chỉ để tương thích chữ ký gọi
    hàm cũ, không còn dùng để lọc — xem docstring khối trên). Kiểm tra cả
    ĐIỂM ĐƠN (vòng tròn nhỏ quanh 1 lần đánh dấu) LẪN ĐOẠN NỐI giữa 2 điểm đủ
    gần nhau (dải liên tục dọc 1 đường cong đã đánh dấu nhiều điểm)."""
    if not _auto_exclude_zones:
        return False
    pts = [to_px(z["dx"], z["dy"]) for z in _auto_exclude_zones]
    for (ex, ey) in pts:
        if math.hypot(bx - ex, by - ey) < AUTO_EXCLUDE_RADIUS_PX:
            return True
    n = len(pts)
    for i in range(n):
        ax, ay = pts[i]
        for j in range(i + 1, n):
            cx2, cy2 = pts[j]
            if math.hypot(ax - cx2, ay - cy2) > AUTO_EXCLUDE_CHAIN_LINK_PX:
                continue
            if _point_seg_dist(bx, by, ax, ay, cx2, cy2) < AUTO_EXCLUDE_RADIUS_PX:
                return True
    return False

_load_auto_exclude_zones()

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

# ══════════════════════════════════════════════════════════════════════════════
# QUY TẮC "CHỮ SỐ ĐẦU ID -> MÀU HIỂN THỊ" + "KHOẢNG ID -> LOẠI MỤC TIÊU" —
# user yêu cầu: khi operator TỰ TAY sửa ID qua bảng xác nhận (Shift+Click/
# chuột phải -> gõ ID -> Enter), nếu chữ số ĐẦU khớp 1 quy tắc đã cấu hình
# (mặc định 0->GREEN, 6->RED, 8->MAGENTA — đúng quy ước `COLOR_ID_PREFIX` đã
# dùng để sửa lỗi đọc số OCR, xem phía dưới) thì đổi MÀU HIỂN THỊ (vòng tròn/
# tooltip/bảng/JSON-HTML) sang đúng màu đó — sidestep hẳn vấn đề "nhầm đỏ/
# tím" đã dai dẳng nhiều lần trong lịch sử project (chỉnh HSV mù không giải
# quyết dứt điểm được) bằng cách TIN NGƯỜI đã xác nhận đúng ID thật thay vì
# máy phân loại màu pixel.
#
# QUAN TRỌNG: đây CHỈ là lớp HIỂN THỊ, KHÔNG BAO GIỜ đổi `info["color"]` thật
# (dùng để khớp blip↔track theo HSV mỗi chu kỳ trong `TrackManager.update()`,
# và để loại trừ/chẩn đoán) — màu đó vẫn phải khớp ĐÚNG pixel thật trên video
# để track còn tiếp tục bám được; đổi nó theo ý nghĩa ID sẽ làm track "câm"
# ngay lập tức (không còn blip cùng màu HSV nào để khớp nữa). Field MỚI
# `display_color`/`id_label` (đặt bởi `_apply_id_color_rules()`, đọc bởi
# `_track_display()` — cả 2 định nghĩa gần `_LOAI_VN`) tách biệt hoàn toàn
# khỏi `color`.
#
# Cấu hình qua ứng dụng RIÊNG `RadarIDColorConfig.exe` (nguồn:
# `radar_id_color_config.py`/`RadarIDColorConfig.spec`), đặt CẠNH
# RadarVRS.exe — ghi ra `id_color_rules.json` cùng thư mục. File này CHỈ
# được đọc 1 LẦN lúc khởi động (giống `calibration.json`) — sửa xong phải
# khởi động lại RadarVRS.exe để áp dụng, không tự nạp lại giữa chừng.
ID_COLOR_RULES_JSON_PATH = os.path.join(_BASE_DIR, "id_color_rules.json")
_DEFAULT_DIGIT_COLOR = {"0": "GREEN", "6": "RED", "8": "MAGENTA"}
_ID_COLOR_RULES = {"digit_color": dict(_DEFAULT_DIGIT_COLOR), "id_ranges": []}

def _load_id_color_rules():
    global _ID_COLOR_RULES
    if not os.path.isfile(ID_COLOR_RULES_JSON_PATH):
        return
    try:
        with open(ID_COLOR_RULES_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        digit_color = {str(k): str(v) for k, v in data.get("digit_color", {}).items()
                        if str(v) in COLOR_MAP}
        id_ranges = [r for r in data.get("id_ranges", [])
                     if isinstance(r, dict) and "min" in r and "max" in r]
        _ID_COLOR_RULES = {"digit_color": digit_color or dict(_DEFAULT_DIGIT_COLOR),
                            "id_ranges": id_ranges}
        print(f"[ID-COLOR] Da nap {len(_ID_COLOR_RULES['digit_color'])} quy tac "
              f"chu-so-dau, {len(id_ranges)} khoang ID tu id_color_rules.json")
    except Exception as e:
        print(f"[ID-COLOR] Loi doc id_color_rules.json: {e}")

_load_id_color_rules()

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
# BUG đã sửa: user báo "nhầm giữa màu quốc tế (MAGENTA) và quân sự (RED)"
# khi Shift+Click — đo lại khoảng cách giữa các dải hue liền kề: RED_thap→
# YELLOW=4°, YELLOW→GREEN=2°, GREEN→CYAN=19°, CYAN→MAGENTA=30°, nhưng
# MAGENTA→RED_cao (166) chỉ **1°** (165→166) — hẹp hơn HẲN mọi cặp khác
# (2-30°). `classify_color_at()` (Shift+Click) VÀ `detect_blips()` (tự động,
# qua `_compute_color_masks()`) đều dùng chung bảng này, nên 1 icon đỏ có
# hue trôi nhẹ do nén/mờ (chỉ cần lệch 1-2°) rất dễ bị đếm là MAGENTA —
# ảnh hưởng CẢ click thủ công LẪN tự động phát hiện. RED đã được nới hue
# thấp xuống 166 (từ 168) trước đây VÌ LÝ DO ĐÃ ĐO (icon RED nhỏ dễ mất, xem
# lịch sử CLAUDE.md) nên không thu hẹp lại — thay vào đó hẹp MAGENTA từ 165
# xuống 158 (7° đệm, vẫn hẹp hơn các cặp khác nhưng gấp 7 lần mức 1° cũ).
# CHƯA có dữ liệu thật để biết 158 có làm rớt icon MAGENTA thật hay không —
# cần user quan sát thêm sau khi đổi.
HSV_RANGES = {
    "RED":     [((0,  80, 80),(14, 255,255)), ((166,80, 80),(180,255,255))],
    "GREEN":   [((40,  70, 80),(66, 255,255))],
    "YELLOW":  [((18,  90, 80),(38, 255,255))],
    "CYAN":    [((85,  70, 80),(105,255,255))],
    "MAGENTA": [((135, 70, 80),(158,255,255))],
}

# Tối ưu nhỏ cho _compute_color_masks() — HSV_RANGES là hằng số, không đổi
# giữa các lần gọi, nhưng bản cũ tự dựng lại np.array(lo)/np.array(hi) MỖI
# LẦN gọi (5 màu x 1-2 dải x 2 mảng = tới ~14 lần cấp phát mảng nhỏ mỗi chu
# kỳ detect, thuần lãng phí trên máy CPU yếu). Dựng sẵn 1 LẦN lúc nạp module.
_HSV_RANGES_NP = {
    name: [(np.array(lo, dtype=np.uint8), np.array(hi, dtype=np.uint8)) for lo, hi in ranges]
    for name, ranges in HSV_RANGES.items()
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
# nguồn CAPTURE CARD (`run_radar_from_capture`, xem khối docstring ngay trên
# hàm đó) — cửa sổ chạy true fullscreen trên toàn màn hình output nên click
# phải bắt qua hook TOÀN CỤC thay vì cv2.setMouseCallback cục bộ (kế thừa từ
# radar_live_2.py, xem lý do trong file đó). Chế độ phát lại file
# (`run_radar_from_video`) vẫn dùng cv2.setMouseCallback cục bộ như cũ, không
# đụng tới các biến này.
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
        # Đẩy kèm trạng thái Shift LÚC BẤM — Shift+Delete = xoá + đánh dấu
        # vùng loại trừ vĩnh viễn (xem docstring `_auto_exclude_zones` +
        # 2 nơi xử lý `_delete_key_q` trong run_radar_from_capture/_video).
        _delete_key_q.put(bool(_shift_state["held"]))
    else:
        # Mọi phím khác — chỉ thực sự dùng bởi bảng ID (_id_panel) trong chế
        # độ capture (cửa sổ true fullscreen, không đáng tin cậy nhận focus
        # bàn phím cục bộ — cùng lý do Delete đã dùng hook toàn cục từ trước).
        # Chế độ phát file xả hàng đợi này mà KHÔNG dùng tới (đã dùng
        # cv2.waitKey cục bộ, đáng tin cậy hơn vì cửa sổ có focus thật) — chỉ
        # để tránh hàng đợi phình to qua 1 phiên chạy dài.
        _id_panel_key_q.put(key)

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
    # BUG đã sửa: trước đây chỉ đọc ID khi `tid.isdigit()` — TRUE với track đã
    # đặt tên tay (Shift+Click rồi gõ số / bảng chuột phải), nhưng LUÔN FALSE
    # với track do "Phát tự động" tự tạo (tid dạng "?7") dù màn hình đang
    # hiện đúng số hiệu do OCR đọc được (`display_id()`) — phần ID bị bỏ qua
    # hoàn toàn trong câu đọc, nghe như thiếu mất 1 trường (nhảy thẳng sang
    # phương vị). Fix: dùng `display_id(tid)` (ưu tiên số OCR đã chốt, rơi về
    # `tid`/"???" như cũ nếu chưa có) để quyết định có đọc ID hay không —
    # track được OCR nhận diện giờ cũng được đọc ID dù chưa ai đặt tên tay.
    did = display_id(tid)
    if did.isdigit():
        clips.extend(list(did))
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

def _stop_all_audio_now():
    """Tắt NGAY âm thanh đang phát + dọn sạch hàng đợi — gọi lúc thoát app
    (ESC/Q) để không còn tiếng phát dở dang sau khi cửa sổ đã đóng."""
    _audio_cancel.set()
    while not _audio_queue.empty():
        try:
            _audio_queue.get_nowait()
        except queue.Empty:
            break
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass

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

# True  = "tự do quét" — tự động dò + đọc mọi blip trong 150km (kể cả khi đã
#         có sẵn mục tiêu chọn thủ công — xem lịch sử fix ngay dưới).
# False = "chỉ mục tiêu đã chọn" — KHÔNG còn dùng để TỰ ĐỘNG chuyển vào nữa
#         (giữ lại biến/nhánh code này chỉ để không phải sửa lại toàn bộ nơi
#         đọc nó — luôn là True kể từ fix dưới đây).
#
# LỊCH SỬ: trước đây biến này được ĐÁNH GIÁ LẠI mỗi lần bấm bật "Phát"
# (_start_auto_session()), dựa trên "đã có mục tiêu chọn thủ công hay chưa"
# — nếu ĐÃ có (điển hình sau khi dùng "Ưu tiên"), tự động chuyển sang "chỉ
# mục tiêu đã chọn", TẮT LUÔN việc dò mục tiêu MỚI (`auto_confirm_nearby()`
# không chạy). User phản hồi: "khi đang ở chế độ Ưu tiên mà nhấn nút Phát,
# vẫn giữ mục tiêu đó. Và ở chế độ Phát đó, vẫn tiếp tục dò tự động các mục
# tiêu khác" — tức là bấm "Phát" (bất kể trước đó đã có mục tiêu thủ công
# nào chưa, bất kể nút "Ưu tiên" đang bật hay tắt) PHẢI luôn dò thêm mục
# tiêu mới, không được để heuristic "đã có mục tiêu thủ công" âm thầm tắt
# việc dò đó. Giờ đã có nút "Ưu tiên" RIÊNG, TƯỜNG MINH để hạn chế "chỉ đọc
# mục tiêu thủ công" (xem `_priority_manual_only`) — heuristic ngầm định cũ
# hết cần thiết, gây đúng hành vi sai user vừa báo. Fix: `_start_auto_session()`
# luôn đặt `_auto_scan_mode = True` — mục tiêu thủ công đang có KHÔNG bị đụng
# tới gì (không nằm trong logic này), chỉ có việc DÒ MỤC TIÊU MỚI được đảm
# bảo luôn bật khi "Phát" đang chạy.
_auto_scan_mode = False

# Nút "Ưu tiên" — độc lập với _auto_scan_mode (vốn chỉ được ĐÁNH GIÁ 1 lần
# lúc bấm bật "Phát", dựa trên track nào đang có sẵn tại đúng thời điểm đó).
# True = ép "Phát" (dù nhanh hay chậm) CHỈ đọc track do CHÍNH TAY xác nhận
# (Shift+Click, auto=False) — bỏ qua MỌI track do "Phát tự động" tự dò ra
# (auto=True), bất kể _auto_scan_mode đang là gì. Có thể bật/tắt bất cứ lúc
# nào (kể cả trước khi bấm Phát) — chỉ ảnh hưởng tới việc ĐỌC (giọng nói)
# trong _global_auto_worker(), KHÔNG ảnh hưởng auto_confirm_nearby() (vẫn tự
# dò/tạo track mới như cũ nếu đang ở chế độ tự-do-quét) — track tự động vẫn
# được tạo/hiển thị/bám bình thường, chỉ tạm không được xướng tên qua loa.
_priority_manual_only = False

def toggle_priority_manual_only(tm):
    """BẬT: coi như "chỉ mục tiêu đã chọn" tuyệt đối kể từ đây — xoá NGAY mọi
    track tự động dò được (auto=True, bất kể _auto_scan_mode đang là gì —
    khác _finish_auto_session() vốn chỉ xoá khi _auto_scan_mode=True) và
    dừng NGAY âm thanh đang phát (cùng kỹ thuật _stop_all_audio_now() dùng
    cho nút Phát). Đồng thời dừng timer đọc riêng theo chu kỳ CỐ ĐỊNH (mặc
    định 60s, do bảng ID/`start_auto_speak()` tạo lúc Shift+Click xác nhận
    TỪNG mục tiêu thủ công — xem `_id_panel_confirm()`) của MỌI track thủ
    công đang có: từ giờ các track đó được đúng vòng round-robin LIÊN TỤC
    của `_global_auto_worker()` (đã lọc chỉ còn track thủ công nhờ
    `_priority_manual_only`) đọc đi đọc lại ngay khi tới lượt, không còn
    phải đợi hết 1 chu kỳ cố định (thường chậm hơn hẳn) mới đọc lại — nhanh
    hơn, và không còn 2 cơ chế đọc cùng 1 mục tiêu chồng lấn/lệch nhịp nhau.

    TẮT: KHÔNG xoá gì cả, giữ nguyên toàn bộ track/trạng thái đang có — chỉ
    đơn thuần quay lại đọc theo chế độ bình thường (_auto_scan_mode)."""
    global _priority_manual_only
    _priority_manual_only = not _priority_manual_only
    if _priority_manual_only:
        to_delete = [tid for tid, info in tm.tracks.items() if info.get("auto", False)]
        for tid in to_delete:
            stop_auto_speak(tid)
            del tm.tracks[tid]
        for tid, info in list(tm.tracks.items()):
            if not info.get("auto", False):
                stop_auto_speak(tid)
        _stop_all_audio_now()
        print(f"[UU-TIEN] BAT — da xoa {len(to_delete)} muc tieu tu-dong-quet, "
              f"tat het timer doc rieng, chi giu + doc lien tuc muc tieu da chon tay",
              flush=True)
    else:
        print("[UU-TIEN] TAT — doc theo che do binh thuong, giu nguyen muc tieu dang co", flush=True)

def _start_auto_session(tm):
    global _auto_scan_mode
    # Luôn "tự do quét" — xem docstring dài ở khai báo `_auto_scan_mode` phía
    # trên (đã bỏ heuristic cũ "có mục tiêu thủ công sẵn thì tắt dò mới").
    _auto_scan_mode = True
    # KHÔNG reset _discovery_last_time/_discovery_prev_snapshot ở đây —
    # xem docstring auto_confirm_nearby() (mục "ảnh chụp nền luôn chạy").
    # Reset về rỗng mỗi lần bật khiến vòng khám phá ĐẦU TIÊN sau MỖI lần bật
    # "Phát tự động" phải xác nhận mù mọi candidate đang thấy (không có gì
    # để so sánh) — nếu đúng lúc đó có nhiễu đường viền/lưới chưa kịp bị
    # StaticBackgroundMask lọc, nó lọt qua vĩnh viễn. Giữ nguyên ảnh chụp
    # đang chạy nền (nếu app đã chạy đủ lâu từ trước) để vòng khám phá đầu
    # tiên đã có sẵn "trước" để so sánh ngay.

def _finish_auto_session(tm):
    if not _auto_scan_mode:
        return
    to_delete = [tid for tid, info in tm.tracks.items() if info.get("auto", False)]
    for tid in to_delete:
        stop_auto_speak(tid)
        del tm.tracks[tid]
    if to_delete:
        print(f"[GLOBAL-AUTO] Da xoa {len(to_delete)} muc tieu tu-dong-quet khi dung", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# BẢNG XÁC NHẬN ID + CHU KỲ PHÁT — cố định góc trên-trái, có đường nối tới
# vị trí mục tiêu trên màn hình (vẽ trong draw_frame() → _draw_id_panel()).
# DÙNG CHUNG cho CẢ 2 nguồn (trước đây là 2 giao diện riêng, đã gộp làm 1
# theo yêu cầu — xem `open_id_panel()`):
#   - Track TỰ ĐỘNG phát hiện (auto=True, do auto_confirm_nearby() tạo trong
#     chế độ "tự-do-quét") — đưa vào hàng đợi từ vòng round-robin của
#     `_global_auto_worker`, hiện NGAY lúc mục tiêu được đọc lần đầu.
#   - Track chọn THỦ CÔNG (Shift+Click / chuột phải) — đưa vào hàng đợi qua
#     `open_id_panel()`.
# Chỉ 1 bảng hiện tại 1 thời điểm — mọi yêu cầu khác xếp hàng trong
# `_id_panel_queue`, tự mở lần lượt khi bảng trước đó đóng lại
# (`_id_panel_activate_next()`, gọi mỗi khung hình từ vòng lặp chính).
# ══════════════════════════════════════════════════════════════════════════════
ID_PANEL_POS        = (10, 28)     # góc trên-trái, ngay dưới thanh trạng thái
ID_PANEL_W          = 300
ID_PANEL_H          = 96
# BUG đã sửa: user báo màu xanh dương ("dodger blue") cũ dễ lẫn với màu track
# CYAN (BGR (220,200,30) trong COLOR_MAP — cũng thiên xanh dương/lục) khi
# nhìn nhanh trên màn — đổi sang NÂU ấm ("chocolate"/"peru"), không trùng dải
# màu với BẤT KỲ màu nào trong 5 màu track (đỏ/lục/vàng/lam/tím) hay cam vành
# 300km/trắng-xám lưới.
ID_PANEL_LINE_COLOR = (60, 110, 180)  # BGR nâu ấm

_id_panel_queue = queue.Queue()   # tid đang chờ xác nhận, xử lý TUẦN TỰ
_id_panel_key_q = queue.Queue()   # phím gõ — chỉ dùng cho chế độ capture (pynput toàn cục)
_id_panel = {
    "active": False, "tid": None,
    "id_text": "", "id_cursor": 0, "id_selected": False,
    "interval_text": "", "int_cursor": 0,
    "field": "id",   # "id" hoặc "interval"
}

def _id_panel_activate_next(tm):
    """Nếu chưa có bảng nào đang mở, lấy tid TIẾP THEO trong hàng đợi (bỏ qua
    tid đã bị mất/xoá) và mở bảng cho nó — ID điền sẵn số hiệu OCR đã chốt
    (nếu có) và coi như đang "bôi đen" để gõ số là ghi đè ngay."""
    if _id_panel["active"]:
        return
    while not _id_panel_queue.empty():
        tid = _id_panel_queue.get_nowait()
        if tid not in tm.tracks:
            continue
        prefill = _ocr_confirmed.get(tid) or ""
        _id_panel.update({
            "active": True, "tid": tid,
            "id_text": prefill, "id_cursor": len(prefill), "id_selected": bool(prefill),
            "interval_text": "", "int_cursor": 0,
            "field": "id",
        })
        return

def _id_panel_confirm(tm):
    """ENTER — xác nhận: đổi tên (nếu có gõ ID mới), phát ƯU TIÊN 2 lần liên
    tiếp (ngắt mọi âm thanh khác đang phát để đọc ngay) rồi bắt đầu chu kỳ
    lặp lại (để trống hoặc nhập đúng 60 đều dùng mặc định 60s). Hành vi "đọc
    ưu tiên 2 lần" kế thừa từ dialog tkinter cũ (đã gộp vào đây, xem
    `open_id_panel()`), áp dụng chung cho cả track auto-scan lẫn thủ công."""
    tid = _id_panel["tid"]
    if tid and tid in tm.tracks:
        new_id     = _id_panel["id_text"].strip()
        active_tid = tid
        if new_id and new_id != tid:
            tm.rename(tid, new_id)
            active_tid = new_id
            # BUG đã sửa: user báo ID hiển thị sai (vd "064" thay vì đúng
            # "027") — truy ra: `display_id()` LUÔN ưu tiên `_ocr_confirmed`
            # trước tid, và `TrackManager.rename()` đổi hẳn KHOÁ track sang
            # `new_id` — nên nếu operator gõ ĐÚNG số hiệu để sửa 1 lần đọc
            # OCR sai, track giờ mang khoá MỚI (vd "027") KHÔNG có trong
            # `_ocr_confirmed` (chỉ khoá CŨ "?7" từng có) → luồng OCR nền vẫn
            # coi đây là track CHƯA chốt ID, tiếp tục đọc lại nhãn CÙNG VỊ
            # TRÍ VẬT LÝ đó — rất có thể đọc ra LẠI ĐÚNG kết quả sai y hệt
            # trước (Tesseract đọc SAI CÙNG 1 CÁCH mỗi lần với cùng ảnh đầu
            # vào — đã ghi nhận nhiều lần trong CLAUDE.md) — rồi GHI ĐÈ lại
            # đúng giá trị sai đó vào `_ocr_confirmed[new_id]`, âm thầm XOÁ
            # MẤT sửa đổi thủ công của operator ngay sau đó. Fix: khoá LUÔN
            # `_ocr_confirmed[new_id]` bằng chính giá trị operator vừa gõ —
            # vừa làm `display_id()` hiển thị đúng ngay (nhất quán với hành
            # vi cũ khi ID trùng đúng kết quả OCR), vừa loại `new_id` khỏi
            # `pending` của `_id_ocr_worker()` (lọc theo `tid not in
            # _ocr_confirmed`) nên KHÔNG BAO GIỜ bị đọc/ghi đè lại nữa — số
            # hiệu do CHÍNH OPERATOR xác nhận qua bảng là NGUỒN THẬT CUỐI
            # CÙNG, không nhường lại cho máy đọc lại.
            _ocr_confirmed[new_id] = new_id
            # Áp dụng quy tắc "chữ số đầu ID -> màu hiển thị" / "khoảng ID ->
            # loại mục tiêu" — CHỈ đường thủ công (đúng yêu cầu user), xem
            # docstring đầy đủ ở `_apply_id_color_rules()`/`ID_COLOR_RULES_JSON_PATH`.
            _new_info = tm.tracks.get(new_id)
            if _new_info is not None:
                _apply_id_color_rules(_new_info, new_id)
        secs = 60.0
        int_str = _id_panel["interval_text"].strip()
        if int_str:
            try:
                parsed = float(int_str)
                if parsed > 0:
                    secs = parsed
            except ValueError:
                pass
        info = tm.tracks.get(active_tid)
        if info is not None:
            info["reviewed"] = True
            for i in range(2):
                speak_target(active_tid, info, interrupt=(i == 0))
            start_auto_speak(active_tid, secs, tm)
    _id_panel["active"] = False
    _id_panel_activate_next(tm)

def _id_panel_cancel(tm):
    # Bỏ qua (ESC) KHÔNG xoá track — chỉ là "chưa muốn đặt tên/chu kỳ ngay",
    # không phải "đây là nhiễu" (đó là việc của phím Delete, xem docstring
    # trên khối xử lý _delete_key_q). Vẫn đánh dấu "đã duyệt" để track hiện
    # khoanh tròn bình thường từ giờ, không bị coi là "chưa xem" mãi mãi.
    tid = _id_panel["tid"]
    if tid and tid in tm.tracks:
        tm.tracks[tid]["reviewed"] = True
    _id_panel["active"] = False
    _id_panel_activate_next(tm)

def _id_panel_feed_char(ch):
    """Gõ 1 ký tự in được vào trường đang focus. Nếu trường ID đang 'bôi
    đen' (id_selected), ký tự đầu tiên GHI ĐÈ toàn bộ — đúng hành vi bôi đen
    rồi gõ số thay vào của thao tác soạn thảo văn bản thông thường."""
    if not _id_panel["active"]:
        return
    if _id_panel["field"] == "id":
        if _id_panel["id_selected"]:
            _id_panel["id_text"] = ch
            _id_panel["id_cursor"] = 1
            _id_panel["id_selected"] = False
            return
        text, cur = _id_panel["id_text"], _id_panel["id_cursor"]
        _id_panel["id_text"]   = text[:cur] + ch + text[cur:]
        _id_panel["id_cursor"] = cur + 1
    else:
        text, cur = _id_panel["interval_text"], _id_panel["int_cursor"]
        _id_panel["interval_text"] = text[:cur] + ch + text[cur:]
        _id_panel["int_cursor"]    = cur + 1

def _id_panel_feed_control(name, tm):
    """name: 'backspace' | 'left' | 'right' | 'tab' | 'enter' | 'esc'."""
    if not _id_panel["active"]:
        return
    field = _id_panel["field"]
    if name == "enter":
        _id_panel_confirm(tm);  return
    if name == "esc":
        _id_panel_cancel(tm);   return
    if name == "tab":
        _id_panel["field"] = "interval" if field == "id" else "id"
        _id_panel["id_selected"] = False
        return
    key_text, key_cur = ("id_text", "id_cursor") if field == "id" else ("interval_text", "int_cursor")
    if name == "backspace":
        if field == "id" and _id_panel["id_selected"]:
            _id_panel["id_text"] = "";  _id_panel["id_cursor"] = 0;  _id_panel["id_selected"] = False
            return
        text, cur = _id_panel[key_text], _id_panel[key_cur]
        if cur > 0:
            _id_panel[key_text] = text[:cur-1] + text[cur:]
            _id_panel[key_cur]  = cur - 1
    elif name == "left":
        if field == "id" and _id_panel["id_selected"]:
            _id_panel["id_cursor"] = 0;  _id_panel["id_selected"] = False
        else:
            _id_panel[key_cur] = max(0, _id_panel[key_cur] - 1)
    elif name == "right":
        if field == "id" and _id_panel["id_selected"]:
            _id_panel["id_cursor"] = len(_id_panel["id_text"]);  _id_panel["id_selected"] = False
        else:
            _id_panel[key_cur] = min(len(_id_panel[key_text]), _id_panel[key_cur] + 1)

def _global_auto_worker(stop_evt, tm_ref, slow=False):
    while not stop_evt.is_set():
        candidates = []
        for tid, info in list(tm_ref.tracks.items()):
            # `_priority_manual_only` (nút "Ưu tiên") ép bỏ qua MỌI track
            # auto=True bất kể _auto_scan_mode — xem docstring hằng số này.
            if (_priority_manual_only or not _auto_scan_mode) and info.get("auto", False):
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
            info = tm_ref.tracks.get(tid)
            if not info:
                continue
            # Lịch sử (kế thừa từ radar_live_4.py, xem CLAUDE.md): (1) ban đầu
            # track auto-scan mới phát hiện bị ĐỌC NGAY (thiếu ID vì OCR chưa
            # kịp đọc) → (2) sửa thành PHẢI đợi Enter xác nhận qua bảng ID mới
            # đọc → (3) đảo lại đọc ngay NHƯNG bảng ID vẫn TỰ ĐỘNG bật lên mỗi
            # lần có mục tiêu mới, đòi operator gõ/Enter mới "thoát" được bảng
            # dù âm thanh đã đọc xong — user báo "vẫn chờ tôi Enter và nhập số
            # liệu lúc ban đầu" (xác nhận qua AskUserQuestion: đúng là bảng ID
            # góc trên-trái, không phải phần âm thanh). Fix RIÊNG Ở FORK NÀY
            # (radar_live_4.py giữ nguyên không đổi theo yêu cầu user): KHÔNG
            # tự đẩy track auto-scan vào `_id_panel_queue` ở đây nữa — chỉ
            # đọc, không mở bảng. Bảng ID vẫn còn nguyên trong file, chỉ mở
            # khi operator chủ động Shift+Click/chuột phải (`open_id_panel()`,
            # không đổi) — không còn bất kỳ lúc nào tự bật lên đòi nhập liệu.
            # `reviewed` giữ nguyên `False` cho track auto-scan chưa qua bảng
            # — vô hại: chỉ ảnh hưởng khoanh tròn tạm thời khi bảng ĐANG TRỎ
            # tới track đó (xem draw_frame()), mà giờ bảng không còn tự trỏ
            # tới các track này nữa nên không có gì để vẽ khác đi.
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
        # Dừng NGAY âm thanh đang phát dở — trước đây CHỈ đặt cờ dừng, worker
        # tự nhận ra ở vòng kiểm tra kế tiếp (có thể trễ tới hàng giây nếu
        # đang giữa 1 clip dài) — user yêu cầu rõ "âm thanh phải dừng ngay
        # lập tức" khi nút Phát gộp (xem cycle_play_button()) chuyển sang TẮT.
        _stop_all_audio_now()
        print("[GLOBAL-AUTO] Dung", flush=True)
    else:
        if _global_auto_slow_active:
            toggle_global_auto_slow(tm)
        _start_auto_session(tm)
        _global_auto_stop = threading.Event()
        _global_auto_thread = threading.Thread(target=_global_auto_worker, args=(_global_auto_stop, tm, False), daemon=True)
        _global_auto_thread.start()
        _global_auto_active = True
        ut_txt = " (Uu tien: chi doc muc tieu thu cong)" if _priority_manual_only else ""
        print(f"[GLOBAL-AUTO] Bat dau (nhanh) — tu dong quet <= 150km{ut_txt}", flush=True)

def toggle_global_auto_slow(tm):
    global _global_auto_slow_active, _global_auto_slow_stop, _global_auto_slow_thread
    if _global_auto_slow_active:
        _global_auto_slow_stop.set()
        _global_auto_slow_active = False
        _finish_auto_session(tm)
        # Xem chú thích tương ứng trong toggle_global_auto() — dừng ngay âm
        # thanh, không đợi worker tự phát hiện cờ dừng. Nhánh này cũng chạy
        # khi CHUYỂN TỪ "Phát chậm" SANG "Phát nhanh" (toggle_global_auto()
        # tự gọi lại đây để tắt chậm trước khi bật nhanh) — nên âm thanh
        # cũng dừng ngay đúng lúc chuyển tốc độ, không chỉ lúc tắt hẳn.
        _stop_all_audio_now()
        print("[GLOBAL-AUTO-CHAM] Dung", flush=True)
    else:
        if _global_auto_active:
            toggle_global_auto(tm)
        _start_auto_session(tm)
        _global_auto_slow_stop = threading.Event()
        _global_auto_slow_thread = threading.Thread(target=_global_auto_worker, args=(_global_auto_slow_stop, tm, True), daemon=True)
        _global_auto_slow_thread.start()
        _global_auto_slow_active = True
        ut_txt = " (Uu tien: chi doc muc tieu thu cong)" if _priority_manual_only else ""
        print(f"[GLOBAL-AUTO-CHAM] Bat dau (cham) — tu dong quet <= 150km{ut_txt}", flush=True)

def cycle_play_button(tm):
    """Nút "Phát" gộp (thay 2 nút "PHÁT TỰ ĐỘNG"/"PHÁT CHẬM" cũ tách rời) —
    mỗi lần bấm chuyển đúng 1 trạng thái theo chu trình:
        TẮT ("Phát") -> PHÁT CHẬM -> PHÁT NHANH -> TẮT -> ...
    Tái dùng nguyên trạng toggle_global_auto()/toggle_global_auto_slow() (đã
    có sẵn logic "tắt bên kia trước khi bật bên này" + đánh giá lại
    _auto_scan_mode mỗi lần chuyển — xem CLAUDE.md "Chuyển đổi nhanh↔chậm
    coi như dừng+bật lại") — cả 2 hàm đó giờ tự dừng NGAY âm thanh đang phát
    ở đúng nhánh "tắt" của chúng (xem _stop_all_audio_now() thêm vào đó),
    nên hàm này không cần tự gọi lại lần nữa."""
    if not _global_auto_active and not _global_auto_slow_active:
        toggle_global_auto_slow(tm)     # TAT -> PHAT CHAM
    elif _global_auto_slow_active:
        toggle_global_auto(tm)          # PHAT CHAM -> PHAT NHANH (tu tat cham truoc)
    else:
        toggle_global_auto(tm)          # PHAT NHANH -> TAT

# Phát hiện mục tiêu mới cho "Phát tự động" (tự-do-quét) — SO SÁNH 2 "ẢNH
# CHỤP" candidate cách nhau >= AUTO_DISCOVERY_INTERVAL_SEC giây, KHÔNG đếm
# streak mỗi chu kỳ detect nhanh. Lịch sử các lần sửa:
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
# 3) Thử THEO DÕI QUỸ ĐẠO từng candidate qua MỌI chu kỳ liên tiếp (khớp
#    candidate mới với entry đang theo dõi bằng nearest-pair, xác nhận khi
#    đã lệch đủ xa baseline) — theo đề xuất user, ý tưởng đúng ("1 điểm đứng
#    yên tuyệt đối không bao giờ tự dịch chuyển trong lịch sử của chính nó")
#    nhưng THUẬT TOÁN KHỚP GẶP MÂU THUẪN BÁN KÍNH không giải được: bán kính
#    khớp giữa 2 chu kỳ LIÊN TIẾP phải NHỎ (để không khớp nhầm 2 đốm nhiễu
#    khác nhau đứng gần nhau trên cùng 1 đường viền nét đứt) — nhưng mục
#    tiêu thật khi NHẢY vị trí (mỗi 5-11s) có thể lệch xa tới ~130px (đã đo
#    trước đó cho `ASSOC_DIST_WIDE`), vượt xa bất kỳ bán kính "nhỏ, an toàn"
#    nào — nên cú nhảy bị hiểu nhầm thành "biến mất + xuất hiện vật mới",
#    KHÔNG BAO GIỜ ghi nhận được là "đã di chuyển". Bắt được lỗi này bằng
#    test đơn vị (mô phỏng 1 điểm nhảy 60px, không được xác nhận) TRƯỚC khi
#    build cho user — đã trình bày lại, user đồng ý quay về cách (4).
# Fix hiện tại (4) — quay lại hướng "2 ảnh chụp", nhưng ẢNH CHỤP CHẠY NỀN
# LIÊN TỤC thay vì reset mỗi lần bật: so sánh candidate hiện tại (trong bán
# kính GLOBAL_RADIUS) với ảnh chụp cách đây AUTO_DISCOVERY_INTERVAL_SEC giây
# (theo mốc thời gian thực `time.time()`, kiểm tra ngay trong hàm này —
# KHÔNG cần luồng nền riêng, vì phần so sánh chỉ thực sự chạy 1 lần mỗi >60s
# nên "nhẹ máy", và không có thao tác nào chặn/làm chậm vòng lặp chính).
# KHÔNG cần khớp từng candidate qua mọi chu kỳ (tránh hẳn mâu thuẫn bán kính
# ở cách (3)) — chỉ cần hỏi "có candidate CÙNG MÀU nào đứng gần đây (trong
# AUTO_DISCOVERY_STATIC_TOL_PX) ở ẢNH CHỤP TRƯỚC hay không", bất kể khoảng
# cách cú nhảy thật là bao nhiêu. Mục tiêu thật luôn cập nhật vị trí ít nhất
# 1 lần trong bất kỳ khoảng 60s+ nào (quan sát thực tế: mỗi 5-11s) nên gần
# như chắc chắn "khác" ảnh chụp trước và được xác nhận; nhiễu tĩnh thật
# (không bao giờ dịch chuyển) luôn "giống hệt" ảnh chụp trước nên không bao
# giờ được xác nhận.
# Ảnh chụp LUÔN được cập nhật mỗi AUTO_DISCOVERY_INTERVAL_SEC giây, BẤT KỂ
# "Phát tự động" đang bật hay tắt (khác bản gốc — vốn chỉ so sánh KHI đang
# bật, và bị `_start_auto_session()` reset về rỗng mỗi lần bật, xem đoạn dưới
# về lỗ hổng "vòng đầu tiên xác nhận mù"). Phần XÁC NHẬN THÀNH TRACK
# (`do_confirm`) vẫn chỉ chạy khi đang bật + tự-do-quét + StaticBackgroundMask
# đã warmup — chỉ phần DUY TRÌ ảnh chụp là luôn chạy.
# Lý do cần "luôn chạy nền": `_start_auto_session()` trước đây RESET ảnh
# chụp về RỖNG mỗi lần bật, khiến vòng khám phá ĐẦU TIÊN sau MỖI LẦN BẬT
# phải xác nhận MÙ mọi candidate đang thấy (không có "trước" để so sánh) —
# nếu lúc đó có nhiễu đường viền/lưới chưa kịp bị StaticBackgroundMask lọc,
# nó lọt qua vĩnh viễn (đúng triệu chứng user báo: track giả từ đường viền
# đỏ/xanh dương/lục vẫn xuất hiện dù đã chạy "Phát tự động" nhiều phút). Nếu
# app đã chạy được >= 1 khoảng AUTO_DISCOVERY_INTERVAL_SEC TRƯỚC KHI user bật
# (thường đúng — user thường quan sát/chỉnh tâm/mốc trước khi bật), vòng
# khám phá đầu tiên đã có sẵn 1 ảnh chụp THẬT để so sánh ngay — đường viền/
# lưới tĩnh bị nhận ra "chưa đổi vị trí" từ vòng đầu tiên, thay vì được cấp
# "vé miễn kiểm tra" 1 lần như trước. Chỉ khi app VỪA mở (<1 khoảng
# AUTO_DISCOVERY_INTERVAL_SEC) rồi bật auto-scan ngay lập tức mới còn gặp lại
# vòng "xác nhận mù" 1 lần duy nhất — hiếm hơn hẳn so với trước (từng xảy ra
# ở MỌI lần bật, dù app đã chạy bao lâu).
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
# BUG đã báo (user: MAGENTA "thiếu track/không bắt được" — cùng LOẠI triệu
# chứng đã sửa cho GREEN bằng STATIC_EXPIRE_SEC, nhưng lần này ở 1 TẦNG KHÁC):
# so sánh "đã dịch chuyển hay chưa" ở đây LUÔN so với ẢNH CHỤP VÒNG NGAY
# TRƯỚC (`prev = _discovery_prev_snapshot`, rồi `_discovery_prev_snapshot =
# new_snapshot` ở cuối hàm) — nếu 1 vị trí candidate CÙNG MÀU tiếp tục xuất
# hiện Ở CÙNG CHỖ (trong AUTO_DISCOVERY_STATIC_TOL_PX) qua MỌI vòng khám phá
# liên tiếp (mục tiêu thật cập nhật CHẬM HƠN AUTO_DISCOVERY_INTERVAL_SEC=65s —
# y hệt giả thuyết đã xác nhận đúng cho GREEN/StaticNoiseFilter, nhưng ở đây
# chưa hề có cơ chế "hạn sử dụng" nào cả), nó bị `bo_qua_dung_yen` MÃI MÃI —
# không có gì để nó "thoát" ra được, dù chờ bao lâu, vì MỖI vòng đều so với
# vòng NGAY TRƯỚC (cũng luôn thấy nó ở đó). Fix: đếm THỜI GIAN LIÊN TỤC 1 vị
# trí (color, ô lưới theo AUTO_DISCOVERY_STATIC_TOL_PX) bị coi là "chưa đổi"
# — sau `DISCOVERY_STUCK_EXPIRE_SEC`, ép coi là "đã đổi" cho ĐÚNG 1 vòng (cho
# nó 1 cơ hội được xác nhận), rồi đặt lại đồng hồ — nhiễu tĩnh THẬT (không
# bao giờ thực sự đổi) sẽ bị `too_close_to_existing`/không đọc được OCR loại
# dần theo cách khác, còn mục tiêu thật đứng yên lâu có thêm cơ hội định kỳ
# thay vì KHÔNG BAO GIỜ.
_discovery_stuck_since   = {}   # (color, binx, biny) -> ts lần đầu bị coi "chưa đổi"
# Hạ 300 -> 150s (user báo "phải đợi rất lâu mới thấy mục tiêu mới" sau khi
# hằng số này ra đời). Lý do dám hạ MẠNH hơn STATIC_EXPIRE_SEC (vẫn giữ 300s,
# CHƯA đụng): đây là lớp bảo vệ THỨ HAI, có tính DƯ THỪA — hàng phòng thủ
# CHÍNH chống nhiễu tĩnh là StaticNoiseFilter/StaticBackgroundMask (chạy
# TRƯỚC, đã tự có "hạn sử dụng" riêng STATIC_HIT_LIMIT_SEC=35s/STATIC_EXPIRE_SEC
# =300s) — 1 candidate phải VƯỢT QUA lớp đó rồi mới tới được đây. Mục đích BAN
# ĐẦU của lớp NÀY (theo docstring gốc của `auto_confirm_nearby`) chỉ là tránh
# "xác nhận mù" ở vòng khám phá ĐẦU TIÊN sau khi bật auto-scan/zoom — không
# phải để lọc nhiễu tĩnh (việc đó StaticNoiseFilter đã làm) — nên không cần
# giữ mức 5 phút thận trọng như STATIC_EXPIRE_SEC. 150s (~2.3 vòng khám phá,
# AUTO_DISCOVERY_INTERVAL_SEC=65s) vẫn đủ để không "xác nhận lại" ngay vòng
# kế tiếp (tránh giật cục), nhưng giảm ~50% thời gian chờ tối đa cho mục tiêu
# thật đứng yên lâu ("quá cảnh"). CHƯA kiểm chứng trên nguồn thật — cần theo
# dõi có tăng track giả không sau khi hạ.
DISCOVERY_STUCK_EXPIRE_SEC = 150
# BUG đã sửa: vẫn còn 1 đường kích hoạt "vòng đầu tiên xác nhận mù" mà fix
# "ảnh chụp nền luôn chạy" (mục lịch sử ngay dưới `auto_confirm_nearby()`)
# CHƯA che kín — fix đó chỉ giải quyết trường hợp bật/tắt "Phát tự động"
# (không còn reset ảnh chụp khi bật), nhưng `_reset_discovery_snapshot()`
# (gọi khi ZOOM đổi) VẪN xoá `_discovery_prev_snapshot` về rỗng — nên vòng
# khám phá ĐẦU TIÊN sau MỖI LẦN ZOOM vẫn xác nhận MÙ mọi candidate đang
# thấy (giống hệt lỗ hổng cũ, chỉ đổi đường kích hoạt). Giả định cũ ("lúc
# đó StaticBackgroundMask cũng đang warmup lại nên do_confirm đã bị chặn
# riêng") KHÔNG LUÔN ĐÚNG — đo thực tế trên Wyse 5070: `static_bg.n_updates`
# vừa vượt ngưỡng 300 (vd 308) đúng lúc vòng khám phá đầu tiên sau zoom kích
# hoạt (do tốc độ detect thực tế thay đổi, 2 mốc thời gian không được đảm
# bảo thứ tự) — dẫn tới 8-9 track RED giả được xác nhận CÙNG LÚC, cụm gần
# nhau, không đọc được ID OCR nào — đúng chữ ký của nhiễu tĩnh lọt qua vòng
# xác nhận mù. Fix: thêm `_discovery_primed` — chỉ cho phép XÁC NHẬN
# (không phải duy trì ảnh chụp) khi đã có ÍT NHẤT 1 vòng khám phá THẬT (so
# với ảnh chụp CÓ DỮ LIỆU, không rỗng) kể từ lần reset gần nhất — trì hoãn
# thêm đúng 1 khoảng AUTO_DISCOVERY_INTERVAL_SEC sau mỗi lần zoom trước khi
# auto-scan xác nhận bất kỳ candidate nào, đổi lấy loại bỏ hẳn nguy cơ xác
# nhận mù ở đường kích hoạt này.
_discovery_primed = False

# ══════════════════════════════════════════════════════════════════════════════
# CHẨN ĐOÁN HÌNH DẠNG — user nhắc lại gợi ý hình dạng icon máy bay THẬT đã
# cung cấp trước đây (xem `createPlaneElement()` trong `radar_simulation.html`,
# KHÔNG ĐƯỢC SỬA theo yêu cầu đầu file — chỉ ĐỌC để tham khảo hình học ở đây):
# 1 thân ellipse dẹt ngang (rx=30,ry=5 trên viewBox 100×100 — RẤT mỏng so với
# chiều dài) + 2 CÁNH HÌNH TAM GIÁC toả ra 2 phía + 1 khối đuôi/mũi phức tạp
# hơn ở đầu còn lại — tổng thể đúng hình "ngôi sao/dấu hoa thị" (thân+cánh).
# Bounding box gần vuông (10-90 × 5-95 trên viewBox 100) NHƯNG diện tích thực
# tế LẤP ĐẦY hộp bao đó RẤT THẤP (cánh là tam giác NHỌN, 4 góc hộp bao gần
# như trống) — khác hẳn 1 khối nhiễu ĐẶC (đốm nền sau dilate, góc rẽ đường
# viền) vốn lấp gần đầy hộp bao của chính nó.
#
# User phản hồi trực tiếp: vùng loại trừ vĩnh viễn (mục lịch sử ngay trên)
# "không hiệu quả lắm" — dấu chấm than quá nhỏ để loại trừ đáng tin, vị trí
# tâm (mũi biển) loại trừ vĩnh viễn RỦI RO che mất 1 mục tiêu thật sau này
# bay ngang đúng chỗ đó. Hướng hình dạng (đã gợi ý) mới là hướng ĐÚNG hơn về
# lâu dài — nhưng LỊCH SỬ đã thử area/solidity(so với convex hull)/circularity/
# đếm convexity-defect trên blob ĐÃ QUA dilate và ĐỀU "chồng lấn" giữa icon
# thật và nhiễu góc rẽ đường viền (xem CLAUDE.md, mục USB_Video). CHƯA thử
# EXTENT (area / diện_tích_HỘP_BAO_CHỮ_NHẬT — khác solidity là area/convex_hull)
# — về hình học, cánh tam giác NHỌN phải cho extent THẤP HƠN RÕ RỆT so với 1
# khối đặc gần vuông sau dilate (extent gần 1.0). CHƯA CÓ DỮ LIỆU THẬT để xác
# nhận ngưỡng — hàm này CHỈ LOG, KHÔNG lọc gì (an toàn tuyệt đối, không đổi
# hành vi hiện có) — mục đích thu thập số liệu THẬT ở lần chạy tới để quyết
# định ngưỡng dựa trên dữ liệu, tránh lặp lại sai lầm "đoán rồi chỉnh" đã xảy
# ra 2 lần gần đây (luật màu RED/MAGENTA, vùng loại trừ vị trí).
def _shape_diag_at(frame, color, bx, by, radius=20):
    """Tính lại hình dạng (bw,bh,area,extent,solidity) của blob màu `color`
    gần (bx,by) nhất trong bán kính `radius` — CHỈ để log chẩn đoán, không
    dùng để lọc/quyết định gì. Trả về None nếu không tìm thấy blob nào."""
    try:
        h, w = frame.shape[:2]
        x0, x1 = max(0, bx - radius), min(w, bx + radius)
        y0, y1 = max(0, by - radius), min(h, by + radius)
        if x1 <= x0 or y1 <= y0:
            return None
        crop = frame[y0:y1, x0:x1]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        m = np.zeros(crop.shape[:2], np.uint8)
        for lo, hi in HSV_RANGES[color]:
            m = cv2.bitwise_or(m, cv2.inRange(hsv, np.array(lo), np.array(hi)))
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        m = cv2.dilate(m, np.ones((5, 5), np.uint8), iterations=1)
        n, lbl, stats, centroids = cv2.connectedComponentsWithStats(m, 8)
        if n <= 1:
            return None
        local_cx, local_cy = bx - x0, by - y0
        best_i, best_d = None, None
        for i in range(1, n):
            cx_i, cy_i = centroids[i]
            d = (cx_i - local_cx) ** 2 + (cy_i - local_cy) ** 2
            if best_d is None or d < best_d:
                best_d, best_i = d, i
        bw_, bh_, area_ = int(stats[best_i][2]), int(stats[best_i][3]), int(stats[best_i][4])
        extent = area_ / max(bw_ * bh_, 1)
        blob_mask = (lbl == best_i).astype(np.uint8) * 255
        contours, _ = cv2.findContours(blob_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        solidity = None
        if contours:
            hull = cv2.convexHull(contours[0])
            hull_area = cv2.contourArea(hull)
            if hull_area > 0:
                solidity = cv2.contourArea(contours[0]) / hull_area
        return {"bw": bw_, "bh": bh_, "area": area_, "extent": round(extent, 3),
                "solidity": round(solidity, 3) if solidity is not None else None}
    except Exception:
        return None

def _reset_discovery_snapshot():
    """Gọi khi zoom đổi (cùng lúc với noise_filter.reset()/static_bg.reset())
    — toạ độ pixel của ảnh chụp cũ hết ý nghĩa sau khi tỉ lệ km/px đổi, so
    sánh xuyên qua 1 lần zoom sẽ coi MỌI thứ (kể cả nền tĩnh) là "đã dịch
    chuyển". Đặt `_discovery_last_time = now` (không phải 0) để delay đúng 1
    khoảng AUTO_DISCOVERY_INTERVAL_SEC trước khi ảnh chụp đầu tiên SAU zoom
    được lấy lại. Đặt `_discovery_primed = False` — xem docstring hằng số
    ngay trên — để vòng khám phá ĐẦU TIÊN sau zoom đó chỉ populate ảnh chụp
    (không xác nhận gì), tránh xác nhận mù."""
    global _discovery_last_time, _discovery_prev_snapshot, _discovery_primed, _discovery_stuck_since
    _discovery_last_time = time.time()
    _discovery_prev_snapshot = {}
    _discovery_primed = False
    _discovery_stuck_since = {}

def auto_confirm_nearby(tm, frame_idx, unmatched_blips, static_bg=None, frame=None):
    """`frame`: khung hình HIỆN TẠI, CHỈ dùng cho `_shape_diag_at()` (log chẩn
    đoán hình dạng, xem docstring hàm đó) — không ảnh hưởng logic xác nhận
    nếu để `None` (tương thích ngược cho nơi gọi cũ/test không có frame).

    So ảnh chụp candidate hiện tại (trong bán kính GLOBAL_RADIUS) với ảnh
    chụp từ AUTO_DISCOVERY_INTERVAL_SEC giây trước — khi "Phát tự động"/chậm
    đang bật VÀ đang ở chế độ tự-do-quét, xác nhận (tạo track, auto=True)
    các candidate MỚI xuất hiện hoặc đã dịch chuyển kể từ lần trước. `unmatched_blips`
    đã được StaticNoiseFilter/StaticBackgroundMask lọc bỏ phần lớn nền tĩnh
    trước khi tới đây — xem docstring đầu file.

    ẢNH CHỤP NỀN LUÔN CHẠY, không phụ thuộc "Phát tự động" đang bật hay tắt
    (xem khối docstring lịch sử ngay trên, mục "vòng đầu tiên xác nhận mù").

    Tham số `static_bg`: chỉ gác cổng phần XÁC NHẬN (không gác phần duy trì
    ảnh chụp nền) — nếu `not static_bg.is_warmed_up()` (chưa đủ
    STATIC_BG_WARMUP_SEC giây THẬT kể từ lúc khởi tạo/reset gần nhất — đã đổi
    từ đếm số lần gọi sang đếm thời gian thật, xem CLAUDE.md), không tạo
    track mới ở vòng này (xem lịch sử AUTO_DISCOVERY_INTERVAL_SEC vs
    STATIC_BG_WARMUP lệch pha trong CLAUDE.md).

    `_discovery_primed`: gác cổng XÁC NHẬN thêm 1 lớp nữa — `was_primed`
    đọc giá trị NGAY TRƯỚC KHI đặt lại `True` cho vòng này, nên vòng ĐẦU
    TIÊN sau mỗi lần `_reset_discovery_snapshot()` (zoom đổi) chỉ populate
    ảnh chụp (không xác nhận gì, dù static_bg đã sẵn sàng) — vòng KẾ TIẾP
    mới thực sự so sánh + xác nhận. Tránh xác nhận mù ngay sau zoom (xem
    docstring hằng số `_discovery_primed` phía trên)."""
    global _discovery_last_time, _discovery_prev_snapshot, _discovery_primed, _discovery_stuck_since
    now = time.time()
    if now - _discovery_last_time < AUTO_DISCOVERY_INTERVAL_SEC:
        return
    candidates = [b for b in unmatched_blips if b[3] <= GLOBAL_RADIUS]
    prev = _discovery_prev_snapshot
    was_primed = _discovery_primed
    _discovery_last_time = now
    _discovery_primed = True
    new_snapshot = {}
    for bx, by, area, dist, bear, color, dx, dy in candidates:
        new_snapshot.setdefault(color, []).append((bx, by))

    do_confirm = (
        (_global_auto_active or _global_auto_slow_active)
        and _auto_scan_mode
        and was_primed
        and (static_bg is None or static_bg.is_warmed_up())
    )
    if do_confirm:
        # Log tổng hợp mỗi vòng khám phá (mỗi AUTO_DISCOVERY_INTERVAL_SEC=65s)
        # — user báo "Phát tự động đang bắt thiếu" mục tiêu thật. Đếm candidate
        # THEO MÀU thấy được ở vòng này (đã qua StaticNoiseFilter/StaticBackgroundMask/
        # filter_dense_candidates TRƯỚC khi tới đây) và lý do từng candidate
        # KHÔNG được xác nhận (đứng yên/đã có track gần đó) — nếu 1 màu có rất
        # ít candidate dù mắt thường thấy nhiều mục tiêu màu đó trên màn hình,
        # nghi vấn nằm ở CÁC LỚP LỌC TRƯỚC (detect_blips()/StaticNoiseFilter/
        # StaticBackgroundMask), không phải ở auto_confirm_nearby() này.
        _seen_by_color = {}
        _skip_unmoved = 0
        _skip_close = 0
        _skip_excluded = 0
        _new_confirmed = 0
        _stuck_seen_this_round = set()
        for bx, by, area, dist, bear, color, dx, dy in candidates:
            _seen_by_color[color] = _seen_by_color.get(color, 0) + 1
        for blip in candidates:
            bx, by, area, dist, bear, color, dx, dy = blip
            # Vùng đã bị operator đánh dấu loại trừ vĩnh viễn (Shift+Delete,
            # xem docstring trên `_auto_exclude_zones`) — kiểm tra TRƯỚC các
            # bước khác vì đây là quyết định CHẮC CHẮN NHẤT (do người xác
            # nhận trực tiếp), không cần tính toán gì thêm.
            if _is_auto_excluded(color, bx, by):
                _skip_excluded += 1
                continue
            moved_or_new = True
            for (px, py) in prev.get(color, []):
                if abs(bx - px) < AUTO_DISCOVERY_STATIC_TOL_PX and abs(by - py) < AUTO_DISCOVERY_STATIC_TOL_PX:
                    moved_or_new = False
                    break
            # HẠN SỬ DỤNG cho "chưa đổi" (xem docstring `_discovery_stuck_since`/
            # `DISCOVERY_STUCK_EXPIRE_SEC` phía trên) — 1 vị trí CÙNG MÀU đứng
            # yên qua MỌI vòng khám phá liên tiếp (so với vòng NGAY TRƯỚC, nên
            # KHÔNG BAO GIỜ tự "thoát" nếu không có cơ chế này) được cho 1 cơ
            # hội xác nhận sau khi tích luỹ đủ lâu, rồi đồng hồ đặt lại.
            _stuck_key = (color, bx // AUTO_DISCOVERY_STATIC_TOL_PX, by // AUTO_DISCOVERY_STATIC_TOL_PX)
            if not moved_or_new:
                _stuck_seen_this_round.add(_stuck_key)
                _first_stuck = _discovery_stuck_since.get(_stuck_key)
                if _first_stuck is None:
                    _discovery_stuck_since[_stuck_key] = now
                elif now - _first_stuck >= DISCOVERY_STUCK_EXPIRE_SEC:
                    moved_or_new = True
                    _discovery_stuck_since[_stuck_key] = now
            else:
                _discovery_stuck_since.pop(_stuck_key, None)
            if not moved_or_new:
                _skip_unmoved += 1
                continue
            # BUG đã sửa: hàm này trước đây chỉ so candidate với ẢNH CHỤP LẦN
            # TRƯỚC (`prev`), KHÔNG BAO GIỜ so với track ĐÃ XÁC NHẬN hiện có
            # (`tm.tracks`) — nếu 2 blip cùng màu đứng sát nhau (đội hình gần,
            # hoặc 1 blip thật + 1 mảnh vỡ/nhiễu chưa lọc hết) cùng "mới xuất
            # hiện" ở 1 chu kỳ khám phá, CẢ HAI đều bị xác nhận thành 2 TRACK
            # RIÊNG — rồi tranh nhau đúng 1 blip mãi mãi sau đó (thuật toán
            # "global nearest-pair" chỉ 1 track thắng mỗi chu kỳ), track thua
            # cuộc trượt dần tới MAX_LOST rồi bị xoá — đúng triệu chứng "tự mất"
            # user báo. Đo trực tiếp trên USB capture card thật: 12/12 ca "có
            # blip gần trong tầm nhưng vẫn mất khớp" đều do 1 track KHÁC cùng
            # màu đứng cách 0-20px cướp mất, khớp đúng cơ chế này. Fix: bỏ qua,
            # KHÔNG tạo track mới nếu đã có track cùng màu trong bán kính
            # `SHIFT_CLICK_SKIP_RADIUS` (10px — dùng lại đúng ngưỡng đã kiểm
            # chứng an toàn cho trường hợp tương tự ở Shift+Click thủ công, dưới
            # khoảng cách thật gần nhất giữa 2 mục tiêu khác nhau từng đo được).
            too_close_to_existing = False
            _cross_color_dup = None
            for info in tm.tracks.values():
                if not info["history"]:
                    continue
                _, edx, edy, _, _ = info["history"][-1]
                epx, epy = to_px(edx, edy)
                d = np.hypot(bx - epx, by - epy)
                if info["color"] == color:
                    if d < SHIFT_CLICK_SKIP_RADIUS:
                        too_close_to_existing = True
                        break
                elif d < CROSS_COLOR_DEDUP_RADIUS_PX:
                    # Xem docstring CROSS_COLOR_DEDUP_RADIUS_PX — khoảng cách
                    # này CHẮC CHẮN không phải 2 mục tiêu thật khác nhau.
                    too_close_to_existing = True
                    _cross_color_dup = (info["color"], d)
                    break
            if too_close_to_existing:
                _skip_close += 1
                if _cross_color_dup is not None:
                    print(f"[LOAI-TRUNG-LAP-KHAC-MAU] {color} @ px({bx},{by}) bo qua — da co "
                          f"track {_cross_color_dup[0]} cach {_cross_color_dup[1]:.1f}px "
                          f"(< {CROSS_COLOR_DEDUP_RADIUS_PX}px)", flush=True)
                continue
            # BỔ SUNG — user yêu cầu: nếu 1 track ĐÃ ĐƯỢC CHỈNH TAY (qua bảng
            # ID) sang đúng MÀU HIỂN THỊ của candidate này (`display_color ==
            # color`), và candidate đứng GẦN track đó — "rất có thể đang bắt
            # nhầm" (chính lời user). Đây là bằng chứng RẤT MẠNH: operator đã
            # TỰ TAY xác nhận track kia thực ra là màu `color`, dù máy phân
            # loại HSV ban đầu ra màu KHÁC — khớp đúng cơ chế "1 icon thật bị
            # chia đôi thành 2 màu HSV do rìa/anti-alias" đã ghi nhận nhiều
            # lần trong lịch sử project (RED/MAGENTA). Tính TRƯỚC (di chuyển
            # lên đây, trước `_new_confirmed`/`confirm_candidate`) để có thể
            # CHẶN HẲN thay vì chỉ cảnh báo suông như CANH BAO bên dưới — dùng
            # LẠI đúng bán kính 30px đã có sẵn (không phát minh số mới), chỉ
            # SIẾT quyết định (chặn) khi có thêm bằng chứng do CHÍNH NGƯỜI
            # DÙNG xác nhận, không áp dụng cho mọi cặp khác-màu-đứng-gần nói
            # chung (case đó vẫn chỉ cảnh báo, xem CANH BAO bên dưới).
            _nearest_other_color = None
            _nearest_other_info  = None
            for _info2 in tm.tracks.values():
                if _info2["color"] == color or not _info2["history"]:
                    continue
                _, _edx2, _edy2, _, _ = _info2["history"][-1]
                _epx2, _epy2 = to_px(_edx2, _edy2)
                _d2 = np.hypot(bx - _epx2, by - _epy2)
                if _nearest_other_color is None or _d2 < _nearest_other_color[0]:
                    _nearest_other_color = (_d2, _info2["color"])
                    _nearest_other_info  = _info2
            if (_nearest_other_color is not None and _nearest_other_color[0] < 30
                    and _nearest_other_info is not None
                    and _nearest_other_info.get("display_color") == color):
                _skip_close += 1
                print(f"[LOAI-TRUNG-LAP-DA-SUA-MAU] {color} @ px({bx},{by}) bo qua — "
                      f"cach {_nearest_other_color[0]:.1f}px 1 track "
                      f"({_nearest_other_color[1]}) da duoc chinh tay thanh mau {color} "
                      f"— rat co the la CUNG 1 muc tieu", flush=True)
                continue

            _new_confirmed += 1
            # Log chẩn đoán: user báo "Phát tự động" vẫn bám nhầm đường viền
            # đỏ/xanh dương/lục ngay cả sau vài phút chạy (đã loại trừ giả
            # thuyết chỉ do warmup chưa xong — xem CLAUDE.md). In peak EMA +
            # n_updates của StaticBackgroundMask NGAY LÚC xác nhận, để đối
            # chiếu: n_updates thấp bất thường => nghi bị reset lặp lại (zoom
            # bị coi là đổi liên tục, xem dòng "[LOC-NEN-PX] Reset" cùng
            # console); peak_ema thấp dù n_updates đủ cao => điểm này thực sự
            # CHƯA từng được StaticBackgroundMask ghi nhận là tĩnh (khác giả
            # thuyết warmup/reset).
            if static_bg is not None:
                _peak = static_bg.peak(color, bx, by)
                _peak_txt = f"{_peak:.3f}" if _peak is not None else "n/a"
                # Log chan doan HINH DANG — xem docstring day du tren
                # _shape_diag_at() — CHI THU THAP SO LIEU, khong loc gi.
                _shape_txt = "n/a"
                if frame is not None:
                    _shape = _shape_diag_at(frame, color, bx, by)
                    if _shape is not None:
                        _shape_txt = (f"bw={_shape['bw']} bh={_shape['bh']} "
                                       f"area={_shape['area']} extent={_shape['extent']} "
                                       f"solidity={_shape['solidity']}")
                # BỔ SUNG — user báo "vẫn nhầm đường dải là mục tiêu" ngay cả
                # sau khi có cơ chế bắc cầu tự động (StaticBackgroundMask
                # gộp+dilate, xem CLAUDE.md) — 2 con số mới để phân biệt ĐÚNG
                # nguyên nhân thay vì đoán tiếp:
                #   - `chua_du_am` (giây) = thời gian THẬT còn thiếu tới khi
                #     warmup xong (0 nếu đã warmup) — nếu > 0, candidate này
                #     bị xác nhận TRƯỚC KHI cơ chế bắc cầu kịp bật, không phải
                #     lỗi của chính cơ chế đó.
                #   - `diem_tinh_gan_nhat` (px) = khoảng cách tới điểm GẦN
                #     NHẤT đã ghi nhận tĩnh trong bán kính 40px (xem
                #     `nearest_static_px()`) — số nhỏ (gần STATIC_BG_BRIDGE_PX)
                #     nghĩa là "suýt bắt được", cần nới bán kính bắc cầu; số
                #     lớn/"khong co" nghĩa là vị trí này CHƯA từng được ghi
                #     nhận tĩnh ở bất kỳ đâu gần đó — khác nguyên nhân hoàn
                #     toàn (cần thêm thời gian tích luỹ, không phải bán kính).
                _elapsed_warmup = max(0.0, STATIC_BG_WARMUP_SEC - (time.time() - static_bg.start_time))
                _nearest = static_bg.nearest_static_px(bx, by)
                _nearest_txt = f"{_nearest:.1f}px" if _nearest is not None else "khong co (>40px)"
                print(f"[AUTO-CONFIRM-CHAN-DOAN] {color} @ px({bx},{by}) "
                      f"static_bg.n_updates={static_bg.n_updates} peak_ema={_peak_txt} "
                      f"(nguong={STATIC_BG_THRESHOLD}) chua_du_am={_elapsed_warmup:.1f}s "
                      f"diem_tinh_gan_nhat={_nearest_txt}  hinh_dang: {_shape_txt}", flush=True)
            # BỔ SUNG — user báo "mục tiêu đỏ nhầm thành lục" kèm ID đọc sai
            # (622->624): nghi vấn 1 đốm nhiễu KHÁC MÀU đứng SÁT 1 mục tiêu
            # thật bị xác nhận thành track riêng (dedup `too_close_to_existing`
            # ở trên CHỈ so CÙNG MÀU — cố ý, để không chặn 2 mục tiêu thật
            # khác màu đứng gần nhau, xem CLAUDE.md — nhưng vì vậy không chặn
            # được đốm nhiễu khác màu đứng sát mục tiêu thật). Dùng LẠI
            # `_nearest_other_color`/`_nearest_other_info` đã tính ở khối
            # ngay trên (không tính lại — không có gì thay đổi `tm.tracks`
            # giữa 2 điểm này trong cùng 1 lượt xét candidate).
            if _nearest_other_color is not None and _nearest_other_color[0] < 30:
                print(f"[AUTO-CONFIRM-CHAN-DOAN] {color} @ px({bx},{by}) — CANH BAO: "
                      f"track KHAC MAU ({_nearest_other_color[1]}) dung cach "
                      f"{_nearest_other_color[0]:.1f}px — nghi 2 track cho CUNG 1 muc tieu that",
                      flush=True)
            tm.confirm_candidate(frame_idx, bx, by, color, dx, dy, auto=True)

        # Dọn `_discovery_stuck_since` — vị trí không còn xuất hiện là candidate
        # "chưa đổi" ở vòng NÀY (đã di chuyển thật, đã bị lọc ở tầng trước, hay
        # đã được xác nhận thành track) không cần theo dõi tiếp, tránh phình to
        # qua 1 phiên dài.
        for _k in list(_discovery_stuck_since.keys()):
            if _k not in _stuck_seen_this_round:
                del _discovery_stuck_since[_k]

        print(f"[AUTO-SCAN-TONG-HOP] candidate_theo_mau={_seen_by_color} "
              f"xac_nhan_moi={_new_confirmed} bo_qua_dung_yen={_skip_unmoved} "
              f"bo_qua_da_co_track_gan={_skip_close} bo_qua_da_loai_tru={_skip_excluded}",
              flush=True)

    _discovery_prev_snapshot = new_snapshot

# ══════════════════════════════════════════════════════════════════════════════
# CHUỘT PHẢI / SHIFT+CLICK: đưa track vào bảng ID góc trên-trái
# ══════════════════════════════════════════════════════════════════════════════
# Trước đây có 1 dialog tkinter RIÊNG (tk.Tk() mới cho mỗi lần gọi) cho
# Shift+Click/chuột phải, tách biệt với bảng `_id_panel` góc trên-trái (chỉ
# dành cho track auto-scan). User yêu cầu gộp lại thành 1 bảng duy nhất
# (bảng góc trên-trái) — dùng chung đúng 1 cơ chế `_id_panel_queue` cho CẢ
# track tự-động phát hiện LẪN track chọn thủ công, thay vì duy trì 2 giao
# diện song song (cũng loại bỏ luôn rủi ro crash native đã từng gặp khi
# nhiều tk.Tk() root chạy đồng thời — xem lịch sử cũ trong CLAUDE.md).
def open_id_panel(tid, tm):
    """Đưa track vào hàng đợi bảng ID (`_id_panel`) — dùng cho Shift+Click
    và chuột phải. KHÔNG dùng cờ `queued_for_panel` (cờ đó chỉ cần cho vòng
    round-robin của auto-scan, lặp lại liên tục mỗi giây — xem
    `_global_auto_worker`): click thủ công là 1 sự kiện rời rạc, phải luôn
    mở lại được kể cả với track đã từng xác nhận từ trước (vd sửa lại chu kỳ
    phát).

    Đồng thời đưa `tid` vào `_ocr_priority_tids` (nếu chưa có ID OCR) — user
    yêu cầu: chọn mục tiêu thủ công cũng phải "tự động nhận diện luôn" thay
    vì chờ tới lượt trong hàng đợi round-robin — xem docstring
    `_ocr_priority_tids`."""
    if tid in tm.tracks:
        _id_panel_queue.put(tid)
        if tid not in _ocr_confirmed:
            _ocr_priority_tids.add(tid)

# ══════════════════════════════════════════════════════════════════════════════
# BLIP DETECTION
# ══════════════════════════════════════════════════════════════════════════════
BLIP_MAX_DIM        = 24    # px — cạnh tối đa hộp bao icon mục tiêu hợp lệ
BLIP_MIN_SOLIDITY   = 0.28  # area/(bw*bh) tối thiểu — loại nét đứt mảnh/dài
BLIP_ARTIFACT_DIM   = 9     # px — hộp bao ≤ mức này COI CHỪNG là 1 dấu chấm
BLIP_ARTIFACT_SOLID = 0.9   # ... nếu ĐỒNG THỜI đặc gần như tuyệt đối (hình
                             # vuông nhỏ hoàn hảo) — xem giải thích dưới.
# Nâng 8->9 (chỉ `radar_live_6.py`): log thật từ Wyse 5070 (`[AUTO-CONFIRM-
# CHAN-DOAN] RED @ px(777,559) ... hinh_dang: bw=7 bh=9 area=63 extent=1.0
# solidity=1.0` — CHÍNH XÁC chữ ký "chấm nền" mà bộ lọc này sinh ra để bắt)
# cho thấy 1 track RED "ma" được xác nhận CÁCH đúng 15px 1 track MAGENTA có
# sẵn (`CANH BAO: track KHAC MAU (MAGENTA) dung cach 15.0px — nghi 2 track
# cho CUNG 1 muc tieu that`, đúng triệu chứng user báo "nhầm tím với đỏ") —
# lọt qua CHỈ VÌ bh=9 > BLIP_ARTIFACT_DIM=8 cũ (1px). Đã kiểm chứng trên
# `phong_to.mp4` (6 khung hình thật) trước khi nâng: 8->9 KHÔNG loại bỏ bất
# kỳ blob RED/MAGENTA nào (chỉ loại thêm GREEN/CYAN — đã biết là 2 màu ô
# nhiễm nặng nhất) — an toàn. Đã thử nâng tiếp lên 10+ nhưng BẮT ĐẦU loại cả
# RED/MAGENTA thật (5 blob ở mức 10, tăng dần) — KHÔNG nâng thêm, chỉ dừng ở
# mức vừa đủ khớp đúng kích thước ghost đã đo được, không đoán thêm.
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

# BUG/tối ưu đã sửa: mỗi chu kỳ detect, 3 hàm riêng biệt (detect_blips(),
# StaticBackgroundMask.update(), _blip_color_mask() — hàm sau được gọi từ
# update_scale_from_reference() để dò mốc tỉ lệ) đều TỰ tính lại
# cv2.cvtColor(BGR2HSV) + cv2.inRange() cho TỪNG màu trên CÙNG 1 khung hình —
# thuần tuý trùng lặp phép tính (không có gì khác nhau về input/logic), chỉ
# tốn thêm CPU. Trên máy dev (nhanh) mỗi lần tốn ~10-25ms nên không thấy rõ,
# nhưng trên máy YẾU hơn (CPU chậm hơn), 3 lần lặp lại của phép tính vốn đã
# không rẻ trên khung 1920x1080 có thể cộng dồn thành phần lớn thời gian mỗi
# chu kỳ detect, gây giật/lag. Fix: tính HSV + mặt nạ màu THÔ (trước khi giới
# hạn theo vòng radar — đúng thứ tự các hàm trên vốn đã làm) đúng 1 LẦN mỗi
# chu kỳ, dùng chung qua tham số `precomputed` — không đổi bất kỳ phép tính
# hay ngưỡng nào, chỉ tránh lặp lại y hệt.
def _compute_color_masks(frame):
    """Trả về (hsv, {ten_mau: mat_na_tho}) — mat_na_tho là hợp các dải
    HSV_RANGES của màu đó trên TOÀN khung hình, CHƯA giới hạn theo vòng
    radar (mask_radar) hay bất kỳ bước lọc nào khác — đúng đầu vào mà
    detect_blips()/StaticBackgroundMask.update()/_blip_color_mask() cần,
    mỗi hàm tự áp dụng bước riêng của mình (giới hạn radar, morphology...)
    lên cùng 1 mặt nạ thô này."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    raw_masks = {}
    for name, ranges_np in _HSV_RANGES_NP.items():
        # Da so mau chi co 1 dai hue (tru RED, 2 dai do phai boc qua diem
        # gay 0/180 cua banh xe hue) — bo qua np.zeros()+bitwise_or() thua
        # cho truong hop 1 dai, ket qua toan hoc giong het (hop voi mang
        # rong luon = chinh no).
        if len(ranges_np) == 1:
            lo, hi = ranges_np[0]
            raw_masks[name] = cv2.inRange(hsv, lo, hi)
        else:
            m = cv2.inRange(hsv, ranges_np[0][0], ranges_np[0][1])
            for lo, hi in ranges_np[1:]:
                m = cv2.bitwise_or(m, cv2.inRange(hsv, lo, hi))
            raw_masks[name] = m
    return hsv, raw_masks

_mask_radar_cache = {"key": None, "mask": None}

def _get_mask_radar(h, w):
    """Cache vòng tròn giới hạn vùng dò (bán kính R_300KM quanh CX,CY) —
    trước đây `detect_blips()` VÀ `StaticBackgroundMask.update()` đều tự
    dựng lại mask này TỪ ĐẦU (np.zeros + cv2.circle trên toàn khung hình)
    MỖI CHU KỲ DETECT, dù CX/CY/R_300KM chỉ đổi khi chỉnh tâm radar thủ công
    (hiếm, luôn xảy ra TRƯỚC khi vòng lặp detect chính bắt đầu) — thuần tuý
    lãng phí, đo được là 1 phần đóng góp vào `detect_blip`/`static_bg_update`
    chậm trên PC yếu (Wyse 5070). Cache theo key (CX,CY,R_300KM,h,w): đổi 1
    trong các giá trị này (vd sau khi chỉnh tâm) tự động tính lại đúng, kết
    quả TOÁN HỌC giống hệt bản không cache — thuần tối ưu, không đổi hành vi."""
    global _mask_radar_cache
    key = (CX, CY, R_300KM, h, w)
    if _mask_radar_cache["key"] != key:
        m = np.zeros((h, w), np.uint8)
        cv2.circle(m, (CX, CY), R_300KM, 255, -1)
        _mask_radar_cache["key"] = key
        _mask_radar_cache["mask"] = m
    return _mask_radar_cache["mask"]

BLIP_CROP_PAD = 20   # px — lề an toàn quanh hình chữ nhật bao vòng tròn
                     # R_300KM khi cắt vùng xử lý (xem _radar_bbox()) — đủ
                     # rộng hơn hẳn kernel dilate 5x5 (cần 2px)/morphology
                     # OPEN 2x2 (cần ~1px) để morphology/dilate cho kết quả
                     # TOÁN HỌC GIỐNG HỆT bản không cắt tại mọi điểm bên
                     # trong vòng tròn — không đổi hành vi, chỉ tránh xử lý
                     # vùng NGOÀI vòng tròn vốn đã bị mask_radar loại bỏ.

def _radar_bbox(h, w, pad=0):
    x0 = max(0, CX - R_300KM - pad)
    y0 = max(0, CY - R_300KM - pad)
    x1 = min(w, CX + R_300KM + pad + 1)
    y1 = min(h, CY + R_300KM + pad + 1)
    return x0, y0, x1, y1

def detect_blips(img, precomputed=None):
    h, w = img.shape[:2]
    _hsv, color_masks = precomputed if precomputed is not None else _compute_color_masks(img)
    mask_radar = _get_mask_radar(h, w)
    # Cắt về đúng hình chữ nhật bao vòng tròn R_300KM (+ lề an toàn) TRƯỚC
    # khi chạy morphology/dilate/connectedComponents — mọi pixel NGOÀI vòng
    # tròn đã bị mask_radar loại bỏ hoàn toàn (bitwise_and) nên xử lý chúng
    # trên TOÀN khung hình 1920x1080 là lãng phí thuần tuý. Đo được: cắt
    # giảm ~2.5-3 lần số pixel phải xử lý (vòng tròn hiện tại chỉ chiếm
    # ~1/3 diện tích khung hình). Cần OFFSET lại centroid về toạ độ khung
    # hình GỐC trước khi trả kết quả (xem bx0+cx0 bên dưới) — đã kiểm chứng
    # bằng cách so kết quả TRƯỚC/SAU cắt trên nhiều khung hình thật, giống
    # hệt nhau (xem CLAUDE.md).
    cx0, cy0, cx1, cy1 = _radar_bbox(h, w, BLIP_CROP_PAD)
    mask_radar_c = mask_radar[cy0:cy1, cx0:cx1]

    kernel       = np.ones((5, 5), np.uint8)
    kernel_noise = np.ones((2, 2), np.uint8)
    raw = []
    for color_name, m_full in color_masks.items():
        m = m_full[cy0:cy1, cx0:cx1]
        m = cv2.bitwise_and(m, mask_radar_c)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel_noise)  # loai dom nhieu 1px
        m = cv2.dilate(m, kernel, iterations=1)                # noi pixel dut doan
        m = cv2.bitwise_and(m, mask_radar_c)

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
            # centroid tính trên toạ độ ĐÃ CẮT — cộng lại offset (cx0,cy0)
            # để về đúng toạ độ khung hình GỐC như trước khi cắt.
            shaped.append((int(centroids[i][0]) + cx0, int(centroids[i][1]) + cy0, int(area)))

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

def _color_diag_stage_counts(color_name, precomputed, h, w):
    """CHỈ dùng để chẩn đoán (`[LUC-CHAN-DOAN]`) — đo số PIXEL thô + số BLOB
    qua TỪNG BƯỚC lọc của `detect_blips()` cho 1 màu cụ thể, để biết candidate
    của màu đó bị mất Ở ĐÂU (mask HSV quá hẹp ngay từ đầu? hay bị lọc hình
    dạng/kích thước sau đó?) — thay vì chỉ thấy con số CUỐI CÙNG như
    `[AUTO-SCAN-TONG-HOP]`. Đọc-only, KHÔNG sửa/gọi lại `detect_blips()`,
    chỉ lặp lại đúng các bước morphology/lọc hình dạng của nó để quan sát
    (an toàn tuyệt đối cho pipeline detect thật — xem nguyên tắc "không đụng
    vào detect_blips()" đã áp dụng xuyên suốt file này)."""
    _hsv, color_masks = precomputed
    mask_radar = _get_mask_radar(h, w)
    cx0, cy0, cx1, cy1 = _radar_bbox(h, w, BLIP_CROP_PAD)
    mask_radar_c = mask_radar[cy0:cy1, cx0:cx1]
    m = color_masks[color_name][cy0:cy1, cx0:cx1]
    m = cv2.bitwise_and(m, mask_radar_c)
    raw_px = int(cv2.countNonZero(m))
    kernel_noise = np.ones((2, 2), np.uint8)
    kernel = np.ones((5, 5), np.uint8)
    m2 = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel_noise)
    m2 = cv2.dilate(m2, kernel, iterations=1)
    m2 = cv2.bitwise_and(m2, mask_radar_c)
    n, _lbl, stats, _centroids = cv2.connectedComponentsWithStats(m2, 8)
    n_shape_ok = 0
    n_after_artifact = 0
    for i in range(1, int(stats.shape[0])):
        x0, y0, bw, bh, area = stats[i]
        if area < 1 or area > 5000:
            continue
        if bw > BLIP_MAX_DIM or bh > BLIP_MAX_DIM:
            continue
        sol = area / max(bw * bh, 1)
        if sol < BLIP_MIN_SOLIDITY:
            continue
        n_shape_ok += 1
        if bw <= BLIP_ARTIFACT_DIM and bh <= BLIP_ARTIFACT_DIM and sol >= BLIP_ARTIFACT_SOLID:
            continue
        n_after_artifact += 1
    return raw_px, n_shape_ok, n_after_artifact

def filter_dense_candidates(unmatched_blips):
    """Lọc mật độ: loại các CANDIDATE (blip chưa khớp track nào) có > 1 hàng
    xóm cùng màu trong bán kính gần — dấu hiệu chuỗi chấm trên đường bay
    chấm chấm. CHỈ áp dụng cho candidate (auto-scan), KHÔNG áp dụng cho việc
    khớp blip↔track đã xác nhận (xem giải thích ở BLIP_DENSITY_MAX_NB phía
    trên `detect_blips()`) — nên máy bay thật bay theo đội hình sát nhau vẫn
    được các track ĐÃ XÁC NHẬN bám bình thường, chỉ ảnh hưởng tới việc có tự
    động tạo track MỚI cho candidate đó hay không.

    Đếm hàng xóm bằng NumPy (ma trận khoảng cách theo từng nhóm màu) thay vì
    2 vòng lặp Python lồng nhau (O(n²) thuần Python) — kết quả TOÁN HỌC giống
    hệt bản cũ (cùng ngưỡng bán kính, cùng ngưỡng số lượng), chỉ nhanh hơn
    trên máy yếu khi màn hình có nhiều candidate cùng lúc (đúng lúc CPU cần
    được "nhẹ tay" nhất)."""
    n = len(unmatched_blips)
    if n < 2:
        return list(unmatched_blips)
    xs     = np.array([b[0] for b in unmatched_blips], dtype=np.float64)
    ys     = np.array([b[1] for b in unmatched_blips], dtype=np.float64)
    colors = [b[5] for b in unmatched_blips]

    by_color = {}
    for i, c in enumerate(colors):
        by_color.setdefault(c, []).append(i)

    keep = [True] * n
    r2 = BLIP_DENSITY_RADIUS ** 2
    for idxs in by_color.values():
        if len(idxs) < 2:
            continue
        idxs = np.array(idxs)
        gx, gy = xs[idxs], ys[idxs]
        d2 = (gx[:, None] - gx[None, :]) ** 2 + (gy[:, None] - gy[None, :]) ** 2
        nb_counts = (d2 <= r2).sum(axis=1) - 1   # -1: bỏ chính nó (d=0)
        for local_i, global_i in enumerate(idxs):
            if nb_counts[local_i] > BLIP_DENSITY_MAX_NB:
                keep[int(global_i)] = False
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
# BUG đã sửa (phát hiện SAU khi user báo "Phát tự động bắt rất ít, nửa giờ
# mới được 2 mục tiêu"): `STATIC_HIT_LIMIT`/`STATIC_MISS_RESET` CŨ đếm theo
# SỐ LẦN GỌI `filter()` (= số chu kỳ detect), KHÔNG PHẢI thời gian thật — y
# hệt loại bug đã tìm và sửa cho `TrackManager.t_sec` (xem mục "t_sec đồng hồ
# thật" trong CLAUDE.md), nhưng lúc đó CHỈ sửa `TrackManager`, còn ghi chú rõ
# "CHƯA rà theo hướng thời gian thật cho các bộ đếm này" — đúng chỗ này là 1
# trong số đó. Trên máy CHẬM/tải DAO ĐỘNG (Wyse 5070 — đã đo: có lúc ~0.7s+
# thời gian THẬT cho 1 chu kỳ detect, so với giả định "~30fps" đúc trong
# comment "~30-40s @ 15-30fps" của `STATIC_HIT_LIMIT` cũ), 120 chu kỳ có thể
# tương ứng THỜI GIAN THẬT dài hơn hẳn dự tính — không sai về mặt AN TOÀN
# (chỉ loại nhiễu chậm hơn, không loại nhầm mục tiêu thật), nhưng đây là 1
# phần nguyên nhân khiến toàn bộ pipeline (StaticNoiseFilter → StaticBackgroundMask
# → auto_confirm_nearby, xem mục dưới) "chín" chậm hơn nhiều so với thiết kế
# trên máy yếu, cộng dồn thành "bắt rất ít" user báo.
# Fix: đổi hẳn sang đếm THỜI GIAN THỰC (`time.time()`) thay vì số lần gọi —
# hành vi ĐÚNG bằng ý nghĩa gốc bất kể máy nhanh/chậm/tải dao động ra sao.
STATIC_HIT_LIMIT_SEC  = 35   # giây — thay cho STATIC_HIT_LIMIT=120 chu kỳ cũ
                              # (~30-40s @ 15-30fps giả định) — CAO HƠN HẲN
                              # khoảng cập nhật thực tế 5-11s (biên độ an toàn
                              # ~3-4 lần) để không loại nhầm mục tiêu thật cập
                              # nhật rời rạc, nhưng vẫn chắc chắn loại được
                              # nhiễu tĩnh vĩnh viễn — giờ ĐÚNG 35 GIÂY THẬT
                              # trên MỌI tốc độ máy, không còn phụ thuộc nhịp
                              # detect thực tế nhanh/chậm ra sao.
STATIC_MISS_RESET_SEC = 2.0  # giây vắng mặt liên tiếp thì xoá đếm dồn (thay
                              # cho 3 chu kỳ cũ — ước lượng rộng rãi, đủ chịu
                              # vài chu kỳ mất khớp thoáng qua trên mọi tốc độ
                              # máy hợp lý).

# BUG đã báo (user: "để >1 tiếng vẫn chưa nhận diện nổi 5 mục tiêu lục" —
# KHÔNG PHẢI vấn đề dải màu, đã loại trừ bằng đo hue thật): `STATIC_HIT_LIMIT_SEC
# =35s` ở trên được hiệu chỉnh dựa trên khoảng cập nhật vị trí đo được cho mục
# tiêu RED (5-11+ giây, "Quân sự"/patrol) — nhưng GREEN mang nghĩa "Quá cảnh"
# (`_LOAI_VN`), rất có thể là loại mục tiêu di chuyển CHẬM HƠN NHIỀU (đứng
# yên/chờ lâu) — nếu 1 mục tiêu GREEN thật đứng yên LÂU HƠN 35s (hoàn toàn hợp
# lý cho "quá cảnh"), `self.static_set` loại nó VĨNH VIỄN — "vĩnh viễn" đúng
# nghĩa đen: không có cơ chế nào cho nó CƠ HỘI THỨ HAI, dù đợi bao lâu đi nữa
# (khớp đúng "để rất lâu >1 tiếng vẫn không thấy" — thời gian chờ THÊM không
# giúp gì vì đã bị loại NGAY từ giây thứ 35 rồi không bao giờ xét lại). Đối
# chiếu funnel `[LUC-PHEU-LOC]` xác nhận: candidate GREEN giảm rõ rệt qua
# `noise_filter`/`static_bg` theo THỜI GIAN (không phải theo dải màu).
# Fix: thêm HẠN SỬ DỤNG cho việc loại trừ — sau `STATIC_EXPIRE_SEC` (dài hơn
# HẲN STATIC_HIT_LIMIT_SEC, để không cho nhiễu THẬT quay lại quá thường
# xuyên), 1 vị trí đã bị loại được XÉT LẠI TỪ ĐẦU — nhiễu tĩnh THẬT (không
# bao giờ tự thay đổi) sẽ nhanh chóng bị loại lại (chỉ mất thêm
# STATIC_HIT_LIMIT_SEC=35s, một khoảng "hở" ngắn so với 300s), trong khi 1
# mục tiêu thật đứng yên LÂU sẽ có thêm 1 cơ hội được đưa vào vòng khám phá
# (`auto_confirm_nearby`, tự có cơ chế so ảnh chụp riêng để xác nhận đây là
# "mới thấy") mỗi 300s thay vì KHÔNG BAO GIỜ như trước.
STATIC_EXPIRE_SEC = 300   # giây — ~5 phút, dài hơn STATIC_HIT_LIMIT_SEC gần
                          # 9 lần (đủ để nhiễu THẬT tái tích luỹ gần hết trước
                          # lần hết hạn kế tiếp, không gây "lũ" candidate giả
                          # quay lại liên tục) nhưng đủ ngắn để không bắt user
                          # đợi hàng giờ mới có 1 cơ hội.

class StaticNoiseFilter:
    def __init__(self):
        self.hits = {}          # (color, binx, biny) -> [first_seen_ts, last_seen_ts]
        self.static_set = {}    # (color, binx, biny) -> ts luc bi loai (de tinh han su dung)

    def reset(self):
        self.hits.clear()
        self.static_set.clear()
        print("\n[LOC-NEN] Reset nen tinh (ty le km/px vua doi do zoom)", flush=True)

    def filter(self, unmatched_blips, static_bg=None):
        now = time.time()
        seen = set()
        out = []
        for blip in unmatched_blips:
            bx, by, area, dist, bear, color, dx, dy = blip
            key = (color, bx // STATIC_BIN_PX, by // STATIC_BIN_PX)
            seen.add(key)
            if key in self.static_set:
                # HẠN SỬ DỤNG (xem docstring STATIC_EXPIRE_SEC): loại trừ
                # KHÔNG còn là vĩnh viễn — sau đủ lâu, xét lại từ đầu. Đồng
                # bộ luôn `static_bg` (lớp lọc PIXEL riêng, EMA liên tục
                # không tự "hết hạn" — xem StaticBackgroundMask.expire_local())
                # tại ĐÚNG vị trí này, để 2 lớp không "vênh" nhau (StaticNoiseFilter
                # cho qua nhưng StaticBackgroundMask vẫn chặn ngay sau).
                if now - self.static_set[key] >= STATIC_EXPIRE_SEC:
                    del self.static_set[key]
                    self.hits.pop(key, None)
                    if static_bg is not None:
                        static_bg.expire_local(bx, by)
                else:
                    continue
            entry = self.hits.get(key)
            if entry is None:
                entry = [now, now]
                self.hits[key] = entry
            else:
                entry[1] = now
            if now - entry[0] >= STATIC_HIT_LIMIT_SEC:
                self.static_set[key] = now
                continue
            out.append(blip)
        for key in list(self.hits.keys()):
            if key in seen:
                continue
            _first_seen, last_seen = self.hits[key]
            if now - last_seen > STATIC_MISS_RESET_SEC:
                del self.hits[key]
        return out

    def is_static(self, color, x, y):
        """True nếu (color,x,y) rơi vào 1 ô đã được xác nhận là nền tĩnh lâu
        dài (đã tích luỹ đủ STATIC_HIT_LIMIT_SEC giây liên tục là candidate).
        Dùng để CẢNH BÁO (không chặn) khi Shift+click thủ công trúng đúng 1
        vị trí đã biết là bờ biển/đảo/lưới tĩnh — xem
        `SHIFT_CLICK_SKIP_RADIUS`/`_shift_state` nơi gọi."""
        return (color, x // STATIC_BIN_PX, y // STATIC_BIN_PX) in self.static_set

# ══════════════════════════════════════════════════════════════════════════════
# LỌC NỀN TĨNH THEO PIXEL (StaticBackgroundMask) — khác StaticNoiseFilter ở
# trên (vốn theo dõi TỪNG CANDIDATE ĐÃ QUA LỌC HÌNH DẠNG, streak theo ô lưới
# thô 4px): lớp này tích luỹ trực tiếp MASK MÀU THÔ (trước lọc hình dạng) qua
# thời gian bằng trung bình trượt (EMA) — pixel nào "luôn đúng màu" suốt cửa
# sổ tích luỹ (lưới bản đồ, đường viền khu vực bám sát, bờ biển/đảo — tất cả
# đứng yên TUYỆT ĐỐI, không bao giờ đổi) sẽ có EMA tiến gần 1.0; máy bay thật
# (dù cập nhật rời rạc mỗi 5-11s, xem StaticNoiseFilter ở trên) vẫn RỜI VỊ TRÍ
# theo thời gian nên EMA tại từng điểm cụ thể không bao giờ giữ được gần 1.0
# lâu như vậy.
#
# Lý do thêm lớp NÀY dù StaticNoiseFilter đã tồn tại: đo thực nghiệm trên
# phong_to.mp4 (tích luỹ mask màu thô qua 250 mẫu trải ~83s, KHÔNG qua bất kỳ
# lọc hình dạng/màu nào khác) cho thấy riêng tín hiệu THỜI GIAN đã giảm số
# blob thô rất mạnh: GREEN 391→12, CYAN 295→2, RED 199→18, YELLOW 239→7 (so
# với pipeline hiện tại đã lọc hình dạng công phu: 14/1/15/4) — đặc biệt CYAN
# từng bị ghi nhận "không tìm được đặc trưng màu/hình để tách bạch khỏi bờ
# biển/đảo" (xem CLAUDE.md, mục "Bug đã sửa: nhầm mục tiêu CYAN...") nay được
# giải quyết gần như triệt để bằng tín hiệu THỜI GIAN thay vì hình dạng/màu.
# Đã kiểm chứng bằng overlay trực quan: các điểm còn lại sau khi trừ mask
# tĩnh rơi đúng vào icon máy bay thật, không rơi vào lưới/đường viền/bờ biển.
#
# CHỈ áp dụng cho `unmatched` (candidate cho auto-scan), giống nguyên tắc đã
# thiết lập cho StaticNoiseFilter/filter_dense_candidates — KHÔNG áp dụng khi
# khớp blip↔track đã xác nhận, để không lặp lại bug "mục tiêu tự biến mất".
STATIC_BG_WINDOW_SEC      = 50    # giây — THAY cho STATIC_BG_WINDOW_UPDATES=300
                                   # chu kỳ cũ (~40-70s giả định @ nhịp detect
                                   # "bình thường") — số GIÂY THẬT để 1 pixel
                                   # TĨNH TUYỆT ĐỐI (luôn "on") đạt đúng
                                   # STATIC_BG_THRESHOLD, xem công thức tau
                                   # ngay dưới. Đúng bằng ý nghĩa gốc bất kể
                                   # máy nhanh/chậm/tải dao động ra sao (xem
                                   # BUG đã sửa trên STATIC_HIT_LIMIT_SEC —
                                   # cùng gốc rễ, sửa cùng lúc).
STATIC_BG_THRESHOLD       = 0.9   # ngưỡng EMA coi là "nền tĩnh" (đã quét
                                   # 0.90/0.95/0.98 trên dữ liệu thật — không
                                   # đổi kết quả, chọn 0.90 rộng rãi nhất)
# BUG đã sửa (tự phát hiện khi kiểm chứng lại trên đúng khung hình "CYAN lẫn
# bờ biển" — xem CLAUDE.md): công thức alpha=1/WINDOW cũ SAI toán học — với
# EMA `ema = ema*(1-alpha) + moi*alpha`, 1 pixel TĨNH TUYỆT ĐỐI (luôn "on")
# chỉ đạt `ema = 1-(1-alpha)^N` sau N lần cập nhật — với alpha=1/300, sau
# ĐÚNG 300 lần cập nhật chỉ đạt ~0.632, và cần tới ~690 lần mới chạm 0.9, KHÔNG
# PHẢI 300 như tưởng ban đầu. Đã sửa (bản trước): giải ngược alpha từ đúng số
# LẦN CẬP NHẬT mong muốn.
#
# BUG TIẾP đã sửa (sau khi user báo "Phát tự động bắt rất ít, nửa giờ mới
# được 2 mục tiêu"): "số lần cập nhật" vẫn đếm theo SỐ LẦN GỌI `update()`
# (mỗi chu kỳ detect), KHÔNG PHẢI thời gian thật — y hệt lớp bug đã tìm/sửa
# cho `TrackManager.t_sec` VÀ `StaticNoiseFilter` ngay trên (xem 2 mục đó
# trong CLAUDE.md) — công thức alpha CỐ ĐỊNH mỗi lần gọi ngầm giả định nhịp
# gọi ĐỀU ĐẶN theo 1 fps cụ thể; trên máy CHẬM/tải DAO ĐỘNG (Wyse 5070), số
# lần gọi trong 1 khoảng thời gian thật cho trước dao động mạnh → cửa sổ tích
# luỹ THỰC TẾ (tính bằng giây) co giãn theo, khác hẳn "~40-70s" dự tính.
# Fix: đổi từ "alpha cố định mỗi lần gọi" sang "alpha suy ra từ Δt THẬT giữa
# 2 lần gọi liên tiếp" (mô hình phân rã mũ theo hằng số thời gian `STATIC_BG_TAU`,
# giống RC circuit/phân rã phóng xạ — CHUẨN toán học cho "trung bình trượt
# theo THỜI GIAN" bất kể nhịp lấy mẫu đều hay không đều):
# `alpha(Δt) = 1 - exp(-Δt / tau)`, với `tau` giải ra để 1 pixel tĩnh tuyệt
# đối vừa chạm STATIC_BG_THRESHOLD sau đúng STATIC_BG_WINDOW_SEC giây THẬT
# (không phụ thuộc có bao nhiêu lần gọi trong khoảng đó).
STATIC_BG_TAU = -STATIC_BG_WINDOW_SEC / math.log(1.0 - STATIC_BG_THRESHOLD)
# BUG đã sửa (đo bằng số liệu THẬT — user báo "nhầm dải biển đảo thành mục
# tiêu xanh dương [CYAN]", đối chiếu log `[AUTO-CONFIRM-CHAN-DOAN]` thật):
# CẢ 4 track CYAN bị xác nhận nhầm trong CÙNG 1 vòng khám phá đều có
# `peak_ema=0.660` — giải ngược công thức EMA (`0.660 = 1-exp(-t/tau)`) ra
# đúng ~23.4 GIÂY tích luỹ liên tục, còn thiếu ~26.6 giây nữa mới chạm
# ngưỡng 0.9. Nguyên nhân: `is_warmed_up()` là 1 ĐỒNG HỒ DUY NHẤT tính từ
# lúc reset gần nhất — nếu 1 vùng CỤ THỂ (ở đây: dải bờ biển màu CYAN) chỉ
# BẮT ĐẦU được ghi nhận "on" từ GIỮA cửa sổ warmup (không phải ngay từ đầu —
# có thể do chính lúc đó mới bị phân loại đúng màu CYAN, hoặc do zoom/khởi
# động app xảy ra không đúng lúc), tới khi đồng hồ CHUNG báo "đã warmup xong"
# (STATIC_BG_WARMUP_SEC giây kể từ mốc reset), vùng đó vẫn CHƯA kịp tích luỹ
# đủ THỜI GIAN CỦA RIÊNG NÓ (cũng cần ~STATIC_BG_WINDOW_SEC giây tính từ lúc
# NÓ bắt đầu, không phải từ lúc reset) — 1 khoảng hở thời gian có thể xảy ra
# với BẤT KỲ vùng tĩnh nào "xuất hiện muộn" trong cửa sổ warmup, không chỉ
# CYAN. Fix: nới `STATIC_BG_WARMUP_SEC` thêm 30s (làm tròn lên từ mức thiếu
# ~26.6s đo được) — KHÔNG loại bỏ hoàn toàn khả năng này (1 vùng xuất hiện
# đủ muộn, sát mép cửa sổ warmup mới, vẫn có thể lọt — về lý thuyết không có
# giá trị hữu hạn nào loại trừ hẳn được), chỉ giảm xác suất. Cái giá phải trả
# CHỈ là auto-scan chờ lâu hơn 30s trước khi bắt đầu xác nhận BẤT KỲ candidate
# nào (cả thật lẫn giả) sau mỗi lần khởi động/zoom — chấp nhận được, đúng
# tinh thần "thà bỏ sót/chậm hơn còn hơn xác nhận nhầm" đã áp dụng xuyên suốt.
STATIC_BG_WARMUP_SEC      = STATIC_BG_WINDOW_SEC + 30  # < ngưỡng này (giây
                                   # THẬT kể từ lúc khởi tạo/reset gần nhất):
                                   # EMA chưa đủ "chín" — KHÔNG lọc gì cả, để
                                   # an toàn (thà bỏ sót nhiễu còn hơn lỡ loại
                                   # nhầm mục tiêu thật khi dữ liệu tích luỹ
                                   # chưa đủ).
STATIC_BG_MATCH_RADIUS    = 3     # px — dò quanh centroid candidate (không
                                   # chỉ đúng 1 điểm) vì centroid sau dilate/
                                   # lọc hình dạng của detect_blips() có thể
                                   # lệch vài px so với mask màu thô gốc.

# TỰ ĐỘNG nhận diện "đường/dải nhiễu tĩnh" — user hỏi thẳng "sao không cho
# nhận đường dải luôn, tự động ấy" thay vì phải Shift+Delete từng điểm
# (xem `_auto_exclude_zones`/`_is_auto_excluded` — cơ chế THỦ CÔNG). Câu trả
# lời: dữ liệu để làm việc này ĐÃ CÓ SẴN ngay trong `self.ema` — mỗi màu là 1
# mảng EMA TOÀN KHUNG HÌNH (không phải danh sách điểm rời rạc), nên thay vì
# chỉ hỏi "đúng điểm (x,y) này có tĩnh không" (is_static(), theo ĐÚNG 1 màu),
# có thể GỘP CẢ 5 MÀU thành 1 mask nhị phân rồi DILATE nhẹ để tự động "bắc
# cầu" qua khe hở giữa các dấu chấm/nét đứt liền kề của CÙNG 1 đường viền —
# không cần operator đánh dấu tay bất kỳ điểm nào, và tự PHỤC HỒI nếu sau
# này 1 mục tiêu thật thường trực đi qua đúng chỗ đó (EMA sẽ tự hạ dần nếu
# không còn "luôn on" ở đó nữa, do bản chất công thức phân rã mũ — không cần
# reset tay).
# Gộp qua MỌI MÀU (không chỉ màu của candidate đang xét) vì đã quan sát thực
# tế: 1 đường viền tĩnh có thể bị phân loại màu KHÁC NHAU thoáng qua giữa
# các khung hình (cùng 1 chỗ có lúc RED có lúc GREEN, do nhiễu nén/anti-alias)
# — chỉ cần ĐÃ từng được xác nhận tĩnh ở BẤT KỲ màu nào là đủ để loại trừ.
STATIC_BG_BRIDGE_PX = 8   # px — bán kính dilate cho mask nền tĩnh GỘP MÀU.
                          # CỐ Ý chọn THẬN TRỌNG (nhỏ hơn BLIP_MERGE_RADIUS/
                          # SHIFT_CLICK_SKIP_RADIUS=10, dưới hẳn khoảng cách
                          # tối thiểu thật đo được giữa 2 mục tiêu khác nhau
                          # ~13-16px) — chỉ đủ bắc cầu khe hở nhỏ giữa các nét
                          # đứt SÁT NHAU (thường vài px do anti-alias/nén),
                          # không đủ rộng để nuốt luôn 1 mục tiêu thật đứng
                          # gần đường viền (đã ghi nhận trước đây: có mục tiêu
                          # thật nằm cách đường viền chưa đầy 1px — dilate quá
                          # tay ở đây rủi ro cao hơn hẳn so với vòng loại trừ
                          # thủ công AUTO_EXCLUDE_RADIUS_PX, vì áp dụng tự
                          # động cho MỌI vị trí không cần operator xác nhận).

# 2 TỐI ƯU HIỆU NĂNG cho `_rebuild_merged_mask()` — user hỏi thẳng "có đảm
# bảo phân phối luồng cho Wyse 5070 không" ngay sau khi tính năng trên được
# thêm — đúng lo ngại chính đáng: bản đầu tiên gộp+dilate trên TOÀN khung
# hình 1920x1080 MỖI CHU KỲ DETECT, chưa áp dụng 2 bài học tối ưu ĐÃ CÓ SẴN
# trong chính file này cho đúng loại phép tính này:
#   1. **Cắt về hình chữ nhật bao vòng tròn radar** (`_radar_bbox()`, cùng kỹ
#      thuật đã dùng cho `detect_blips()` — đo được nhanh hơn ~2.4-3 lần khi
#      áp dụng ở đó, xem CLAUDE.md) — mọi pixel NGOÀI vòng tròn R_300KM đã
#      LUÔN LÀ 0 trong `self.ema` (do `update()` đã `bitwise_and` với
#      `mask_radar` từ trước), nên gộp+dilate trên toàn khung hình là lãng
#      phí thuần tuý ~2/3 diện tích. Đệm thêm đúng `STATIC_BG_BRIDGE_PX` quanh
#      bbox (như `BLIP_CROP_PAD` đã làm cho kernel dilate của `detect_blips()`)
#      để dilate cho kết quả TOÁN HỌC giống hệt bản không cắt tại mọi điểm
#      bên trong vòng tròn.
#   2. **Throttle theo THỜI GIAN THẬT** (không phải theo số lần gọi — đúng
#      bài học đã trả giá đắt ở `t_sec`/`STATIC_HIT_LIMIT_SEC`/`STATIC_BG_TAU`,
#      xem CLAUDE.md: throttle theo SỐ LẦN GỌI ngầm giả định 1 nhịp fps cụ
#      thể, sai lệch trên máy chậm/tải dao động). EMA gốc đổi RẤT CHẬM
#      (`STATIC_BG_TAU≈21.7s`) nên mask GỘP+DILATE dẫn xuất từ nó không cần
#      dựng lại ở tần suất MỖI CHU KỲ DETECT — dựng lại tối đa 1 lần mỗi
#      `STATIC_BG_MERGE_REFRESH_SEC` giây THẬT là đủ mới, độ trễ thêm vào
#      (tối đa vài giây) không đáng kể so với thời gian tích luỹ 50s+ để 1
#      pixel được coi là "tĩnh" ngay từ đầu.
STATIC_BG_MERGE_REFRESH_SEC = 1.0

# BUG hiệu năng tự bắt được lúc đo (KHÔNG phải suy đoán): `cv2.dilate()` với
# kernel MORPH_ELLIPSE 17x17 (bán kính STATIC_BG_BRIDGE_PX=8) đo được ~12ms
# trên vùng đã cắt (845x845px) — chiếm > 60% tổng thời gian `_rebuild_merged_mask()`
# dù đã cắt bbox. Đo lại bằng benchmark riêng: đổi sang MORPH_RECT CÙNG kích
# thước → còn ~0.5ms (nhanh hơn ~8-25 lần, vì OpenCV tối ưu dilate hình chữ
# nhật bằng thuật toán TÁCH TRỤC ngang/dọc riêng — không áp dụng được cho
# hình elip/tổng quát). Đánh đổi hình học CHẤP NHẬN ĐƯỢC: kernel chữ nhật
# "bắc cầu" xa hơn ở đường CHÉO so với elip cùng bán kính (khoảng cách Chebyshev
# r=8px thay vì Euclid đẳng hướng r=8px mọi hướng — ở góc chéo, khoảng cách
# Euclid thực tế nới ra ~8×√2≈11.3px) — VẪN dưới khoảng cách tối thiểu thật
# đo được giữa 2 mục tiêu khác nhau (~13-16px, còn dư ~1.7-4.7px biên an
# toàn), nên không đổi kết luận an toàn đã tính cho STATIC_BG_BRIDGE_PX=8.
# Kernel không đổi trong suốt vòng đời chương trình (chỉ phụ thuộc hằng số
# STATIC_BG_BRIDGE_PX) — precompute 1 LẦN ở cấp module thay vì gọi
# `cv2.getStructuringElement()` lại mỗi lần rebuild (tự nó rẻ, ~0.14ms đo
# được, nhưng không có lý do gì để làm lại mỗi lần).
_STATIC_BG_BRIDGE_KERNEL = cv2.getStructuringElement(
    cv2.MORPH_RECT, (STATIC_BG_BRIDGE_PX * 2 + 1, STATIC_BG_BRIDGE_PX * 2 + 1))

class StaticBackgroundMask:
    def __init__(self):
        self.ema = {}       # color_name -> np.float32 (h,w), None nếu chưa có
        self.n_updates = 0        # chỉ để LOG/chẩn đoán — KHÔNG còn dùng để
                                   # gác cổng warmup (xem is_warmed_up()).
        self.start_time = time.time()
        self._last_update_time = None
        self._merged_dilated = None   # cache — throttle theo STATIC_BG_MERGE_REFRESH_SEC
        self._merged_offset = (0, 0)  # (cx0,cy0) của bbox đã cắt, xem is_static_any()
        self._merged_rebuild_time = 0.0

    def reset(self):
        self.ema = {}
        self.n_updates = 0
        self.start_time = time.time()
        self._last_update_time = None
        self._merged_dilated = None
        self._merged_offset = (0, 0)
        self._merged_rebuild_time = 0.0
        print("\n[LOC-NEN-PX] Reset mask nen tinh theo pixel (ty le km/px vua doi do zoom)",
              flush=True)

    def is_warmed_up(self):
        return time.time() - self.start_time >= STATIC_BG_WARMUP_SEC

    def update(self, frame, precomputed=None):
        # BUG/tối ưu đã sửa: đo bằng benchmark trực tiếp — công thức EMA cũ
        # (`(m>0).astype(float32)` rồi `prev*(1-a) + binary*a` bằng NumPy)
        # tốn ~15ms/màu trên khung 1920x1080 (5 màu × mỗi chu kỳ detect = có
        # thể ~75ms chỉ riêng phần này). `cv2.accumulateWeighted()` làm ĐÚNG
        # cùng phép tính EMA (`dst = dst*(1-alpha) + src*alpha`) trong 1 lệnh
        # gọi OpenCV tối ưu sẵn (không cần tạo mảng `binary` trung gian) — đo
        # được nhanh hơn ~17.7 lần (0.85ms/màu) trên cùng kích thước khung
        # hình, số liệu EMA sai khác chỉ ~1e-6 (nhiễu làm tròn float32, không
        # ảnh hưởng ngưỡng `STATIC_BG_THRESHOLD=0.9`). Khác biệt duy nhất:
        # `m` là mặt nạ 0/255 (không phải 0/1), nên EMA tích luỹ theo thang
        # 0-255 thay vì 0-1 — `is_static()` so ngưỡng nhân thêm 255 để giữ
        # đúng Ý NGHĨA ngưỡng cũ (không đổi hành vi, chỉ đổi thang đo).
        now = time.time()
        dt = 0.0 if self._last_update_time is None else (now - self._last_update_time)
        self._last_update_time = now
        # alpha=0 ở lần gọi đầu tiên (dt=0) — tương đương "không tích luỹ gì"
        # (prev vẫn là 0 lúc khởi tạo), đúng ý gốc "chưa có dữ liệu thì thôi".
        alpha = 1.0 - math.exp(-dt / STATIC_BG_TAU) if dt > 0 else 0.0
        h, w = frame.shape[:2]
        _hsv, color_masks = precomputed if precomputed is not None else _compute_color_masks(frame)
        mask_radar = _get_mask_radar(h, w)
        for color_name, m in color_masks.items():
            m = cv2.bitwise_and(m, mask_radar)
            prev = self.ema.get(color_name)
            if prev is None or prev.shape != (h, w):
                # Khởi tạo tại 0 (không copy thẳng mẫu đầu) để tránh 1 lần
                # xuất hiện ngẫu nhiên "đóng băng" EMA ở mức cao ngay từ đầu —
                # xem giải thích trong docstring khối trên.
                prev = np.zeros((h, w), dtype=np.float32)
            if alpha > 0:
                self.ema[color_name] = cv2.accumulateWeighted(m, prev, alpha)
            else:
                self.ema[color_name] = prev
        self.n_updates += 1

    def is_static(self, color, x, y):
        if not self.is_warmed_up():
            return False
        arr = self.ema.get(color)
        if arr is None:
            return False
        h, w = arr.shape
        r = STATIC_BG_MATCH_RADIUS
        x0, x1 = max(0, x - r), min(w, x + r + 1)
        y0, y1 = max(0, y - r), min(h, y + r + 1)
        patch = arr[y0:y1, x0:x1]
        if patch.size == 0:
            return False
        # arr tích luỹ theo thang 0-255 (xem update()) — nhân ngưỡng lên
        # tương ứng, giữ ĐÚNG ý nghĩa ngưỡng cũ (0-1).
        return float(patch.max()) >= STATIC_BG_THRESHOLD * 255.0

    def peak(self, color, x, y):
        """EMA cao nhất (0-1) quanh (x,y) cho `color` — chỉ để CHẨN ĐOÁN
        (in log ở auto_confirm_nearby), không dùng trong is_static()/filter()."""
        arr = self.ema.get(color)
        if arr is None:
            return None
        h, w = arr.shape
        r = STATIC_BG_MATCH_RADIUS
        x0, x1 = max(0, x - r), min(w, x + r + 1)
        y0, y1 = max(0, y - r), min(h, y + r + 1)
        patch = arr[y0:y1, x0:x1]
        if patch.size == 0:
            return None
        return float(patch.max()) / 255.0

    def expire_local(self, x, y, radius=None):
        """Xoá (đưa về 0) EMA của MỌI MÀU trong 1 vùng nhỏ quanh (x,y) — gọi
        từ `StaticNoiseFilter.filter()` khi 1 vị trí vừa HẾT HẠN loại trừ
        (xem docstring `STATIC_EXPIRE_SEC`), để đồng bộ CẢ 2 lớp lọc nền tĩnh
        cùng lúc "quên" vị trí đó — nếu chỉ xoá ở `StaticNoiseFilter` mà
        không xoá ở đây, lớp PIXEL (EMA liên tục, không có khái niệm "hạn sử
        dụng" nội tại — 1 pixel LUÔN "on" thì EMA hội tụ và GIỮ NGUYÊN ở mức
        cao mãi mãi, không tự giảm) sẽ tiếp tục chặn ngay lập tức, khiến việc
        hết hạn ở lớp kia vô nghĩa. CHỈ xoá CỤC BỘ (bán kính nhỏ quanh 1 vị
        trí cụ thể, mặc định `STATIC_BG_MATCH_RADIUS*3` — rộng hơn bán kính
        so khớp bình thường 1 chút để chắc chắn trùm hết vùng đã gây loại
        trừ) — KHÔNG xoá toàn khung hình, để không tạo ra 1 đợt "hồi sinh"
        hàng loạt nhiễu tĩnh cùng lúc (rủi ro chính nếu làm mới TOÀN BỘ EMA
        định kỳ thay vì chỉ đúng vị trí vừa hết hạn)."""
        if radius is None:
            radius = STATIC_BG_MATCH_RADIUS * 3
        for arr in self.ema.values():
            h, w = arr.shape
            x0, x1 = max(0, x - radius), min(w, x + radius + 1)
            y0, y1 = max(0, y - radius), min(h, y + radius + 1)
            if x1 > x0 and y1 > y0:
                arr[y0:y1, x0:x1] = 0.0

    def _rebuild_merged_mask(self):
        """Gộp EMA của MỌI MÀU thành 1 mask nhị phân "đã xác nhận nền tĩnh",
        rồi DILATE nhẹ (`STATIC_BG_BRIDGE_PX`) để tự động bắc cầu qua khe hở
        giữa các nét đứt/chấm liền kề của cùng 1 đường viền — xem docstring
        khối hằng số `STATIC_BG_BRIDGE_PX` phía trên. Gọi tối đa 1 lần mỗi
        `STATIC_BG_MERGE_REFRESH_SEC` giây THẬT (từ `filter()`, ngay dưới,
        không phải mỗi chu kỳ detect — xem docstring khối hằng số đó).
        CẮT về hình chữ nhật bao vòng tròn radar (+ đệm `STATIC_BG_BRIDGE_PX`)
        trước khi gộp/dilate — mọi pixel ngoài vòng tròn đã luôn là 0 trong
        `self.ema` (do `update()` đã `bitwise_and` với `mask_radar`), nên xử
        lý chúng là lãng phí thuần tuý (xem docstring khối hằng số phía trên,
        cùng kỹ thuật đã dùng cho `detect_blips()`)."""
        if not self.ema:
            self._merged_dilated = None
            return
        h, w = next(iter(self.ema.values())).shape
        cx0, cy0, cx1, cy1 = _radar_bbox(h, w, STATIC_BG_BRIDGE_PX)
        thresh = STATIC_BG_THRESHOLD * 255.0
        merged = None
        for arr in self.ema.values():
            binary = arr[cy0:cy1, cx0:cx1] >= thresh
            merged = binary if merged is None else (merged | binary)
        if merged is None or not merged.any():
            self._merged_dilated = None
            return
        merged_u8 = merged.astype(np.uint8) * 255
        self._merged_dilated = cv2.dilate(merged_u8, _STATIC_BG_BRIDGE_KERNEL)
        self._merged_offset = (cx0, cy0)

    def is_static_any(self, x, y):
        """True nếu (x,y) rơi vào (hoặc đủ gần, xem STATIC_BG_BRIDGE_PX) 1
        vùng đã được xác nhận nền tĩnh ở BẤT KỲ MÀU NÀO — gộp + bắc cầu TỰ
        ĐỘNG, không cần operator đánh dấu tay (khác `_is_auto_excluded()`,
        cơ chế Shift+Delete thủ công/lưu file). Dùng `self._merged_dilated`
        đã dựng sẵn trong `filter()` — gọi hàm này TRƯỚC khi dựng mask (vd
        gọi rời rạc để test/debug) sẽ luôn trả về False. (x,y) là toạ độ
        khung hình GỐC — quy đổi về toạ độ cục bộ của bbox đã cắt bằng
        `self._merged_offset` trước khi tra bảng."""
        if not self.is_warmed_up() or self._merged_dilated is None:
            return False
        cx0, cy0 = self._merged_offset
        lx, ly = x - cx0, y - cy0
        h, w = self._merged_dilated.shape
        if not (0 <= lx < w and 0 <= ly < h):
            return False
        return bool(self._merged_dilated[ly, lx])

    def nearest_static_px(self, x, y, max_search=40):
        """CHẨN ĐOÁN CHỈ (không dùng trong filter()/is_static_any()): khoảng
        cách (px) tới điểm GẦN NHẤT đã được `_merged_dilated` xác nhận tĩnh,
        trong bán kính `max_search` quanh (x,y) — trả None nếu không có điểm
        nào trong bán kính đó. Dùng để đo "suýt bị loại" (khoảng cách nhỏ,
        gần ngưỡng STATIC_BG_BRIDGE_PX) so với "hoàn toàn chưa từng được ghi
        nhận tĩnh ở đây" (None hoặc khoảng cách lớn) — xem
        `[AUTO-CONFIRM-CHAN-DOAN]` nơi gọi hàm này."""
        if not self.is_warmed_up() or self._merged_dilated is None:
            return None
        cx0, cy0 = self._merged_offset
        lx, ly = x - cx0, y - cy0
        h, w = self._merged_dilated.shape
        r = max_search
        x0, x1 = max(0, lx - r), min(w, lx + r + 1)
        y0, y1 = max(0, ly - r), min(h, ly + r + 1)
        patch = self._merged_dilated[y0:y1, x0:x1]
        ys, xs = np.nonzero(patch)
        if len(xs) == 0:
            return None
        dists = np.hypot(xs + x0 - lx, ys + y0 - ly)
        return float(dists.min())

    def filter(self, unmatched_blips):
        if not self.is_warmed_up():
            return unmatched_blips
        now = time.time()
        # Throttle THUẦN THEO THỜI GIAN THẬT (`_merged_rebuild_time` khởi tạo
        # 0.0 nên lần gọi ĐẦU TIÊN luôn "quá hạn", tự rebuild bình thường) —
        # KHÔNG kiểm tra thêm `self._merged_dilated is None` (bug đã tự bắt
        # được lúc test: nếu 1 lần rebuild hợp lệ nhưng CHƯA có vùng tĩnh nào
        # đạt ngưỡng — bình thường ở đầu phiên — kết quả hợp lệ CŨNG là None,
        # dùng "is None" làm điều kiện rebuild lại sẽ vô tình rebuild MỌI lần
        # gọi thay vì throttle, phản tác dụng đúng thứ đang cố tối ưu).
        if now - self._merged_rebuild_time >= STATIC_BG_MERGE_REFRESH_SEC:
            self._rebuild_merged_mask()
            self._merged_rebuild_time = now
        return [b for b in unmatched_blips if not self.is_static_any(b[0], b[1])]

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

# BUG NGHIÊM TRỌNG đã sửa: user gửi log THẬT (`ket_qua_test.txt`, phiên ~15
# phút, nguồn USB capture card) cho thấy `km/px` TRÔI LIÊN TỤC suốt cả phiên
# — từ 0.7367 lên tới 1.2039 (tăng ~63%!) — dù không có bằng chứng video vừa
# zoom lớn đến vậy (chỉ 2-3 lần "[LOC-NEN] Reset..." thật sự vượt ngưỡng
# 15%, phần còn lại trôi ÂM THẦM, LIÊN TỤC qua hàng trăm chu kỳ detect). Đây
# rất có thể là NGUYÊN NHÂN GỐC của CẢ 3 triệu chứng user báo cùng lúc: "bắt
# nhầm mục tiêu", "chọn tay 1 mục tiêu, điểm bám lại đi sang mục tiêu khác",
# và "rất ít mục tiêu được nhận diện dù đợi rất lâu" — vì MỌI vị trí pixel
# trong toàn hệ thống đều tính lại từ km qua `to_px()` dùng `KM_PX` TOÀN CỤC
# hiện tại (nguyên tắc xuyên suốt file này) — nếu `KM_PX` tự trôi dù video
# đứng yên, MỌI icon/track/candidate hiển thị SAI VỊ TRÍ ngày càng xa dần so
# với nội dung video thật, và các mốc thời gian tĩnh (StaticBackgroundMask)
# liên tục bị coi là "vừa zoom" mỗi khi trôi vượt 15%, phải RESET + warmup
# lại từ đầu — giải thích đúng "rất ít mục tiêu dù đợi rất lâu".
#
# Truy ra cơ chế: `_ref_refresh_template()` (gọi mỗi chu kỳ CHẤP NHẬN kết
# quả khớp, không có ngưỡng riêng) đặt `template_k = k` với `k =
# scale_rel * template_k_CŨ` (xem `_ref_match()`, field "k") — tức là
# `template_k` là TÍCH LUỸ NHÂN DỒN qua MỌI chu kỳ đã chấp nhận kể từ lúc
# đặt mốc, KHÔNG PHẢI đo lại độc lập mỗi lần từ 2 hằng số vật lý cố định
# (`real_km`/`offset0`). Nếu `scale_rel` (hệ số biến đổi RANSAC đo được MỖI
# CHU KỲ giữa khung hình hiện tại và MẪU HIỆN TẠI) có dù chỉ 1 SAI SỐ HỆ
# THỐNG RẤT NHỎ (vd lệch trung bình ~0.1-0.2% mỗi lần, do nhiễu lượng tử hoá
# lúc resize/resample mẫu mới, hoặc thiên lệch nhẹ trong cách RANSAC ước
# lượng affine) — sai số này NHÂN DỒN THEO CẤP SỐ NHÂN qua HÀNG TRĂM chu kỳ
# chấp nhận trong 1 phiên dài (mỗi chu kỳ detect có thể chấp nhận 1 lần khớp
# mới), y hệt lỗi "trôi tích luỹ" kinh điển của hệ thống tự tham chiếu vào
# CHÍNH đầu ra của nó mà không có cơ chế hiệu chỉnh lại — hoàn toàn khớp
# đúng độ lớn quan sát được (0.1-0.2%/chu kỳ, luỹ thừa qua ~500 chu kỳ, cho
# ra đúng bậc độ lớn ~63% tổng).
#
# Fix: CHỈ làm mới mẫu (`_ref_refresh_template`) khi `scale_rel` (hệ số biến
# đổi ĐO ĐƯỢC NGAY LÚC ĐÓ, TRƯỚC khi nhân dồn vào template_k) lệch khỏi 1.0
# ÍT NHẤT `REF_REFRESH_MIN_SCALE_CHANGE` — video ĐANG ĐỨNG YÊN tỉ lệ (đa số
# thời gian 1 phiên thật) sẽ có `scale_rel` dao động rất gần 1.0 mỗi chu kỳ
# → KHÔNG làm mới mẫu → không có gì để nhân dồn sai số vào → hết trôi. Khi
# video THẬT SỰ zoom (thay đổi rõ rệt, vượt ngưỡng), vẫn làm mới bình thường
# như thiết kế gốc — giữ nguyên khả năng "bắc cầu" qua nhiều bước zoom liên
# tiếp đã ghi nhận trong lịch sử project. `KM_PX` VẪN được tính lại MỖI chu
# kỳ từ `result["k"]` như cũ (không đổi) — chỉ riêng việc "có nhân dồn sai số
# vào mẫu cho lần sau hay không" là bị chặn lại khi không cần thiết.
REF_REFRESH_MIN_SCALE_CHANGE = 0.02   # 2% — dưới mức này coi như "chưa đổi
                                   # tỉ lệ đáng kể", không làm mới mẫu.

# Fix TIẾP (đo được từ log thật user gửi sau khi có fix trên): fix trên chặn
# đúng "nhiều sai số NHỎ dồn dần" nhưng KHÔNG chặn được "1 lần khớp YẾU/NHIỄU
# ĐƠN LẺ nhưng lệch NHIỀU" — log thật cho thấy KM_PX đứng yên tuyệt đối
# 0.6803 suốt ~900 khung hình đầu (xác nhận fix trên hoạt động đúng), rồi
# NGAY SAU 1 dòng `[MOC] OK inlier=7/11 (64%) k=0.81` — 1 khớp YẾU, sát mép
# dưới của CẢ 2 ngưỡng chấp nhận (`REF_MIN_INLIERS=6`, `REF_MIN_INLIER_RATIO
# =0.35`) — hệ thống coi đây là "vừa zoom" (>15%, kích hoạt `[LOC-NEN] Reset`)
# và KM_PX trôi dần không dừng suốt phần còn lại của phiên (tệ hơn cả trước
# khi có fix trên). Vì 1 khớp YẾU vẫn có thể lệch NHIỀU (đủ vượt 2% dù chỉ 1
# lần), ngưỡng biên độ đơn thuần không đủ — cần thêm điều kiện: KHÔNG tin
# ngay 1 lần lệch đáng kể, mà đợi chu kỳ KẾ TIẾP cũng cho thấy lệch đáng kể
# rồi mới làm mới mẫu. Video zoom THẬT luôn kéo dài qua NHIỀU chu kỳ liên
# tiếp (đã ghi nhận nhiều lần trong lịch sử project — "video zoom thật đổi
# dần qua nhiều chu kỳ, không nhảy cóc") nên vẫn được xác nhận & bắc cầu bình
# thường, chỉ trễ thêm ĐÚNG 1 chu kỳ detect (~0.2-0.7s); còn 1 khớp nhiễu đơn
# lẻ (do 1 khung hình xấu/che khuất/mờ thoáng qua) hầu như không lặp lại
# đúng kiểu lệch đó ở chu kỳ NGAY SAU, nên bị bỏ qua — không làm mới mẫu,
# không nhân dồn sai số. Lưu ý: chỉ gác việc LÀM MỚI MẪU — `KM_PX` của CHÍNH
# chu kỳ có khớp yếu đó vẫn được tính/hiển thị bình thường (xem code bên
# dưới), nhưng vì mẫu KHÔNG đổi, chu kỳ kế tiếp (nếu khớp lại yếu bình
# thường như trước) sẽ tự cho ra `scale_rel` gần 1.0 trở lại — sai số chỉ
# ảnh hưởng ĐÚNG 1 khung hình thoáng qua, không để lại dấu vết.
# (Logic nằm trong update_scale_from_reference(), dùng _ref["pending_refresh_k"]
# làm cờ nhớ "chu kỳ trước đã thấy lệch đáng kể chưa".)
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
        "last_score": 0.0, "last_margin": 0.0, "manual": False, "via_known": False,
        "pending_refresh_k": None, "last_revalidate_time": 0.0, "pre_jump_km_px": None}

# BUG đã sửa: log thật (Wyse 5070, phiên ~5.3 phút) cho thấy `km/px` trôi
# LIÊN TỤC 0.6803 -> ~0.94 (~38%) dù KHÔNG có `[LOC-NEN] Reset` nào (đổi
# >15%/1 bước) — tức là trôi DẦN qua rất nhiều bước nhỏ, không phải 1 lần
# zoom thật. Truy ra: bước 1 (dò QUANH ước lượng gần nhất) tự so khớp với
# CHÍNH MẪU đã bị trôi từ chu kỳ trước — nếu nội dung khung hình hiện tại
# vẫn "khớp tốt" với mẫu (dù mẫu đó đã sai lệch dần), `ok=True` ngay ở bước
# 1, KHÔNG BAO GIỜ chạm tới bước 3 (so với `KNOWN_KM_PX` — nguồn SỰ THẬT duy
# nhất KHÔNG tự tham chiếu vào chính nó) vì bước 3 chỉ chạy khi `not ok`.
# Gate "2 chu kỳ liên tiếp" (`REF_REFRESH_MIN_SCALE_CHANGE`, xem trên) chặn
# được 1 lần khớp YẾU/NHIỄU ĐƠN LẺ (đã xác nhận đúng lần trước) nhưng KHÔNG
# chặn được chuỗi ≥2 chu kỳ LIÊN TIẾP cùng lệch nhẹ (do nhiễu/che khuất kéo
# dài vài khung, không phải zoom thật) — mỗi chuỗi như vậy làm mới mẫu 1
# lần, và vì mẫu MỚI lại tiếp tục tự so khớp với CHÍNH NÓ ở chu kỳ sau,
# không có gì ngăn nhiều chuỗi nhỏ như vậy CỘNG DỒN không giới hạn.
# Fix: `REF_REVALIDATE_SEC` — buộc chạy LẠI bước 3 (so `KNOWN_KM_PX`) mỗi
# ĐỊNH KỲ giây thật, BẤT KỂ bước 1 có báo "ok" hay không — 1 lần "chấm điểm
# lại với sự thật" định kỳ, độc lập với chuỗi tự-tham-chiếu của bước 1. Dùng
# LẠI đúng tiêu chí chấp nhận đã có sẵn của bước 3
# (`best_ok and margin >= KNOWN_CANDIDATE_MARGIN`, đã kiểm chứng kỹ trong
# lịch sử project) — nếu 1 known-value thắng rõ ràng, GHI ĐÈ kết quả bước 1
# (kéo `template_k` về đúng); nếu không ứng viên nào đủ tin cậy (vd video
# đang ở 1 mức zoom THẬT khác, chưa từng đo), giữ nguyên kết quả bước 1 —
# AN TOÀN vì bước 3 chỉ override khi CHÍNH NÓ đủ tự tin theo tiêu chí đã có,
# không so sánh/ưu tiên hơn bước 1.
REF_REVALIDATE_SEC = 15.0

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

def _blip_color_mask(frame, precomputed=None):
    """Mặt nạ hợp toàn bộ pixel thuộc màu icon mục tiêu quy định (HSV_RANGES)
    trong khung hình."""
    _hsv, color_masks = precomputed if precomputed is not None else _compute_color_masks(frame)
    m = np.zeros(frame.shape[:2], np.uint8)
    for rm in color_masks.values():
        m = cv2.bitwise_or(m, rm)
    return m

def _non_blip_mask(frame, precomputed=None):
    """Mặt nạ 255 ở MỌI nơi TRỪ pixel màu icon mục tiêu (đảo ngược của
    `_blip_color_mask`) — dùng làm mask cho `_detect_features()` để KHÔNG BAO
    GIỜ đặt 1 keypoint nào lên icon máy bay (vật chuyển động), dù vùng chọn
    (tay hoặc tự động) có vô tình trùm lên 1 phần icon. Tổng quát hơn cách cũ
    (loại cả 1 vùng cửa sổ nếu tỉ lệ pixel màu icon vượt ngưỡng): chỉ loại
    ĐÚNG pixel dính icon, giữ lại toàn bộ chi tiết tĩnh còn lại trong cùng
    cửa sổ."""
    return cv2.bitwise_not(_blip_color_mask(frame, precomputed))

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

def update_scale_from_reference(frame, precomputed=None):
    """Dò lại vùng mốc bằng feature matching (xem khối docstring phía trên):
    ưu tiên tìm quanh ước lượng k gần nhất trước (vùng cắt rộng, không phải
    lưới k như v3), mở rộng dò TOÀN KHUNG HÌNH (masked theo vòng radar) khi
    lân cận thất bại, rồi thử các tỉ lệ "thường gặp" (KNOWN_KM_PX) khi cả 2
    bước trên đều thất bại. Chỉ chấp nhận khi đủ tin cậy (`_ref_evaluate`).
    Cập nhật KM_PX toàn cục, trả về True nếu tỉ lệ vừa đổi ĐÁNG KỂ (video vừa
    zoom) — nơi gọi cần reset StaticNoiseFilter.

    `precomputed`: (hsv, raw_color_masks) đã tính sẵn cho khung hình này
    (xem `_compute_color_masks()`) — tránh tính lại HSV/mặt nạ màu một lần
    nữa chỉ để lấy `_non_blip_mask()`, khi nơi gọi (vòng lặp chính) đã tính
    đúng 1 lần cho cả chu kỳ detect."""
    global KM_PX
    if not _ref["active"] or _ref["manual"]:
        return False
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Loai pixel mau icon muc tieu khoi ca dò lan lam moi mau — 1 may bay dang
    # bay ngang qua vung mốc khong duoc phep gop keypoint gia vao ket qua
    # khop (xem _non_blip_mask).
    non_blip = _non_blip_mask(frame, precomputed)

    # 1) Do QUANH uoc luong k gan nhat truoc (zoom that doi dan qua nhieu chu
    # ky, khong nhay coc) — 1 lan do duy nhat la du, khong can quet nhieu gia
    # thuyet k nhu matchTemplate (xem docstring khoi tren).
    x0, y0, x1, y1 = _crop_bounds_for_k(_ref["k_est"], gray.shape)
    result = _ref_match(gray, x0, y0, x1, y1, mask=non_blip)
    ok, ratio = _ref_evaluate(result)
    via_known = False

    # "Chấm điểm lại với sự thật" định kỳ (xem docstring `REF_REVALIDATE_SEC`
    # cạnh khởi tạo `_ref`) — bước 1 ở trên có thể "ok=True" MÃI MÃI dù đã
    # trôi dần, vì nó tự so khớp với chính mẫu (có thể đã sai) của chu kỳ
    # trước, không phải với sự thật. Chỉ ẢNH HƯỞNG tới việc có ép chạy bước 3
    # (so KNOWN_KM_PX, độc lập với chuỗi tự tham chiếu) hay không — không tự
    # nó thay đổi kết quả nếu không ứng viên nào đủ tin cậy.
    need_revalidate = (time.time() - _ref.get("last_revalidate_time", 0.0)) >= REF_REVALIDATE_SEC

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
    #
    # `or need_revalidate` — chạy ĐỊNH KỲ ngay cả khi `ok=True` (bước 1 tự
    # báo thành công), để đóng lỗ hổng trôi dần đã ghi nhận (xem docstring
    # `REF_REVALIDATE_SEC`). Tiêu chí chấp nhận GIỮ NGUYÊN không đổi
    # (`best_ok and margin >= KNOWN_CANDIDATE_MARGIN`) — nếu không ứng viên
    # nào đủ tin cậy, `result/ok/ratio` giữ nguyên giá trị của bước 1 (không
    # bị đụng tới), an toàn cho trường hợp video đang ở 1 mức zoom thật khác,
    # chưa từng đo.
    # BUG chẩn đoán đã sửa: log thật (build 35, phiên có drift 1 bước >10%
    # thoát khỏi vùng 8% rồi KHÔNG hồi phục suốt ~28s còn lại của phiên) cho
    # thấy: `need_revalidate` CÓ kích hoạt bước 3 (đúng thiết kế), nhưng khi
    # không ứng viên nào đủ tin cậy, hàm ÂM THẦM giữ nguyên kết quả bước 1 —
    # KHÔNG in gì cả (khác 2 nhánh có log sẵn: thành công thì in "Nhan dien
    # ty le thuong gap", mất dấu hoàn toàn thì in "Dang tim lai moc") — nên
    # không thể phân biệt "định kỳ có chạy nhưng thật sự không tìm thấy gì
    # đáng tin ở vị trí mốc" với "có gì đó ngăn nó chạy đúng". Thêm log riêng
    # cho đúng khoảng trống này — chỉ in khi `need_revalidate` (không phải
    # do `not ok`, tránh spam mỗi lần mất dấu thoáng qua bình thường) VÀ
    # không có ứng viên nào thắng — tần suất tối đa ~1 lần/REF_REVALIDATE_SEC.
    was_ok_before_step3 = ok
    if not ok or need_revalidate:
        _ref["last_revalidate_time"] = time.time()
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
        won = False
        if kk:
            best_ratio, best_r, best_kmpx, best_ok = kk[0]
            second_ratio = kk[1][0] if len(kk) >= 2 else -1.0
            if best_ok and (best_ratio - second_ratio) >= KNOWN_CANDIDATE_MARGIN:
                result, ok, ratio, via_known = best_r, True, best_ratio, True
                won = True
                print(f"\r[MOC] Nhan dien ty le thuong gap ({best_kmpx:.4f} km/px, "
                      f"inlier={best_r['inliers']} ty le={best_ratio*100:.0f}% "
                      f"chenh ung vien con lai={best_ratio - second_ratio:.2f})          ",
                      end="", flush=True)
        if not won and was_ok_before_step3 and need_revalidate:
            if kk:
                best_ratio, best_r, best_kmpx, best_ok = kk[0]
                second_ratio = kk[1][0] if len(kk) >= 2 else -1.0
                print(f"\r[MOC-DINH-KY] Kiem tra dinh ky: khong ung vien nao du tin cay "
                      f"(tot nhat {best_kmpx:.4f} km/px inlier={best_r['inliers']} "
                      f"ty le={best_ratio*100:.0f}% chenh={best_ratio - second_ratio:.2f}) "
                      f"— giu nguyen KM_PX={KM_PX:.4f}                    ",
                      end="", flush=True)
            else:
                print(f"\r[MOC-DINH-KY] Kiem tra dinh ky: khong tim thay dac trung nao "
                      f"o ca 3 vi tri da biet — giu nguyen KM_PX={KM_PX:.4f}          ",
                      end="", flush=True)

    _ref["last_score"]  = ratio
    _ref["last_margin"] = float(result["inliers"]) if result else 0.0
    _ref["via_known"]   = via_known

    if not ok or result is None:
        print("\r[MOC] Dang tim lai moc...                                   ", end="", flush=True)
        return False

    _ref["k_est"] = float(result["k"])

    # Làm mới mẫu tham chiếu khi CHẤP NHẬN 1 kết quả — nhưng CHỈ khi tỉ lệ
    # THỰC SỰ vừa đổi đáng kể (xem docstring `REF_REFRESH_MIN_SCALE_CHANGE`
    # phía trên — làm mới vô điều kiện mỗi chu kỳ khiến sai số đo nhỏ NHÂN
    # DỒN qua template_k, gây trôi KM_PX không giới hạn qua 1 phiên dài dù
    # video đứng yên tỉ lệ). Vẫn giữ nguyên khả năng "bắc cầu" qua nhiều bước
    # zoom liên tiếp thật — chỉ chặn refresh THỪA khi không có gì thay đổi.
    #
    # THÊM: đòi hỏi độ lệch đáng kể này lặp lại ở 2 CHU KỲ LIÊN TIẾP mới thực
    # sự làm mới mẫu (xem docstring `REF_REFRESH_MIN_SCALE_CHANGE` — phần "Fix
    # TIẾP") — chặn đúng trường hợp 1 khớp YẾU/NHIỄU đơn lẻ (vd inlier sát mép
    # ngưỡng chấp nhận) gây lệch NHIỀU chỉ trong 1 lần, khiến mẫu bị "đầu độc"
    # ngay bởi 1 kết quả không đáng tin, kéo theo trôi tiếp ở các chu kỳ sau.
    significant = abs(result["scale_rel"] - 1.0) >= REF_REFRESH_MIN_SCALE_CHANGE
    if significant:
        if _ref.get("pending_refresh_k") is not None:
            _ref_refresh_template(gray, result["k"], mask=non_blip)
            _ref["pending_refresh_k"] = None
        else:
            _ref["pending_refresh_k"] = result["k"]
    else:
        _ref["pending_refresh_k"] = None

    dist_px_capture = float(np.hypot(*_ref["offset0"]))
    new_dist_px = dist_px_capture * result["k"]
    if new_dist_px < 5 or KM_PX <= 0:
        return False
    new_km_px = _snap_known_km_px(_ref["real_km"] / new_dist_px)
    ratio_change = new_km_px / KM_PX
    old_km_px = KM_PX
    KM_PX = new_km_px

    # Fix TIẾP 2 (đo được từ log thật: km/px đứng yên TUYỆT ĐỐI ở 0.6803 rất
    # nhiều chu kỳ liên tiếp — snap đang hoạt động đúng — RỒI ĐỘT NGỘT nhảy
    # ra ngoài, trôi tiếp không dừng tới tận 1.09, một mẫu hình lặp lại nhiều
    # lần trong 1 phiên): `_snap_known_km_px()` ở trên CHỈ sửa GIÁ TRỊ HIỂN
    # THỊ (`KM_PX`) — KHÔNG hề đụng tới `_ref["template_k"]` (mẫu tham chiếu
    # dùng để so khớp ORB/AKAZE mỗi chu kỳ). Nghĩa là ngay cả khi màn hình
    # hiện đúng 0.6803 liên tục (nhờ snap "che" đi), bản thân `template_k`
    # bên dưới vẫn có thể tiếp tục trôi ÂM THẦM qua từng lần commit của gate
    # "2 chu kỳ liên tiếp" ở trên — tới khi trôi đủ xa VƯỢT QUA dung sai snap
    # (`KNOWN_KM_PX_TOL=8%`), nó "thoát" khỏi vùng được kéo về và trôi tự do
    # không còn gì giữ lại — đúng khớp mẫu hình quan sát được.
    # Fix: mỗi khi `new_km_px` snap ĐÚNG vào 1 giá trị đã biết (`KNOWN_KM_PX`)
    # — 1 xác nhận ĐỘC LẬP với ground truth vật lý đã đo trước, đáng tin cậy
    # HƠN HẲN so với tự-so-sánh scale_rel với chính mẫu cũ — RE-ANCHOR
    # `template_k` về ĐÚNG giá trị mà known value đó ngụ ý, BỎ QUA gate "2 chu
    # kỳ" ở trên (không cần chờ xác nhận thêm, vì đây là bằng chứng khác hẳn,
    # không tự tham chiếu vào chính nó). Chỉ thực sự làm mới mẫu (tốn 1 lần
    # crop+detect đặc trưng) khi có CHÊNH LỆCH ĐÁNG KỂ (>0.5%) so với
    # template_k hiện tại — tránh làm việc thừa mỗi chu kỳ khi đã đúng sẵn.
    if new_km_px in KNOWN_KM_PX:
        k_corrected = _ref["real_km"] / (dist_px_capture * new_km_px)
        if abs(k_corrected / _ref["template_k"] - 1.0) > 0.005:
            _ref_refresh_template(gray, k_corrected, mask=non_blip)
        _ref["pending_refresh_k"] = None

    if not via_known:
        print(f"\r[MOC] OK  inlier={result['inliers']}/{result['matches']} "
              f"({result['ratio']*100:.0f}%)  k={result['k']:.2f}          ", end="", flush=True)

    # BUG đã sửa: log thật cho thấy "Phát tự động" bỏ lỡ ~50% số vòng khám
    # phá dự kiến (`AUTO-SCAN-TONG-HOP` thưa hơn hẳn `AUTO_DISCOVERY_INTERVAL_SEC
    # =65s` lẽ ra phải cho) — tương quan CHÍNH XÁC với các cụm `[LOC-NEN]
    # Reset` gần nhau: mỗi lần trả `True` ở dòng return CŨ (`not (1/REF_JUMP_RATIO
    # < ratio_change < REF_JUMP_RATIO)`), nơi gọi RESET NGAY
    # `noise_filter`/`static_bg`, khởi động lại `STATIC_BG_WARMUP_SEC=80s` —
    # kể cả khi bước nhảy đó CHỈ LÀ 1 lần trôi thoáng qua rồi TỰ VỀ NGAY chu
    # kỳ sau (đã xác nhận bằng log thật: 0.68->0.75->0.68 chỉ trong 1-2 chu
    # kỳ — chính cơ chế trôi đã sửa 1 phần ở các bản build trước, xem lịch sử
    # `REF_REVALIDATE_SEC`). Nếu các lần trôi thoáng qua này xảy ra dày hơn
    # 80s (thực tế đã đo: có phiên nhiều cụm reset cách nhau ~100-250s, đủ
    # gần để `is_warmed_up()` gần như không bao giờ kịp True) —
    # `auto_confirm_nearby()` bị "đói" (gác cổng bởi `static_bg.is_warmed_up()`)
    # suốt thời gian đó, KHÔNG xác nhận được mục tiêu mới nào — TRỰC TIẾP gây
    # ra "lâu mới nhận diện được mục tiêu" user báo, không chỉ là hiển thị
    # km/px sai thoáng qua.
    # Fix: CHỈ báo hiệu "zoom thật, cần reset" cho nơi gọi khi bước nhảy được
    # XÁC NHẬN Ở CHU KỲ KẾ TIẾP — nếu giá trị MỚI không quay lại gần giá trị
    # CŨ (trước khi nhảy) trong vòng 5%, đó là zoom thật (hoặc ít nhất là 1
    # thay đổi LÂU DÀI, dù không phải zoom); nếu quay lại gần, đó là trôi
    # thoáng qua tự sửa — KHÔNG reset. Không ảnh hưởng gì tới chính giá trị
    # `KM_PX` hiển thị/dùng để tính pixel (vẫn cập nhật MỖI chu kỳ như cũ,
    # xem 2 dòng gán `KM_PX = new_km_px` phía trên) — chỉ QUYẾT ĐỊNH RESET
    # NOISE FILTER bị hoãn đúng 1 chu kỳ (~0.15-0.3s) để xác nhận, cái giá rất
    # nhỏ so với 80s lãng phí mỗi lần reset oan.
    jump_now = not (1 / REF_JUMP_RATIO < ratio_change < REF_JUMP_RATIO)
    pre_jump = _ref.get("pre_jump_km_px")
    if pre_jump is not None:
        _ref["pre_jump_km_px"] = None
        bounced_back = abs(new_km_px / pre_jump - 1.0) < 0.05
        return not bounced_back
    if jump_now:
        _ref["pre_jump_km_px"] = old_km_px
    return False

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
# BUG đã sửa: pad=12 cũ (đo "tốt nhất" từ lần test đầu, chỉ trên vài nhãn cô
# lập) đủ rộng để LẤN sang nội dung liền kề khi nhãn đứng gần hàng chữ/nhãn
# khác — đo thực tế trên phong_to.mp4: 3/6 nhãn ĐƠN DÒNG, đọc đúng lõi số,
# vẫn bị dính thêm 1 chữ số THỪA (vd "016"→"4016", "14126"→"714126") do pad
# đủ lớn để gồm luôn 1 mảnh chữ/lưới ở ngay ngoài rìa bbox thật. Hạ xuống 6
# (đã quét 3-12, xem CLAUDE.md): giảm rủi ro lấn mà không cắt mất chữ số
# ngoài cùng ở các nhãn đã kiểm chứng đọc đúng (612, 883, 015...).
OCR_CROP_PAD         = 6     # px — đệm quanh nhãn trước khi upscale
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

# User yêu cầu: Shift+Click/chuột phải chọn 1 mục tiêu thì OCR cũng "tự động
# nhận diện luôn" — trước đây track vừa chọn thủ công phải CHỜ ĐẾN LƯỢT trong
# vòng round-robin của `_id_ocr_worker()` (có thể xếp sau hàng chục track
# auto-scan khác đang chờ đọc), nên bảng ID thường hiện trống dù bấm ngay lúc
# đó. `_ocr_priority_tids`: tập tid cần đọc TRƯỚC trong lần quét kế tiếp của
# MỖI luồng OCR — `open_id_panel()` (gọi thống nhất từ CẢ Shift+Click LẪN
# chuột phải, xem hàm đó) thêm tid vào đây; `_id_ocr_worker()` sắp `pending`
# ưu tiên các tid có trong tập này lên ĐẦU danh sách quét của chính nó (mỗi
# luồng chỉ phụ trách 1 phần tid cố định qua `hash(tid)%worker_count`, nên
# việc ưu tiên áp dụng đúng NGAY trong lần quét kế tiếp của luồng phụ trách
# tid đó, không cần đợi hết lượt round-robin). Không cần dọn tay — tid tự
# "hết ưu tiên" khi đã có mặt trong `_ocr_confirmed` (không còn nằm trong
# `pending` để mà ưu tiên nữa).
_ocr_priority_tids = set()

# User báo: track "bám" (hiện/lên tiếng) trước, ID OCR chỉ tới "khi nào tới
# lượt" trong round-robin — với 1 luồng OCR duy nhất (Wyse 5070, xem
# OCR_WORKER_COUNT bên dưới) và hàng chục track đang chờ (1 đợt khám phá
# "Phát tự động" có thể xác nhận 20-27 track CÙNG LÚC, xem [AUTO-SCAN-TONG-HOP]
# trong lịch sử), track VỪA khoá phải xếp cuối `pending` (dict giữ nguyên thứ
# tự TẠO — track mới nhất luôn ở cuối) — có thể mất hàng chục giây mới tới
# lượt đọc ĐẦU TIÊN, dù bản thân việc khoá track không hề chậm. Yêu cầu: OCR
# phải bắt đầu dò NGAY khi track khoá (không cần dò xong TRƯỚC khi khoá — sẽ
# chặn vòng lặp chính, không hợp CPU yếu — chỉ cần "vừa dò vừa bám").
#
# KHÔNG dùng chung `_ocr_priority_tids` (ưu tiên VĨNH VIỄN tới khi chốt ID) —
# đã cân nhắc rồi loại: nếu MỌI track auto-scan mới đều được đánh dấu ưu tiên
# và giữ nguyên tới khi chốt, thì sau một thời gian ngắn gần như MỌI track
# đang chờ (kể cả track "ma" không có nhãn, có thể treo rất lâu tới
# OCR_MAX_NOLABEL_ATTEMPTS) đều nằm trong tập ưu tiên — lúc đó sort theo
# "có/không nằm trong tập ưu tiên" không còn phân biệt được gì (mọi phần tử
# cùng khoá sort=0), quay lại ĐÚNG thứ tự FIFO theo thời gian tạo như không hề
# có ưu tiên — track mới nhất vẫn ở cuối. `_ocr_fresh_tids`: ưu tiên CHỈ 1 LẦN
# — `confirm_candidate()` thêm tid vào đây; `_id_ocr_worker()` xoá NGAY sau
# lượt xử lý ĐẦU TIÊN (dù tìm thấy nhãn hay không) — đủ để đảm bảo lượt đọc
# đầu tiên diễn ra ở NGAY VÒNG QUÉT KẾ TIẾP (đầu danh sách) thay vì phải đợi
# hết backlog, mà không làm tập ưu tiên phình to/mất tác dụng theo thời gian.
# Track chọn thủ công (Shift+Click/chuột phải) vẫn dùng `_ocr_priority_tids`
# (ưu tiên LẶP LẠI nhiều lượt cho tới khi chốt đủ phiếu — cố ý, vì operator
# đang chờ xem đúng 1 track cụ thể, khác track auto-scan chỉ cần "bắt đầu
# ngay", không cần vượt mặt mọi track khác ở MỌI vòng quét sau đó).
_ocr_fresh_tids = set()

# CHẨN ĐOÁN TẠM THỜI — user báo "chưa mượt lắm" trên Wyse 5070; benchmark
# draw_frame() trên máy dev (kể cả với lịch sử đuôi vệt bay đầy đủ TAIL_LEN=25
# điểm, không phải mẫu 5 điểm rút gọn của lần đo trước) KHÔNG tái hiện được
# mức tăng chi phí đã đo thật (~6ms→60-65ms khi track tăng 1→16, log thật) —
# độ tăng đo trên dev chỉ ~1.7ms→3.9ms cho 1→23 track, và log thật còn cho
# thấy `ve_canvas` dao động RẤT MẠNH ở CÙNG 1 số lượng track (vd 15 track:
# có lúc 12.8ms, có lúc 60.4ms) — không khớp mô hình "chi phí tỉ lệ thuận số
# track". Nghi vấn: TRANH CHẤP CPU với luồng OCR nền (mỗi lần đọc tự khởi
# `tesseract.exe` — tốn CPU thật, đặc biệt trên máy ít nhân), không phải bản
# thân draw_frame() chậm đi. Đếm số lần luồng OCR THỰC SỰ gọi đọc (bbox tìm
# được, không tính lần "không tìm thấy nhãn" rất rẻ) trong mỗi cửa sổ báo cáo
# `[DO-THOI-GIAN]` để đối chiếu — nếu các khung hình `ve_canvas` cao trùng
# với cửa sổ có nhiều lần đọc OCR, xác nhận đúng giả thuyết tranh chấp CPU.
_ocr_calls_since_report = [0]

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

# BUG/tối ưu đã sửa: `_find_label_near()` gọi `_white_text_mask(frame)` với
# `frame` NGUYÊN VẸN (1920x1080) rồi MỚI cắt vùng cần thiết (~90x90px quanh
# icon, xem `radius`) — nghĩa là `cv2.cvtColor(BGR2HSV)` + `cv2.inRange()`
# chạy trên TOÀN khung hình mỗi lần, dù kết quả CHỈ dùng đúng ~0.35% diện
# tích đó (90x90 / 1920x1080). Đây là phép biến đổi ĐIỂM-ĐỘC-LẬP (mỗi pixel
# tính riêng, không phụ thuộc pixel lân cận) nên cắt TRƯỚC hay cắt SAU cho
# kết quả TOÁN HỌC GIỐNG HỆT — cắt trước chỉ tránh tính thừa phần không dùng.
# Hàm này bị gọi 1 LẦN CHO MỖI TRACK MỖI LẦN THỬ ĐỌC OCR (không phải 1 lần/
# khung hình) — với vài chục track đang chờ đọc, phần thừa này cộng dồn
# thành chi phí đáng kể, đặc biệt trên CPU yếu (Wyse 5070). Đo trên máy dev:
# `_white_text_mask` FULL FRAME ~4.78ms/lần → trên crop nhỏ ~90x90px chỉ
# 0.13ms/lần — nhanh hơn ~35 LẦN. Đã kiểm chứng bbox trả về GIỐNG HỆT trước/
# sau (dilate/connectedComponents vốn đã chạy trên phần ĐÃ CẮT trong cả 2
# bản, không đổi gì ngoài thời điểm cắt).
# BUG đã sửa: user báo ID đọc SAI cho 2 mục tiêu THẬT trong đội hình đông
# (mục tiêu lục "027" đọc ra "034", mục tiêu đỏ "616" đọc ra "611") — không
# phải lỗi ép chữ số đầu theo màu (chữ số đầu ĐÃ ĐÚNG ở cả 2 ca, "0" và "6"),
# tức là `_find_label_near()` khả năng cao đã cắt NHẦM nhãn — 2 mục tiêu cùng
# màu đứng đủ gần nhau (đã đo trước đây: RED có thể cách nhau chỉ ~13-16px)
# có thể có nhãn số của mình rơi vào bán kính tìm kiếm (`OCR_SEARCH_RADIUS
# =45px`) của NHAU, và hàm cũ chỉ chọn cụm chữ GẦN (cx,cy) NHẤT — không biết
# gì về vị trí các track KHÁC cùng màu, nên có thể "cướp" nhầm nhãn của track
# lân cận nếu track đó tình cờ gần cụm chữ đó hơn (do lệch dự đoán/offset
# nhãn không cố định 1 hướng so với icon — xem docstring gốc bên dưới).
# Fix: thêm tham số `other_positions` (vị trí PIXEL hiện tại của các track
# KHÁC, do `_id_ocr_worker()` truyền vào) — áp dụng đúng triết lý "biên độ
# mập mờ" đã dùng cho khớp track (`_filter_ambiguous_pairs`): chỉ chấp nhận
# 1 cụm chữ nếu nó gần (cx,cy) của TRACK NÀY hơn hẳn (ít nhất
# `OCR_LABEL_AMBIG_MARGIN_PX`) so với track khác gần nó nhất — nếu cụm gần
# nhất vẫn mập mờ (gần 1 track khác hơn, hoặc chênh lệch không đủ rõ), THÀ
# không đọc lần này (trả None, thử lại chu kỳ sau) còn hơn đọc nhầm nhãn của
# track khác. Không truyền `other_positions` (gọi rời rạc/test cũ) giữ
# nguyên hành vi gốc — luôn chọn cụm gần nhất, không kiểm tra mập mờ.
#
# BẢN ĐẦU chỉ xét rival CÙNG MÀU (đúng kịch bản gốc: đội hình đông cùng màu).
# User báo lại 1 ca KHÁC: "mục tiêu đỏ nhầm thành lục, 622 đọc thành 624" — 1
# đốm nhiễu bị phân loại KHÁC MÀU (GREEN) đứng sát 1 mục tiêu THẬT (RED) vẫn
# có thể được xác nhận thành track riêng (dedup lúc xác nhận CHỈ so cùng màu,
# cố ý — xem `too_close_to_existing` trong `auto_confirm_nearby()`, không
# chặn 2 mục tiêu thật khác màu đứng gần), rồi track "ma" đó đọc "mượn" đúng
# nhãn của mục tiêu thật vì rival list cũ không hề biết tới track khác màu.
# Fix: `other_positions` giờ gộp MỌI TRACK, không phân biệt màu — ambiguity-
# margin vẫn chỉ từ chối khi THỰC SỰ mập mờ (khoảng cách gần tương đương),
# không ảnh hưởng các ca đã rõ ràng thuộc về đúng track (đã kiểm chứng bằng
# test không hồi quy).
OCR_LABEL_AMBIG_MARGIN_PX = 5

def _find_label_near(frame, cx, cy, radius=OCR_SEARCH_RADIUS, other_positions=None):
    """Tìm cụm chữ trắng (nghi là nhãn số hiệu) gần (cx,cy) nhất trong bán
    kính `radius` quanh vị trí icon — trả về hộp bao (x0,y0,x1,y1) trong toạ
    độ khung hình gốc, hoặc None nếu không thấy cụm nào đủ lớn (>=2 ký tự)
    HOẶC nếu mọi cụm ứng viên đều mập mờ với 1 track khác cùng màu (xem
    `other_positions`, docstring khối trên)."""
    h, w = frame.shape[:2]
    x0s, x1s = max(0, cx - radius), min(w, cx + radius)
    y0s, y1s = max(0, cy - radius), min(h, cy + radius)
    if x1s <= x0s or y1s <= y0s:
        return None
    region = _white_text_mask(frame[y0s:y1s, x0s:x1s])
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
        # BUG đã sửa: dy trước đây so với TỪNG THÀNH VIÊN đang có trong group
        # (`g[5]`) thay vì với hàng gốc (`seed_y`) — cho phép nhóm "trôi" dần
        # qua nhiều hàng chữ xếp chồng (data block ATC hay có 2-3 dòng: ID/độ
        # cao/tốc độ cách nhau ~10-12px, đủ gần để chuỗi bắc cầu từng bước
        # <8px một lần, cộng dồn thành nhóm cao hơn 20px, trộn lẫn nhiều dòng
        # khác nhau vào 1 bbox — đã đo thực tế trên phong_to.mp4: bbox rộng
        # 66x24px cho 1 candidate, đọc ra chuỗi số dài vô nghĩa). Fix: so dy
        # với đúng hàng GỐC (seed_y, cố định khi tạo group) — vẫn cho phép
        # chuỗi ký tự nối ngang tự do trong CÙNG 1 hàng (dx vẫn so với thành
        # viên gần nhất để bắc cầu qua khoảng cách chữ), chỉ chặn trôi dọc.
        seed_y = chars[i][5]
        changed = True
        while changed:
            changed = False
            for j in range(len(chars)):
                if used[j]:
                    continue
                for g in grp:
                    if abs(chars[j][4] - g[4]) < 15 and abs(chars[j][5] - seed_y) < 8:
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
    # (nhóm, khoảng cách tới (cx,cy), tâm nhóm TRONG TOẠ ĐỘ KHUNG HÌNH GỐC) —
    # sắp theo khoảng cách tới (cx,cy) tăng dần để ưu tiên xét nhóm gần nhất
    # trước khi phải cân nhắc "mập mờ" với track khác.
    ginfo = []
    for g in groups:
        lgx, lgy = grp_center(g)
        fgx, fgy = x0s + lgx, y0s + lgy
        ginfo.append((g, math.hypot(fgx - cx, fgy - cy), (fgx, fgy)))
    ginfo.sort(key=lambda t: t[1])
    if other_positions:
        best = None
        for g, d_self, (fgx, fgy) in ginfo:
            d_other = min(math.hypot(fgx - ox, fgy - oy) for ox, oy in other_positions)
            if d_self + OCR_LABEL_AMBIG_MARGIN_PX <= d_other:
                best = g
                break
        if best is None:
            return None
    else:
        best = ginfo[0][0]
    xs = [c[0] for c in best] + [c[0]+c[2] for c in best]
    ys = [c[1] for c in best] + [c[1]+c[3] for c in best]
    return (x0s+min(xs), y0s+min(ys), x0s+max(xs), y0s+max(ys))

# Cấu hình Tesseract — điều chỉnh sau khi benchmark trên 15 nhãn thật đã xác
# nhận bằng mắt (2 khung hình độc lập của phong_to.mp4, xem CLAUDE.md mục
# "Nâng cấp OCR (PSM/OEM/binarize)"):
# - `--oem 1` (chỉ LSTM): `--oem 0`/`2` (cần data engine cổ điển) trả về RỖNG
#   HOÀN TOÀN vì `tessdata/eng.traineddata` đóng gói chỉ hỗ trợ LSTM — ép
#   thẳng oem=1 tránh Tesseract tốn thời gian tự dò/rơi về mặc định.
# - `--psm 6` (coi vùng cắt là 1 KHỐI văn bản, chấp nhận nhiều dòng/khối) —
#   ĐÃ ĐỔI từ `--psm 7` (coi là ĐÚNG 1 dòng): tưởng PSM 7 hợp lý hơn về mặt
#   ngữ nghĩa (nhãn số hiệu luôn 1 dòng), nhưng đo THẬT cho kết quả NGƯỢC:
#   PSM 6 đọc đúng 11/15 nhãn qua 2 khung hình độc lập, PSM 7 chỉ 9/15 — PSM 6
#   khoan dung hơn với nhiễu xung quanh (đường lưới/hàng lang bay cắt ngang
#   nhãn) mà không cần khớp đúng 1 "dòng" duy nhất. Đã thử thêm PSM 8/10/13
#   (khoanh 1 "từ") — chỉ hơn ở 1 ca hiếm ("608", nhãn bị 1 đường nhiễu cắt
#   ngang khiến PSM 6/7 đều bỏ cuộc) nhưng làm HỎNG nhiều ca khác đang đúng —
#   không đáng đánh đổi, giữ PSM 6.
OCR_TESSERACT_CONFIG = "--psm 6 --oem 1 -c tessedit_char_whitelist=0123456789"

def _make_ocr_reader():
    """Tesseract chạy qua `tesseract.exe` như 1 tiến trình HĐH riêng mỗi lần
    gọi (`pytesseract`) — không có state/model cần giữ lại giữa các lần đọc
    như `easyocr.Reader` trước đây, nên không có gì để "tạo" ở đây. Giữ lại
    hàm này (trả về giá trị bất kỳ khác None) chỉ để KHÔNG phải sửa lại chữ
    ký gọi hàm ở `_id_ocr_worker()`/mọi nơi khác đang gọi `_make_ocr_reader()`
    rồi truyền kết quả vào `_ocr_read_bbox(..., reader=...)`."""
    return True

def _ocr_pick_token(raw_text):
    """Tesseract đôi khi trả về NHIỀU "từ" cách nhau khoảng trắng trong 1 lần
    đọc — dù whitelist chỉ cho chữ số, các nét KHÁC chữ số nằm cạnh nhãn thật
    (vd hậu tố "(B)" đánh dấu mục tiêu quân sự thứ cấp) vẫn bị ép đọc thành 1
    "từ" chữ số riêng đứng SAU 1 khoảng trắng (đo thực tế: nhãn "611 (B)" đọc
    ra `"611 8"` — đúng số hiệu "611" cộng thêm "8" giả từ hình dạng "(B)").
    Trước đây cả chuỗi "611 8" (dài 5 ký tự tính cả khoảng trắng) bị coi là 1
    khối, có thể vô tình khớp đúng độ dài hợp lệ (3/5) mà vẫn SAI nội dung,
    lãng phí 1 phiếu bầu (làm chậm hội tụ) mà không tăng được độ chính xác.
    Fix: tách theo khoảng trắng, ưu tiên token ĐẦU TIÊN có độ dài hợp lệ (3
    hoặc 5 — số hiệu luôn đứng TRƯỚC hậu tố, không bao giờ ngược lại), rơi về
    token đầu tiên nếu không token nào khớp độ dài (giữ hành vi cũ)."""
    if not raw_text:
        return raw_text
    parts = raw_text.split()
    if not parts:
        return raw_text
    for p in parts:
        if len(p) in (3, 5):
            return p
    return parts[0]

def _ocr_read_bbox(frame, bbox, reader=None):
    """`reader`: giữ tham số này để tương thích chữ ký gọi hàm cũ (từ thời
    EasyOCR, xem `_make_ocr_reader()`) — Tesseract không dùng tới, mỗi lần
    gọi tự khởi chạy `tesseract.exe` độc lập nên an toàn gọi đồng thời từ
    nhiều luồng mà không cần Reader riêng như EasyOCR."""
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
    # Nhị phân hoá bằng ngưỡng Otsu TRƯỚC khi đưa vào Tesseract — KHÁC hẳn
    # bài học cũ với EasyOCR (nhị phân hoá làm GIẢM độ chính xác EasyOCR, xem
    # CLAUDE.md mục "3. EasyOCR" — model neural đó tận dụng chi tiết
    # anti-alias). Tesseract là engine cổ điển hơn, TỰ nhị phân hoá nội bộ dù
    # ta đưa ảnh màu vào — cho nó 1 ảnh nhị phân SẠCH (ngưỡng Otsu thích ứng,
    # không phụ thuộc màu icon/nền phía sau chữ, vốn đổi theo từng track) làm
    # bước đó ổn định hơn thay vì để Tesseract tự đoán ngưỡng mỗi lần. Đã đo
    # trên 7 nhãn thật: cùng độ chính xác (5/7) nhưng nhanh hơn nhẹ so với ảnh
    # màu gốc (~146ms vs ~154ms), không có ca nào bị tệ đi.
    gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    _, big_bin = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    try:
        text = pytesseract.image_to_string(big_bin, config=OCR_TESSERACT_CONFIG).strip()
    except Exception:
        return None
    if not text:
        return None
    return _ocr_pick_token(text)

OCR_MAX_ATTEMPTS = 20   # số lần đọc tối đa trước khi CHỐT TẠM theo đa số
                        # phiếu hiện có (dù chưa đạt OCR_VOTE_CONFIRM) — nếu
                        # không, 1 track có phiếu rải rác đều (không lần nào
                        # trùng đủ OCR_VOTE_CONFIRM) sẽ bị đọc MÃI MÃI không
                        # bao giờ chốt, tốn tài nguyên vô ích và không bao
                        # giờ hiển thị ID dù đã đọc rất nhiều lần.
# Nâng 8->20 (chỉ radar_live_6.py): log thật (track GREEN/MAGENTA mới bắt
# được nhờ fix "hạn sử dụng lọc nền tĩnh") cho thấy chốt "tạm" với 1/8 hoặc
# 2/8 phiếu — nghĩa là qua ĐỦ 8 lần đọc, GẦN NHƯ MỌI kết quả đều KHÁC NHAU
# (không phải 2-3 ứng viên cạnh tranh sát sao) — dấu hiệu của NHIỄU NGẪU
# NHIÊN mức cao (crop/khung hình thay đổi frame-to-frame), không phải lỗi
# đọc CÓ HỆ THỐNG (vốn sẽ cho VÀI kết quả LẶP LẠI giống hệt nhau nhiều lần —
# xem lịch sử OCR "sai giống hệt nhau mỗi lần" trong CLAUDE.md, kiểu lỗi đó
# KHÔNG hưởng lợi từ việc đọc thêm). `OCR_MAX_ATTEMPTS=8` được hiệu chỉnh khi
# còn dùng EasyOCR (~300-700ms/lần, giới hạn 8 lần để tránh treo quá lâu) —
# từ khi đổi sang Tesseract (~130-350ms/lần, tiến trình HĐH riêng, ưu tiên
# THẤP hơn luồng chính — xem lịch sử "hạ ưu tiên tiến trình Tesseract") chi
# phí mỗi lần đọc đã giảm hẳn, dư địa để tăng số lần thử mà tổng thời gian
# chờ vẫn ở mức chấp nhận được như cũ (~2.5x thời gian, tương đương mức đã
# chấp nhận trước đây khi còn dùng EasyOCR chậm hơn).
# RỦI RO ĐÃ CÂN NHẮC (chưa loại trừ hoàn toàn — cần đối chiếu log mới): nếu
# nguyên nhân THỰC SỰ là "khớp nhầm nhãn hàng xóm trong đội hình dày đặc"
# (không phải nhiễu ngẫu nhiên) thay vì nhiễu ngẫu nhiên, đọc thêm có thể
# khiến 1 kết quả SAI hội tụ đủ OCR_VOTE_CONFIRM=3 phiếu nhanh hơn (chuyển từ
# "tạm, độ tin cậy thấp" sang "chắc chắn" NHƯNG SAI) — đã thêm chẩn đoán
# `toan_bo_phieu=...` (in kèm mỗi lần chốt "tạm") để phân biệt 2 khả năng
# này ở lần đối chiếu log tiếp theo, thay vì chỉ đoán 1 hướng duy nhất.
_ocr_attempts = {}     # tid -> tổng số lần đã thử đọc (kể cả không ra chữ)

# Trước đây chỉ 1 luồng đọc TUẦN TỰ hết track này tới track khác (~350ms/lần
# EasyOCR trên CPU) — với ~26-50 track (thực tế đo được, xem lịch sử OCR ở
# trên), 1 vòng quét hết mất 10-40s, làm chậm tốc độ tích luỹ phiếu bầu
# (`OCR_VOTE_CONFIRM`) một cách không cần thiết. Chạy nhiều luồng đọc SONG
# SONG — mỗi luồng xử lý 1 PHẦN RIÊNG BIỆT (không chồng lấn) của danh sách
# track theo `hash(tid) % OCR_WORKER_COUNT`, nên không cần khoá (lock) khi
# ghi `_ocr_votes`/`_ocr_confirmed`/`_ocr_attempts` — mỗi tid chỉ do ĐÚNG 1
# luồng ghi. Mỗi luồng giữ 1 `easyocr.Reader` RIÊNG (không dùng chung Reader
# toàn cục) vì Reader không đảm bảo an toàn khi gọi `readtext()` đồng thời từ
# nhiều luồng.
#
# BUG đã tránh khi đo: lần đo ĐẦU TIÊN (chưa "làm nóng" Reader trước khi bấm
# giờ) cho kết quả NGƯỢC ĐỜI — nhiều luồng hơn lại CHẬM hơn (3 luồng: 0.85x,
# tức chậm hơn 1 luồng). Nguyên nhân: mỗi `easyocr.Reader()` mất ~3.4s để
# nạp model từ đĩa — dựng nhiều Reader CÙNG LÚC (1 Reader/luồng lúc luồng mới
# khởi động) khiến phép đo bị nhiễu nặng bởi chi phí nạp model 1 LẦN đó,
# không phản ánh đúng tốc độ đọc ổn định lâu dài (trong app thật, Reader chỉ
# dựng 1 lần lúc khởi động, không lặp lại). Đo LẠI đúng cách (dựng sẵn/"làm
# nóng" Reader cho từng luồng TRƯỚC khi bấm giờ, chỉ đo tốc độ đọc ổn định)
# trên máy 8 core: 1 luồng ~275-330ms/lần đọc; 2 luồng ~137-224ms/lần đọc
# (~1.5-2x nhanh hơn); 3 luồng ~140-163ms/lần đọc — GẦN NHƯ KHÔNG nhanh hơn 2
# luồng (máy này torch mặc định dùng 4 luồng nội bộ/lần suy luận, 2 luồng x 4
# = 8 luồng tính toán vừa khít 8 core; luồng thứ 3 chỉ gây tranh chấp CPU
# thêm mà không tăng thông lượng). Chọn **2** (không phải 3) để vẫn còn dư
# CPU cho vòng lặp chính (capture/detect/vẽ) + các luồng nền khác (audio,
# auto-scan) chạy song song trong app thật — không đẩy hết 8 core vào riêng
# OCR. Không cần chỉnh `torch.set_num_threads` — giữ mặc định vẫn cho kết
# quả tốt nhất trong phép đo TRÊN MÁY 8 CORE ĐÓ.
# CẬP NHẬT sau khi đổi EasyOCR→Tesseract: heuristic "2 nếu >=6 core, 1 nếu
# ít hơn" ở trên được đo/tối ưu RIÊNG cho EasyOCR (mỗi luồng tự chiếm 1
# `torch` model với NHIỀU luồng tính toán NỘI BỘ trong CÙNG tiến trình Python
# — dễ tranh chấp CPU/GIL). Tesseract hoàn toàn KHÁC: mỗi lần đọc là 1 TIẾN
# TRÌNH HĐH RIÊNG (`tesseract.exe`, không chia sẻ GIL/bộ nhớ với luồng gọi
# nó) — về lý thuyết chịu được nhiều luồng song song hơn hẳn. Đã đo lại THẬT
# trên máy dev 8 core (tạo N luồng, mỗi luồng tự gọi `pytesseract.image_to_string`
# lặp lại, đo thông lượng tổng — không phải suy luận): thông lượng tăng gần
# tuyến tính 1→6 luồng (6.98 → 20.92 lần đọc/giây, ~3 lần), rồi GIẢM ở 8 luồng
# (17.95 lần đọc/giây, tệ hơn cả 6) — đúng dấu hiệu bắt đầu tranh chấp CPU khi
# số luồng OCR áp sát tổng số core của máy, không còn "room" cho vòng lặp
# chính.
#
# BUG suýt phạm PHẢI: bản đầu tiên đổi thẳng sang công thức scale liên tục
# `max(1, min(_CPU_COUNT-2, 6))` — TRÊN GIẤY nghe hợp lý (chừa 2 core cho
# vòng lặp chính), nhưng với máy ÍT CORE như Wyse 5070 (~4 core, mục tiêu
# THỰC SỰ quan tâm xuyên suốt CLAUDE.md), công thức đó cho ra 2 — TĂNG GẤP
# ĐÔI so với giá trị cũ (1) — dựa HOÀN TOÀN trên số liệu đo được CHỈ TRÊN MÁY
# DEV 8 CORE (không có Wyse 5070 ở đây để đo trực tiếp). User nhắc lại đúng
# lúc: "nhớ về độ CPU của Wyse 5070" — 2 luồng Tesseract song song trên CPU
# 4 nhân đã biết trước là yếu/hay nghẽn (toàn bộ lịch sử đo đạc "Wyse 5070"
# phía trên) có thể cướp mất 50% số core đáng lẽ dành cho vòng lặp chính
# (detect/vẽ/tracking — vốn ĐÃ là điểm nghẽn chính đo được, không phải OCR:
# "Kết quả đo đầu tiên từ Wyse 5070" ghi rõ "OCR ảnh hưởng không nhiều lắm").
# Fix: KHÔNG suy diễn/ngoại suy công thức liên tục sang lớp phần cứng chưa
# đo — chỉ áp dụng số liệu MỚI (6 luồng) cho ĐÚNG lớp máy đã đo (>=8 core),
# GIỮ NGUYÊN 100% hành vi CŨ (đã qua kiểm chứng an toàn từ trước, kể cả trên
# Wyse 5070) cho máy <6 core — không tăng may rủi trên đúng phần cứng đang lo
# ngại chỉ vì "có vẻ hợp lý" mà chưa có số đo thật.
_CPU_COUNT = os.cpu_count() or 4
if _CPU_COUNT >= 8:
    OCR_WORKER_COUNT = 6   # đo thật trên máy dev 8 core (xem ngay trên)
elif _CPU_COUNT >= 6:
    OCR_WORKER_COUNT = 2   # giữ nguyên giá trị CŨ (heuristic gốc thời EasyOCR)
else:
    OCR_WORKER_COUNT = 1   # giữ nguyên giá trị CŨ — KHÔNG đổi cho máy yếu
                            # (Wyse 5070) khi chưa có số đo thật trên đúng
                            # lớp phần cứng đó

# User cung cấp quy tắc nghiệp vụ: chữ số ĐẦU của số hiệu quy định theo MÀU
# — RED (quân sự) luôn bắt đầu bằng 6, GREEN (quá cảnh) bằng 0, MAGENTA
# (quốc tế) bằng 8. Khớp ĐÚNG 100% mọi số hiệu thật đã quan sát được xuyên
# suốt phiên làm việc này (RED: 611-623, GREEN: 025-029, MAGENTA: 881-885).
# Không có quy tắc cho YELLOW/CYAN (user không đề cập) nên bỏ qua 2 màu đó.
# Dùng để SỬA chữ số đầu bị đọc sai (lỗi phổ biến ở OCR độ phân giải thấp,
# dễ nhầm 6/0/8 do hình dạng gần giống nhau khi nhãn chỉ ~5-8px/ký tự) thay
# vì loại bỏ cả kết quả — biết trước chữ số đầu, chỉ cần tin OCR cho các chữ
# số CÒN LẠI (đa dạng hình dạng hơn, đáng tin hơn theo từng ký tự đơn lẻ).
COLOR_ID_PREFIX = {"RED": "6", "GREEN": "0", "MAGENTA": "8"}

OCR_MAX_NOLABEL_ATTEMPTS = 300   # xem docstring _ocr_nolabel_streak bên dưới
_ocr_nolabel_streak = {}   # tid -> so lan LIEN TIEP khong tim thay bbox nhan

def _id_ocr_worker(stop_evt, tm_ref, worker_id=0, worker_count=1):
    """Luồng nền: lần lượt thử đọc nhãn số hiệu của các track CHƯA chốt ID mà
    `hash(tid) % worker_count == worker_id` (phần việc riêng của luồng này).
    Không chạy trong vòng lặp chính vì EasyOCR quá chậm (~350ms/lần trên CPU)."""
    reader = _make_ocr_reader()
    while not stop_evt.is_set():
        frame = _latest_frame_for_ocr[0]
        if frame is None:
            stop_evt.wait(1.0)
            continue
        # Dọn `_ocr_priority_tids` — track đã chốt ID hoặc đã bị xoá không
        # còn gì để "ưu tiên" nữa (tránh tập này phình to qua 1 phiên dài).
        # An toàn khi làm ở NHIỀU luồng cùng lúc: `set.discard()` không lỗi
        # nếu phần tử đã bị luồng khác dọn trước.
        for _tid in list(_ocr_priority_tids):
            if _tid in _ocr_confirmed or _tid not in tm_ref.tracks:
                _ocr_priority_tids.discard(_tid)
        # Dọn `_ocr_fresh_tids` cùng lúc — track có thể bị xoá/dedup NGAY sau
        # khi tạo (vd Shift+Delete, hoặc bị TrackManager dọn do MAX_LOST) TRƯỚC
        # khi kịp có lượt xử lý đầu tiên nào (xem docstring `_ocr_fresh_tids`).
        for _tid in list(_ocr_fresh_tids):
            if _tid in _ocr_confirmed or _tid not in tm_ref.tracks:
                _ocr_fresh_tids.discard(_tid)
        pending = [(tid, info) for tid, info in list(tm_ref.tracks.items())
                   if tid not in _ocr_confirmed and abs(hash(tid)) % worker_count == worker_id]
        if not pending:
            stop_evt.wait(1.0)
            continue
        # Ưu tiên đọc TRƯỚC: (a) track vừa được chọn thủ công (Shift+Click/
        # chuột phải, `_ocr_priority_tids`/`open_id_panel()` — ưu tiên LẶP LẠI
        # tới khi chốt ID); (b) track VỪA khoá (auto-scan lẫn thủ công,
        # `_ocr_fresh_tids` — ưu tiên ĐÚNG 1 LẦN, xem docstring hằng số đó) —
        # đẩy lên ĐẦU danh sách quét của CHÍNH LUỒNG NÀY (sort ổn định, giữ
        # nguyên thứ tự tương đối giữa các track không ưu tiên với nhau).
        if _ocr_priority_tids or _ocr_fresh_tids:
            pending.sort(key=lambda item: 0 if (item[0] in _ocr_priority_tids
                                                 or item[0] in _ocr_fresh_tids) else 1)
        # User yêu cầu: "tăng tốc nhận diện ID khi chọn mục tiêu bằng tay" —
        # trước đây track trong `_ocr_priority_tids` (Shift+Click/chuột phải)
        # tuy được xếp ĐẦU mỗi sweep (sort ngay trên), nhưng vẫn phải đợi HẾT
        # cả sweep (mọi track THƯỜNG khác của cùng luồng — có thể 20-30 track
        # lúc "Phát tự động" vừa xác nhận hàng loạt, mỗi track ~150-400ms/lần
        # đọc) mới quay lại đầu `while` để đọc thêm 1 phiếu cho track ưu
        # tiên — với `OCR_VOTE_CONFIRM=3`, có thể mất hàng chục giây mới chốt
        # xong 1 track đang được operator theo dõi trực tiếp, dù nó luôn
        # "đứng đầu hàng". Fix: khi CÓ track ưu tiên thủ công CHƯA CHỐT thuộc
        # luồng này, thu hẹp sweep NÀY lại CHỈ còn đúng các track đó (tạm bỏ
        # qua track thường) — 1 sweep ngắn (thường 1-3 track) hoàn thành
        # trong ~0.2-0.5s thay vì hàng chục giây, nên track ưu tiên được đọc
        # LẠI (dùng frame MỚI — `_latest_frame_for_ocr` cập nhật mỗi khung
        # hình capture đọc được, không phải mỗi chu kỳ detect, nên luôn có
        # frame mới để đọc chứ không lặp lại y hệt 1 khung cũ) gần như mỗi
        # vòng `while`, hội tụ đủ 3 phiếu nhanh hơn hẳn. Track thường tự động
        # resume ngay khi track ưu tiên chốt xong (dù đúng hay "" — mục
        # `_ocr_priority_tids` được dọn ở đầu vòng lặp kế tiếp) — không
        # "đói" vĩnh viễn, chỉ tạm nhường vài giây cho track đang được chờ.
        # KHÔNG áp dụng thu hẹp này cho `_ocr_fresh_tids` MỘT MÌNH (không có
        # `_ocr_priority_tids`) — fresh chỉ cần ĐÚNG 1 lần đọc (không lặp lại
        # qua nhiều sweep như priority), thu hẹp sweep không giúp gì thêm cho
        # nó, chỉ trì hoãn track thường một cách vô ích.
        if _ocr_priority_tids:
            _priority_only = [item for item in pending if item[0] in _ocr_priority_tids]
            if _priority_only and len(_priority_only) < len(pending):
                pending = _priority_only
        # Vị trí PIXEL HIỆN TẠI của MỌI track — dùng để phát hiện "mập mờ" khi
        # 2 track đứng đủ gần nhau có thể tranh nhau 1 nhãn (xem docstring
        # `OCR_LABEL_AMBIG_MARGIN_PX`/`_find_label_near()`). BAN ĐẦU chỉ gộp
        # theo CÙNG MÀU (đúng kịch bản gốc: đội hình đông CÙNG MÀU, vd 2 RED
        # 616/611) — user báo lại 1 ca KHÁC hẳn: 1 đốm nhiễu bị phân loại
        # KHÁC MÀU (vd GREEN) đứng sát 1 mục tiêu thật (RED) đọc "mượn" đúng
        # nhãn của mục tiêu thật đó (622->624, hiển thị nhầm màu) — dedup lúc
        # xác nhận track CHỈ so cùng màu (cố ý, không chặn 2 mục tiêu thật
        # khác màu đứng gần — xem `too_close_to_existing` trong
        # `auto_confirm_nearby()`), nên 1 track "ma" khác màu vẫn có thể được
        # tạo cạnh mục tiêu thật, rồi không có gì cản nó đọc nhầm nhãn của
        # hàng xóm khác màu như trước (rival list cũ chỉ xét cùng màu). Fix:
        # GỘP MỌI TRACK, không phân biệt màu — ambiguity-margin vẫn chỉ từ
        # chối khi THỰC SỰ mập mờ (gần tương đương), không ảnh hưởng các ca
        # đã rõ ràng thuộc về đúng track (xem test). Dựng lại mỗi VÒNG QUÉT
        # (không phải mỗi track) — đủ rẻ so với chi phí OCR sắp tới.
        all_positions = []
        for tid2, info2 in tm_ref.tracks.items():
            hist2 = info2.get("history")
            if not hist2:
                continue
            _, xkm2, ykm2, _, _ = hist2[-1]
            all_positions.append((tid2, to_px(xkm2, ykm2)))
        for tid, info in pending:
            if stop_evt.is_set():
                break
            hist = info.get("history")
            if not hist:
                continue
            _, xkm, ykm, _, _ = hist[-1]
            cx, cy = to_px(xkm, ykm)
            other_positions = [pos for tid2, pos in all_positions if tid2 != tid]
            bbox = _find_label_near(frame, cx, cy, other_positions=other_positions)
            # Tiêu thụ "ưu tiên 1 lần" NGAY khi track được xử lý lượt đầu tiên
            # (dù tìm thấy nhãn hay không) — xem docstring `_ocr_fresh_tids`.
            # Đủ để đảm bảo lượt đọc đầu tiên diễn ra sớm, không giữ ưu tiên
            # mãi (tránh tập này phình to bằng cả `pending` và mất tác dụng
            # phân biệt theo thời gian).
            _ocr_fresh_tids.discard(tid)
            votes = _ocr_votes.setdefault(tid, {})
            # BUG đã sửa: TRƯỚC ĐÂY `_ocr_attempts[tid]` (ngân sách "bỏ cuộc
            # sau OCR_MAX_ATTEMPTS lần") tăng MỖI VÒNG LẶP, kể cả khi
            # `bbox is None` (không tìm thấy nhãn — vd icon vừa xuất hiện
            # trong cụm đông, nhãn tạm bị che khuất bởi icon/nhãn khác đứng
            # gần) — 8 lần "không tìm thấy" LIÊN TIẾP (hoàn toàn có thể xảy
            # ra trong vài giây nếu track đứng giữa đội hình đông) đủ để
            # track CHỐT VĨNH VIỄN "không có ID" (`_ocr_confirmed[tid]=""`),
            # dù sau đó nhãn có thể lộ ra rõ ràng khi đội hình giãn ra — mất
            # cơ hội đọc ID mãi mãi dù dữ liệu sau này hoàn toàn tốt. Fix:
            # tách riêng ngân sách "không tìm thấy nhãn" (`_ocr_nolabel_streak`,
            # KHÔNG tính vào `_ocr_attempts`) — chỉ bỏ cuộc sau
            # `OCR_MAX_NOLABEL_ATTEMPTS` (300, rộng rãi hơn hẳn 8, vì mỗi lần
            # "không tìm thấy" giờ RẤT RẺ — xem tối ưu `_find_label_near()`
            # cắt vùng nhỏ TRƯỚC khi tính HSV, ~0.13ms thay vì ~4.78ms/lần
            # trên toàn khung hình — không còn lý do phải bỏ cuộc sớm chỉ để
            # tiết kiệm CPU). `_ocr_attempts` (ngân sách chính, vẫn 8) CHỈ
            # tăng khi THỰC SỰ đọc thử được (có bbox, dù kết quả đúng/sai) —
            # đúng ý nghĩa gốc "đã thử đọc nhưng không hội tụ", không lẫn với
            # "chưa có cơ hội thử".
            if bbox is not None:
                _ocr_nolabel_streak[tid] = 0
                text = _ocr_read_bbox(frame, bbox, reader=reader)
                _ocr_calls_since_report[0] += 1
                # Lọc "hợp lý": mọi số hiệu thật quan sát được trên phần
                # mềm này đều dài 3 hoặc 5 ký tự (025-029/611-623/881-885 và
                # mã 14xxx) — loại ngay các chuỗi quá dài/quá ngắn (vd
                # "1445088", "88", "61") thay vì cho vào vòng bầu chọn, vì
                # đó gần như chắc chắn là đọc dính sang nhãn/hoạ tiết khác
                # bên cạnh chứ không phải 1 số hiệu thật bị đọc lệch vài ký
                # tự — tránh "chốt chắc chắn" 1 kết quả rõ ràng vô lý.
                if text and len(text) in (3, 5):
                    # Ép chữ số ĐẦU theo màu (xem COLOR_ID_PREFIX) — sửa lỗi
                    # đọc nhầm phổ biến ở đúng vị trí này thay vì loại bỏ cả
                    # kết quả.
                    #
                    # LỊCH SỬ 2 lần chỉnh trước (xem CLAUDE.md) đều dùng LUẬT
                    # CỨNG để quyết định có tin "màu hiện tại" hay không (bản
                    # 1: không bao giờ sửa nếu chữ số đầu trùng prefix màu
                    # khác; bản 2: chỉ trừ hao cho đúng cặp RED/MAGENTA, coi
                    # là "hue kề nhau nên có thể nhầm màu thật"). User gửi lại
                    # log THẬT cho đúng cặp RED/MAGENTA — hoá ra bản 2 VẪN sai
                    # theo hướng khác: 3/4 mẫu log gửi về có HSV đo được KHỚP
                    # ĐÚNG với màu đã gán (`?24` RED hue=1; `?16` MAGENTA
                    # hue=147-148, V=255 tin cậy) — tức là màu ĐÚNG, chỉ chữ
                    # số bị đọc nhầm (Tesseract lẫn 6↔8/6↔0 ở độ phân giải
                    # thấp) — nhưng luật cứng "RED/MAGENTA luôn nghi ngờ" vẫn
                    # từ chối sửa OAN cả 3 ca này. Chỉ đúng 1/4 mẫu (`?17` RED
                    # nhưng hue=150, V=255 — rõ ràng là màu tím thật) mới thực
                    # sự đáng ngờ.
                    # Fix: BỎ HẲN luật cứng theo cặp màu — dùng CHÍNH giá trị
                    # màu đo được TẠI THỜI ĐIỂM ĐỌC (`classify_color_at()`,
                    # đã có sẵn cho Shift+Click, đếm số pixel khớp từng dải
                    # màu trong 1 vùng nhỏ quanh icon — đáng tin hơn hẳn 1 mẫu
                    # HSV đơn lẻ vì gộp nhiều pixel, tự nhiên bỏ qua các pixel
                    # rìa/nhiễu lẻ loi) để QUYẾT ĐỊNH THEO TỪNG LẦN ĐỌC, không
                    # theo luật chung cứng nhắc cho cả 1 cặp màu:
                    #   - Màu đo lại KHỚP màu đã gán cho track → tin tưởng,
                    #     sửa chữ số đầu bình thường (đây mới là đa số ca thật
                    #     theo log vừa nhận).
                    #   - Màu đo lại KHÁC (hoặc không xác định được) → giữ
                    #     nguyên + log, đúng như thiết kế thận trọng gốc,
                    #     nhưng giờ áp dụng CHÍNH XÁC vào ĐÚNG ca nghi ngờ
                    #     thay vì áp đặt cho cả 1 cặp màu.
                    expected0 = COLOR_ID_PREFIX.get(info["color"])
                    if expected0 is not None and text[0] not in COLOR_ID_PREFIX.values():
                        text = expected0 + text[1:]
                    elif expected0 is not None and text[0] != expected0:
                        # Bọc try/except — nhánh này gọi thêm 1 lần
                        # cv2.cvtColor/inRange, KHÔNG được phép làm crash
                        # luồng nền OCR nếu có gì bất thường (đã tự bắt được
                        # 1 crash thật ở bản trước khi test: frame nhỏ hơn
                        # vùng cắt).
                        try:
                            # radius=5 (rộng hơn mặc định 3 của
                            # classify_color_at, vốn tuning cho click tay
                            # CHÍNH XÁC 1 điểm) — vị trí (cx,cy) ở đây là VỊ
                            # TRÍ DỰ ĐOÁN của track, không chắc trúng đúng
                            # điểm sáng nhất icon, nên lấy mẫu rộng hơn 1 chút
                            # để đỡ phụ thuộc may rủi 1 pixel rìa tối/nhiễu.
                            _resampled = classify_color_at(frame, cx, cy, radius=5)
                        except Exception:
                            _resampled = None
                        if _resampled == info["color"]:
                            # Màu đo lại NGAY LÚC NÀY khớp đúng màu đã gán —
                            # tin tưởng, chữ số đầu sai là do OCR, sửa bình
                            # thường.
                            text = expected0 + text[1:]
                        else:
                            # Màu đo lại KHÔNG khớp (khác màu, hoặc None) —
                            # thực sự đáng ngờ, giữ nguyên + log kèm HSV đo
                            # trực tiếp để có số liệu THẬT cho lần tinh chỉnh
                            # sau (không đoán mù).
                            try:
                                _fh, _fw = frame.shape[:2]
                                _px0, _px1 = max(0, cx-2), min(_fw, cx+3)
                                _py0, _py1 = max(0, cy-2), min(_fh, cy+3)
                                if _px1 > _px0 and _py1 > _py0:
                                    _hsv_px = cv2.cvtColor(frame[_py0:_py1, _px0:_px1], cv2.COLOR_BGR2HSV)
                                    _h, _s, _v = [int(round(float(np.median(_hsv_px[:,:,k])))) for k in range(3)]
                                    print(f"\n[MAU-CHAN-DOAN] {tid} mau_gan={info['color']} "
                                          f"doc_duoc={text!r} (prefix~{text[0]}) mau_do_lai={_resampled} "
                                          f"-> nghi PHAN LOAI MAU/TRACKING SAI  hsv_tai_icon=({_h},{_s},{_v})",
                                          flush=True)
                            except Exception:
                                pass
                    votes[text] = votes.get(text, 0) + 1
                _ocr_attempts[tid] = _ocr_attempts.get(tid, 0) + 1
            else:
                # Không tìm thấy bbox nhãn lần này — KHÔNG tính vào
                # `_ocr_attempts` (xem docstring ở nhánh `if bbox is not None`
                # phía trên), chỉ đếm streak riêng để cuối cùng vẫn bỏ cuộc
                # được nếu track này VĨNH VIỄN không có nhãn lộ ra (vd nhiễu
                # tĩnh bị xác nhận nhầm thành track) — 300 lần rộng rãi vì mỗi
                # lần giờ rất rẻ (~0.13ms, xem tối ưu `_find_label_near`).
                _ocr_nolabel_streak[tid] = _ocr_nolabel_streak.get(tid, 0) + 1
                if _ocr_nolabel_streak[tid] >= OCR_MAX_NOLABEL_ATTEMPTS:
                    _ocr_confirmed[tid] = ""
                stop_evt.wait(OCR_ATTEMPT_INTERVAL)
                continue
            best_text, best_n = (None, 0)
            for t, n in votes.items():
                if n > best_n:
                    best_text, best_n = t, n
            if best_n >= OCR_VOTE_CONFIRM or _ocr_attempts[tid] >= OCR_MAX_ATTEMPTS:
                if best_text:
                    _ocr_confirmed[tid] = best_text
                    tag = "chac chan" if best_n >= OCR_VOTE_CONFIRM else "tam (het luot doc)"
                    # CHẨN ĐOÁN: khi chốt "tạm" (hết lượt, KHÔNG có 1 kết quả
                    # nào đạt đa số rõ ràng) — in thêm TOÀN BỘ phân bố phiếu
                    # (không chỉ số phiếu của kết quả thắng) để biết các lần
                    # đọc có PHÂN TÁN NGẪU NHIÊN (nhiều kết quả khác nhau, mỗi
                    # cái 1 phiếu — nghi crop/nhãn không ổn định) hay TẬP
                    # TRUNG vào 2-3 ứng viên gần giống nhau (nghi lỗi đọc CÓ
                    # HỆ THỐNG ở 1-2 ký tự cụ thể, vd 6↔0/6↔8 đã ghi nhận
                    # trước đây) — 2 nguyên nhân cần hướng sửa khác hẳn nhau.
                    extra = f"  toan_bo_phieu={dict(votes)}" if tag != "chac chan" else ""
                    print(f"\n[OCR] {tid}: so hieu = {best_text} ({tag}, {best_n}/{_ocr_attempts[tid]} phieu){extra}",
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
        # tid -> ((len(history), t_cuoi), vx, vy) — xem get_velocity()
        self._vel_cache = {}

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

        BUG đã sửa: user báo "báo ID 616 nhưng điểm bám lạc chỗ khác... có
        thể máy quá chậm" — ĐÚNG, và là NGUYÊN NHÂN GỐC quan trọng hơn cả lớp
        phòng vệ mập mờ thêm ở dưới. `t_sec` TRƯỚC ĐÂY tính bằng
        `frame_idx / self.fps` — `fps` là giá trị THIẾT BỊ TỰ BÁO (`cap.get
        (CAP_PROP_FPS)`, vd 30), KHÔNG PHẢI tốc độ xử lý THẬT của vòng lặp.
        Trên máy yếu (Wyse 5070, đã đo: ~0.7s thời gian THẬT cho 5 khung hình
        — tức ~7fps thật, chậm hơn ~4 lần so với 30fps thiết bị báo), đồng hồ
        nội bộ `t_sec` chạy NHANH HƠN thời gian thật ~4 lần — vận tốc fit qua
        `get_velocity()` (km / Δt_sec_danh_nghĩa) vì vậy bị THỔI PHỒNG đúng
        theo tỉ lệ đó. Nếu tốc độ xử lý mỗi chu kỳ ỔN ĐỊNH, sai số này tự
        triệt tiêu (dự đoán chu kỳ sau cũng dùng cùng tỉ lệ nén thời gian nên
        vẫn ra đúng vị trí pixel) — nhưng máy yếu có tải DAO ĐỘNG mạnh giữa
        các chu kỳ (đã đo: `waitKey`/đọc khung hình có lúc rất chậm, có lúc
        bình thường, do tranh chấp CPU với luồng OCR/vẽ/driver màn hình) —
        mỗi lần tốc độ xử lý đổi khác so với lúc fit vận tốc, dự đoán vị trí
        (dùng cho MỌI vòng khớp, kể cả vòng 1 chạy MỌI chu kỳ) lệch khỏi vị
        trí thật — càng lệch nhiều khi 2 mục tiêu đứng gần nhau (đã đo: có
        thể chỉ ~13-16px), dễ khớp nhầm sang mục tiêu bên cạnh dù cả 2 đều
        đang được track bình thường (không cần "trượt"/slipped gì cả) —
        đúng KHỚP triệu chứng "616 và 614 đã bắt được, nhưng dò lại 616 nhảy
        sang 614, đợi 1 lúc có thể tự về hoặc không" (tự về khi tốc độ xử lý
        tình cờ ổn định lại, không tự về khi tiếp tục dao động).
        Fix: `t_sec` đổi sang ĐỒNG HỒ THẬT (`time.perf_counter()`, đơn điệu,
        không phụ thuộc `fps` thiết bị báo) — vận tốc/dự đoán vị trí giờ luôn
        tính đúng theo THỜI GIAN THỰC đã trôi qua, bất kể vòng lặp xử lý
        nhanh/chậm/dao động ra sao. Không đổi field lịch sử (vẫn `(t_sec, dx,
        dy, bx, by)`) hay bất kỳ hàm nào dùng `t_sec` sau đó (`get_velocity`,
        `predict_pos`, `_predict_pixel_pos`) — chúng vốn đã được viết tổng
        quát để nhận `t_sec` là "giây kể từ mốc bất kỳ", không giả định cụ
        thể là `frame_idx/fps`.
        """
        t_sec  = time.perf_counter()
        active = {tid: info for tid, info in self.tracks.items()
                  if frame_idx - info["last_frame"] <= MAX_LOST and info["history"]}
        self.tracks = active
        # Dọn cache vận tốc của track vừa bị xoá (tránh phình bộ nhớ vô hạn
        # qua 1 phiên chạy dài) — xem get_velocity().
        self._vel_cache = {tid: v for tid, v in self._vel_cache.items() if tid in active}

        pred = {tid: self._predict_pixel_pos(tid, t_sec) for tid in active}

        # BUG đã tự phát hiện VÀ TỰ SỬA LẠI trong lúc đo đạc: từng thử thay
        # 3 vòng gen_pairs lồng nhau (Python thuần) bằng 1 ma trận khoảng cách
        # NumPy (blip × track) tính 1 lần — dựa theo 1 lần đo cProfile ban đầu
        # (trên kịch bản KHÔNG có track nào, tức `active` luôn rỗng) TƯỞNG hàm
        # này là điểm nghẽn lớn nhất (~48ms/chu kỳ). Trước khi đưa vào dùng,
        # đo lại NGHIÊM TÚC bằng benchmark riêng (không qua cProfile — cProfile
        # tự nó phóng đại chi phí của mã nhiều lệnh gọi NumPy nhỏ lẻ, không
        # phản ánh đúng thời gian THỰC), với dữ liệu THẬT (51 track bootstrap
        # từ `phong_to.mp4`, ~48 blip/chu kỳ trung bình, lặp lại 3 lần lấy
        # trung bình): bản gốc (vòng lặp Python) ~7.8-10.9ms/chu kỳ, bản
        # "tối ưu" bằng ma trận NumPy lại CHẬM HƠN (~8.7ms/chu kỳ nhưng có lúc
        # đo được chậm hơn bản gốc tới ~12%) — với quy mô blip/track thực tế
        # (vài chục, không phải hàng nghìn), chi phí dựng nhiều mảng NumpPy +
        # chuyển ngược kết quả về tuple Python lại LỚN HƠN lợi ích vector hoá.
        # Đã HUỶ hướng đó, GIỮ NGUYÊN thuật toán vòng lặp gốc — chỉ đổi
        # `np.sqrt` → `math.sqrt` (đo xác nhận nhanh hơn ~13% cho riêng phép
        # tính này, do numpy có chi phí gọi hàm cao hơn hẳn `math` khi tính
        # trên từng số vô hướng thay vì cả mảng) — thay đổi AN TOÀN TUYỆT ĐỐI:
        # `d` chỉ dùng để so sánh/sắp xếp (`pairs.sort`), không bao giờ lưu lại
        # hay hiển thị, nên đổi kiểu float thường (thay vì numpy.float64) không
        # ảnh hưởng gì tới kết quả khớp track.
        def gen_pairs(same_color, gate, require_slipped=False):
            pairs = []
            for bi, blip in enumerate(blips):
                bx, by, area, dist, bear, color, dx, dy = blip
                for tid, info in active.items():
                    if (info["color"] == color) != same_color:
                        continue
                    if require_slipped and frame_idx - info["last_frame"] <= DETECT_EVERY:
                        # Chi cho phep khop O BAN KINH RONG/KHAC MAU khi track da
                        # truot it nhat 1 chu ky day du (chua khop lai duoc o chu
                        # ky truoc) — 1 lan mat blip thoang qua (nhieu/che khuat 1
                        # khung) rat pho bien, khong nen coi la ly do de "nhay xa"
                        # hay "cuop" sang muc tieu khac mau ben canh ngay lap tuc.
                        continue
                    px, py = pred[tid]
                    d = math.sqrt((bx - px) ** 2 + (by - py) ** 2)
                    if d < gate:
                        pairs.append((d, bi, tid))
            pairs.sort(key=lambda p: p[0])
            return pairs

        matched_bi  = set()
        matched_tid = set()
        blip_track  = {}
        # Vòng 1 (cùng màu, hẹp) — như cũ, KHÔNG qua lớp phòng vệ mập mờ (dự
        # đoán còn "tươi", đủ tin cậy).
        #
        # ĐÃ BỎ HẲN vòng 2 (khác màu, hẹp hơn — kế thừa nguyên trạng từ
        # radar_live_2.py, mục đích ban đầu "chịu được sai số phân loại màu
        # THOÁNG QUA do viền anti-alias/nén ảnh"). User xác nhận trực tiếp
        # qua log `[MAU-CHAN-DOAN]` + quan sát màn hình thật: track `?17`
        # (màu RED đã khoá) hiện đúng ID/màu cũ nhưng VỊ TRÍ đã "trôi" sang
        # đúng 1 icon MAGENTA thật gần đó — ĐÂY LÀ VÒNG 2 GÂY RA, không phải
        # giả thuyết ban đầu (đã bác bỏ trước đó: "1 lần khớp nhầm-khác-màu
        # làm track ĐỔI MÀU vĩnh viễn" — fix cũ chỉ khoá `info["color"]`
        # không bị ghi đè, nhưng KHÔNG ngăn được vòng 2 tiếp tục cập nhật VỊ
        # TRÍ track sang blip khác màu mỗi khi nó "trượt" — tức chỉ sửa được
        # nửa vấn đề, để lại đúng nửa kia gây bug "trôi" vừa xác nhận).
        # Root cause: 1 khi màu đã là ĐỊNH DANH khoá vĩnh viễn (không đổi
        # theo blip khớp được), cho phép khớp SANG BLIP KHÁC MÀU tự nó đã
        # mâu thuẫn — nếu blip đó thực sự khác màu, nó KHÔNG THỂ là đúng mục
        # tiêu của track (mục tiêu thật không tự đổi màu áo icon giữa
        # chừng); "sai số phân loại màu thoáng qua" (lý do gốc thêm vòng
        # này) và "mục tiêu khác màu đứng gần" (nguyên nhân bug thật) tạo ra
        # TÍN HIỆU GIỐNG HỆT NHAU ở tầng thuật toán khớp (1 blip khác màu
        # trong bán kính hẹp) — không có cách nào phân biệt đáng tin cậy chỉ
        # từ vị trí/màu, nên KHÔNG còn cách nào giữ vòng này an toàn. Đánh
        # đổi chấp nhận: nếu màu thật sự bị phân loại sai thoáng qua (hiếm,
        # do nén/viền anti-alias), track chỉ "đứng hình" 1-2 chu kỳ (marker
        # giữ nguyên vị trí cũ) rồi tự khớp lại BÌNH THƯỜNG qua vòng 1 ngay
        # khi màu phân loại đúng trở lại — cái giá RẤT NHỎ so với rủi ro
        # trước đây (track lặng lẽ bám NHẦM mục tiêu khác trong "tác chiến").
        #
        # Vòng 3 (cùng màu, RỘNG HƠN HẲN — bắt bước NHẢY VỊ TRÍ RỜI RẠC thật,
        # xem docstring trên ASSOC_DIST_WIDE) vẫn giữ, chỉ kích hoạt khi track
        # đã trượt ≥1 chu kỳ (dự đoán "đóng băng", kém tin cậy hơn) — qua
        # `_filter_ambiguous_pairs()` TRƯỚC khi gộp vào all_pairs: loại các
        # cặp có ứng viên khác cạnh tranh cùng blip/track ở khoảng cách gần
        # tương đương (xem docstring trên ROUND_AMBIG_MARGIN_PX) — thà track
        # "đứng hình" 1 chu kỳ còn hơn đoán nhầm sang mục tiêu khác trong khi
        # vẫn hiện đúng ID cũ.
        pairs3 = _filter_ambiguous_pairs(gen_pairs(True, ASSOC_DIST_WIDE, require_slipped=True))
        all_pairs = ([(d, bi, tid, 1) for d, bi, tid in gen_pairs(True, ASSOC_DIST)]
                     + [(d, bi, tid, 3) for d, bi, tid in pairs3])
        for _d, bi, tid, _round in all_pairs:
            if bi in matched_bi or tid in matched_tid:
                continue
            matched_bi.add(bi); matched_tid.add(tid)
            blip_track[bi] = tid
            # Log chẩn đoán: user báo "báo ID 616 nhưng điểm bám lạc chỗ
            # khác" — cùng gốc nghi vấn đã ghi nhận trước ("bắt nhầm mục
            # tiêu, vài giây sau mới đúng"). Giữ lại log này SAU KHI đã thêm
            # `_filter_ambiguous_pairs()` — 1 pair round 3 lọt qua tới đây
            # đáng lẽ KHÔNG còn rival nào trong `pairs3` (đã lọc), nên
            # n_blip_riv/n_track_riv in ra đây kỳ vọng luôn =0; nếu user vẫn
            # thấy dòng này với rival >0, nghĩa là lớp phòng vệ mới có kẽ hở
            # cần xem lại (khác với trước đây — trước đây MỌI pair round 3
            # có thể có rival, kể cả khi được chấp nhận).
            if _round == 3:
                bx, by = blips[bi][0], blips[bi][1]
                color = blips[bi][5]
                n_blip_riv  = sum(1 for _d2, bi2, _t2 in pairs3 if bi2 == bi) - 1
                n_track_riv = sum(1 for _d2, _b2, tid2 in pairs3 if tid2 == tid) - 1
                print(f"[TRACK-MATCH-RONG-CHAN-DOAN] {tid} <- blip@({bx},{by}) {color} d={_d:.1f}px "
                      f"blip_bi_tranh_boi={n_blip_riv}_track_khac "
                      f"track_co_the_chon={n_track_riv}_blip_khac", flush=True)

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
        t_sec = time.perf_counter()
        tid   = self._new_anon()
        self.tracks[tid] = {
            "history":     [(t_sec, dx, dy, bx, by)],
            "color":       color,
            "last_frame":  frame_idx,
            "spoken_once": False,
            "was_lost":    False,
            "auto":        auto,
            # Track do user Shift+Click (auto=False) coi như "đã duyệt" ngay
            # (chính hành động click đã là xác nhận) — track do auto-scan tự
            # tạo (auto=True) coi là CHƯA DUYỆT cho tới khi qua bảng ID
            # (_id_panel_confirm/_id_panel_cancel) hoặc đang được bảng đó trỏ
            # tới — xem draw_frame() (gate vẽ khoanh tròn) và docstring trên
            # ID_PANEL_LINE_COLOR.
            "reviewed":    not auto,
            # True ngay sau khi track được đưa vào `_id_panel_queue` LẦN ĐẦU
            # — chặn `_global_auto_worker` nhồi trùng lặp tid vào hàng đợi ở
            # mỗi vòng round-robin trong lúc nó còn đang chờ tới lượt xử lý
            # (xem nhánh "chưa duyệt" trong _global_auto_worker).
            "queued_for_panel": False,
        }
        print(f"[CONFIRM] {tid} ({color}) @ px({bx},{by})" + (" [auto]" if auto else ""), flush=True)
        # "Vừa dò vừa bám": đẩy track mới vào hàng chờ ưu tiên MỘT LẦN cho
        # luồng OCR nền (xem docstring `_ocr_fresh_tids`) — không đợi tới
        # lượt round-robin bình thường mới bắt đầu đọc ID.
        _ocr_fresh_tids.add(tid)
        return tid

    def get_velocity(self, tid, min_pts=3):
        """Vận tốc (km/s) ước lượng bằng hồi quy tuyến tính (np.polyfit) trên
        tối đa 10 điểm lịch sử gần nhất — kết quả CHỈ phụ thuộc `history`
        (không phụ thuộc frame/thời điểm gọi), nên cache theo (độ dài,
        t cuối cùng) của history: 2 giá trị này CHỈ đổi khi có điểm mới được
        thêm vào (`TrackManager.update()`), nên cache HIT ở mọi lần gọi khác
        trong cùng khoảng đó. Trước đây hàm này bị gọi lại TỪ ĐẦU (2 lần
        polyfit) ở NHIỀU nơi cho CÙNG 1 track: draw_frame() (MỖI khung hình
        render, không chỉ mỗi chu kỳ detect — tần suất cao hơn hẳn), cộng
        thêm build_table()/write_live_outputs() (2 lần trong write_live_outputs)
        và TrackManager.update() (_predict_pixel_pos) mỗi chu kỳ detect —
        tổng cộng có thể 4-5+ lần polyfit TRÙNG LẶP/track/chu kỳ mà kết quả
        giống hệt nhau. Cache giúp chỉ tính 1 LẦN, phần còn lại chỉ tra dict."""
        hist = self.tracks[tid]["history"]
        if len(hist) < min_pts:
            return None, None
        cache_key = (len(hist), hist[-1][0])
        cached = self._vel_cache.get(tid)
        if cached is not None and cached[0] == cache_key:
            return cached[1], cached[2]
        recent = hist[-min(10, len(hist)):]
        ts = np.array([h[0] for h in recent])
        xs = np.array([h[1] for h in recent])
        ys = np.array([h[2] for h in recent])
        if ts[-1] - ts[0] < 0.5:
            vx, vy = None, None
        else:
            vx, vy = float(np.polyfit(ts, xs, 1)[0]), float(np.polyfit(ts, ys, 1)[0])
        self._vel_cache[tid] = (cache_key, vx, vy)
        return vx, vy

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

def _apply_id_color_rules(info, new_id):
    """Gọi NGAY sau khi operator xác nhận đổi tên track thành `new_id` qua
    bảng ID thủ công (xem `_id_panel_confirm()`) — KHÔNG áp dụng cho track
    do OCR tự chốt (`_ocr_confirmed`), chỉ đường thủ công theo đúng yêu cầu
    "khi dùng tay chỉnh ID". Đặt `info["display_color"]`/`info["id_label"]`
    theo `_ID_COLOR_RULES` đã nạp — xem docstring đầy đủ ở khối định nghĩa
    `ID_COLOR_RULES_JSON_PATH` (gần `COLOR_MAP`) — KHÔNG đổi `info["color"]`."""
    if not new_id.isdigit():
        return
    color = _ID_COLOR_RULES["digit_color"].get(new_id[0])
    if color:
        info["display_color"] = color
    val = int(new_id)
    label = None
    for r in _ID_COLOR_RULES["id_ranges"]:
        try:
            if int(r["min"]) <= val <= int(r["max"]):
                label = r.get("label") or None
                break
        except (KeyError, TypeError, ValueError):
            continue
    info["id_label"] = label

def _track_display(info):
    """(tên màu, màu BGR, chữ "loại") dùng cho MỌI nơi HIỂN THỊ cho operator
    (vòng tròn, tooltip, bảng, JSON/HTML) — ưu tiên `display_color`/`id_label`
    (do `_apply_id_color_rules()` đặt khi operator tự sửa ID tay), rơi về
    `info["color"]` (màu HSV gốc)/`_LOAI_VN` nếu chưa từng sửa tay. KHÔNG
    BAO GIỜ dùng cho tracking/matching/loại trừ tự động — những chỗ đó PHẢI
    dùng `info["color"]` trực tiếp (màu thật đã khoá lúc xác nhận)."""
    cname = info.get("display_color") or info["color"]
    bgr   = COLOR_MAP.get(cname, UNKNOWN_COL)
    loai  = info.get("id_label") or _LOAI_VN.get(cname, cname)
    return cname, bgr, loai

def draw_tooltip(canvas, tid, info, mx, my):
    hist = info["history"]
    if not hist:
        return
    _, xkm, ykm, _, _ = hist[-1]
    dist  = float(np.sqrt(xkm**2 + ykm**2))
    bear  = compass_bearing(xkm, ykm)
    _, color, loai = _track_display(info)
    did   = display_id(tid)

    lines = [
        (f"ID: {did}",                                            (220,220,220), _PIL_FONT),
        (f"Loại: {loai}",                                         color,         _PIL_FONT_BD),
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

def _draw_id_panel(canvas, tm):
    """Bảng xác nhận ID mục tiêu mới, cố định góc trên-trái — xem docstring
    đầy đủ ngay trên _id_panel_activate_next()."""
    if not _id_panel["active"]:
        return
    tid  = _id_panel["tid"]
    info = tm.tracks.get(tid)
    if info is None:
        _id_panel["active"] = False
        return
    hist = info["history"]
    if not hist:
        return
    _, xkm, ykm, _, _ = hist[-1]
    tx, ty = to_px(xkm, ykm)
    _, color, _ = _track_display(info)

    px, py = ID_PANEL_POS
    w, h   = ID_PANEL_W, ID_PANEL_H
    anchor = (px + w, py + h)
    cv2.line(canvas, anchor, (tx, ty), ID_PANEL_LINE_COLOR, 1, cv2.LINE_AA)
    cv2.circle(canvas, (tx, ty), 12, ID_PANEL_LINE_COLOR, 2, cv2.LINE_AA)

    cv2.rectangle(canvas, (px, py), (px + w, py + h), (14, 14, 14), -1)
    cv2.rectangle(canvas, (px, py), (px + w, py + h), ID_PANEL_LINE_COLOR, 1, cv2.LINE_AA)

    # User yêu cầu chữ đậm hơn — tăng thickness cv2.putText 1→2 cho các dòng
    # nội dung chính (ID/chu kỳ); dòng hướng dẫn phím ở cuối giữ thickness 1
    # (cố ý nhỏ/nhạt hơn, chỉ là gợi ý phụ). Mọi `cv2.getTextSize` dùng để đo
    # bề rộng chữ (khung bôi đen, vị trí con trỏ) đổi THEO ĐÚNG thickness
    # đang vẽ, để không lệch vị trí so với chữ thật.
    BOLD = 2

    # Tiêu đề: đổi từ "XAC NHAN MUC TIEU [RED]" (không dấu, hiện mã màu thô)
    # sang tên LOẠI bằng tiếng Việt CÓ DẤU theo đúng quy ước đã dùng ở
    # draw_tooltip()/_LOAI_VN (vd "ĐỊCH", "QUÂN SỰ"...), in ĐẬM, cỡ chữ lớn
    # hơn (20px, +2 so với _PIL_FONT_BD 18px) — theo yêu cầu user. cv2.putText
    # (font Hershey) không vẽ được dấu tiếng Việt nên phải dùng PIL, NHƯNG chỉ
    # PIL-hoá đúng VÙNG CROP nhỏ của dòng tiêu đề (không phải cả khung hình
    # như draw_tooltip()) — đã đo: PIL roundtrip toàn khung 1920x1080 tốn
    # ~34ms/lần (bảng ID hiện liên tục nhiều khung hình liền, không phải chỉ
    # lúc hover như tooltip, nên cái giá đó KHÔNG chấp nhận được), trong khi
    # chỉ crop đúng vùng tiêu đề (~300x24px) chỉ tốn ~2.7ms/lần (~12.6 lần rẻ
    # hơn) — vẫn giữ được chữ có dấu mà không đánh đổi hiệu năng.
    pending = _id_panel_queue.qsize()
    _, _, loai = _track_display(info)
    title = loai.upper() + (f"  (+{pending} chờ)" if pending else "")
    title_y0, title_y1 = py + 2, py + 26
    title_crop = canvas[title_y0:title_y1, px + 2:px + w - 2]
    pil_title = Image.fromarray(cv2.cvtColor(title_crop, cv2.COLOR_BGR2RGB))
    ImageDraw.Draw(pil_title).text((4, 2), title, font=_PIL_FONT_BD_20,
                                    fill=(color[2], color[1], color[0]))
    title_crop[:] = cv2.cvtColor(np.array(pil_title), cv2.COLOR_RGB2BGR)

    # Dòng ID
    row_y = py + 44
    cv2.putText(canvas, "ID:", (px + 8, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), BOLD, cv2.LINE_AA)
    id_x  = px + 42
    id_txt = _id_panel["id_text"]
    (tw, th), _ = cv2.getTextSize(id_txt if id_txt else " ", cv2.FONT_HERSHEY_SIMPLEX, 0.5, BOLD)
    if _id_panel["field"] == "id" and _id_panel["id_selected"] and id_txt:
        cv2.rectangle(canvas, (id_x - 2, row_y - th - 4), (id_x + tw + 2, row_y + 4),
                      ID_PANEL_LINE_COLOR, -1)
        id_col = (10, 10, 10)
    else:
        id_col = (255, 255, 255)
    cv2.putText(canvas, id_txt, (id_x, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, id_col, BOLD, cv2.LINE_AA)
    if _id_panel["field"] == "id" and not _id_panel["id_selected"]:
        cur_w = cv2.getTextSize(id_txt[:_id_panel["id_cursor"]], cv2.FONT_HERSHEY_SIMPLEX, 0.5, BOLD)[0][0]
        cv2.line(canvas, (id_x + cur_w, row_y - th - 2), (id_x + cur_w, row_y + 2), (255,255,255), 1)

    # Dòng chu kỳ phát
    row_y2 = py + 70
    cv2.putText(canvas, "Chu ky (giay):", (px + 8, row_y2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), BOLD, cv2.LINE_AA)
    iv_x    = px + 128
    iv_txt  = _id_panel["interval_text"]
    iv_show = iv_txt if iv_txt else "60 (mac dinh)"
    iv_col  = (255,255,255) if iv_txt else (140,140,140)
    cv2.putText(canvas, iv_show, (iv_x, row_y2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, iv_col, BOLD, cv2.LINE_AA)
    if _id_panel["field"] == "interval":
        cur_w = cv2.getTextSize(iv_txt[:_id_panel["int_cursor"]], cv2.FONT_HERSHEY_SIMPLEX, 0.5, BOLD)[0][0] if iv_txt else 0
        cv2.line(canvas, (iv_x + cur_w, row_y2 - 14), (iv_x + cur_w, row_y2 + 2), (255,255,255), 1)

    cv2.putText(canvas, "ENTER:xac nhan  TAB:doi truong  ESC:bo qua", (px + 8, py + h - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (150,150,150), 1, cv2.LINE_AA)

# ══════════════════════════════════════════════════════════════════════════════
# DRAW FRAME
# ══════════════════════════════════════════════════════════════════════════════
def draw_frame(canvas, frame_idx, tm, mx=0, my=0, source_label="", paused=False, drag_rect=None):
    hovered_tid  = None

    for tid, info in tm.tracks.items():
        if frame_idx - info["last_frame"] > VISIBLE_LOST:
            continue
        hist  = info["history"]
        _, color, _ = _track_display(info)
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

        # Lịch sử vòng khoanh màu quanh mục tiêu: ban đầu MỌI track bị khoanh
        # tròn+dấu cộng NGAY LẬP TỨC → chỉ khoanh khi đã "duyệt" hoặc đang
        # được bảng ID trỏ tới → tách dấu cộng khỏi vòng tròn khi CHƯA xác
        # nhận (che mất icon) → bỏ HẲN vòng tròn khi ĐÃ xác nhận (rối mắt) →
        # user yêu cầu tiếp: bỏ nốt cả lúc ĐANG chờ xác nhận → user yêu cầu
        # THÊM LẠI (xem docstring `RING_RADIUS_PX`/`RING_LIGHTEN` phía trên):
        # vòng tròn NHẠT (pha loãng về trắng, không phải màu track nguyên
        # bản) — nhưng khi đó vẫn còn gác cổng bằng `info["reviewed"]`.
        # BUG đã sửa: gác cổng đó lặng lẽ vô hiệu hoá vòng tròn cho HẦU HẾT
        # track "Phát tự động" — sau khi v6 đổi bảng ID KHÔNG còn tự bật cho
        # track auto-scan nữa (xem mục "Bảng ID góc trên-trái KHÔNG còn tự
        # động bật" trong CLAUDE.md), `reviewed` của 1 track `auto=True` chỉ
        # được đặt `True` nếu operator TỰ Shift+Click/chuột phải mở bảng cho
        # ĐÚNG track đó — với "Phát tự động" (tạo hàng loạt track không cần
        # thao tác tay), gần như KHÔNG track nào đạt điều kiện này, nên vòng
        # tròn coi như biến mất khỏi MỌI mục tiêu tự động phát hiện — đúng
        # triệu chứng user báo "mục tiêu phát hiện được không có vòng tròn
        # như cũ". Fix: bỏ hẳn điều kiện `reviewed` — vẽ vòng tròn cho MỌI
        # track đã tồn tại trong `tm.tracks` (đã phát hiện = có vòng ngay,
        # đúng ý "như cái cũ"), không phân biệt đã duyệt tên/ID hay chưa.
        ring_color = tuple(int(c + (255 - c) * RING_LIGHTEN) for c in color)
        # KHÔNG dùng cv2.LINE_AA — đây là hình vẽ chạy MỖI KHUNG HÌNH (mọi
        # track, không throttle như các bổ sung khác trong phiên này), khác
        # các phép tính 1 lần/chu kỳ detect còn lại. Benchmark trực tiếp (30
        # track): có AA ~1.03ms, không AA ~0.55ms (~47% rẻ hơn) — đường viền
        # 1px bán kính nhỏ, đã nhạt màu sẵn (RING_LIGHTEN), nên răng cưa
        # không đáng ngại về mặt thị giác, không đáng đánh đổi thêm CPU mỗi
        # khung hình trên máy yếu (Wyse 5070) cho việc này. Bỏ điều kiện
        # `reviewed` KHÔNG đổi chi phí/track (vẫn đúng 1 lệnh cv2.circle như
        # trước) — chỉ đổi tổng SỐ track được vẽ, vẫn tỉ lệ thuận
        # len(tm.tracks) như benchmark gốc đã đo (an toàn cho mọi số lượng
        # track thực tế quan sát được, tối đa ~16-20 track/phiên).
        cv2.circle(canvas, (px_last, py_last), RING_RADIUS_PX, ring_color, 1)

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
             f"   [Delete] xoa   [Shift+Delete] xoa+loai tru vinh vien   [Space] tam dung"
             f"   [Phai] ID/hen   [Q/Esc] thoat")
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 22), (0, 0, 0), -1)
    cv2.putText(canvas, bar, (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0,220,220), 1)

    fw_c = canvas.shape[1]
    by1 = 0;  by2 = _BTN_AUTO_H

    # Nut "Phat" GỘP — thay 2 nút PHÁT TỰ ĐỘNG (nhanh)/PHÁT CHẬM cũ. Nhãn HIỂN
    # THỊ TÊN TRẠNG THÁI HIỆN TẠI (khác quy ước "hành động sẽ xảy ra" của các
    # nút khác trong file) — đúng yêu cầu user: bình thường "Phát", bấm 1 lần
    # "Phát chậm", bấm nữa "Phát nhanh", bấm nữa về "Phát" (tắt). Xem
    # cycle_play_button() cho logic chu trình 3 trạng thái.
    bx1 = fw_c - _BTN_AUTO_W - 4;  bx2 = fw_c - 4
    if _global_auto_slow_active:
        btn_bg, btn_bdr, btn_txt = (0, 90, 140), (0, 170, 255), "||  PHAT CHAM"
    elif _global_auto_active:
        btn_bg, btn_bdr, btn_txt = (0, 110, 0), (0, 210, 80), "||  PHAT NHANH"
    else:
        btn_bg, btn_bdr, btn_txt = (38, 38, 38), (90, 90, 90), ">  PHAT"
    cv2.rectangle(canvas, (bx1, by1), (bx2, by2), btn_bg,  -1)
    cv2.rectangle(canvas, (bx1, by1), (bx2, by2), btn_bdr,  1)
    cv2.putText(canvas, btn_txt, (bx1 + 7, by2 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.44, (225, 225, 225), 1, cv2.LINE_AA)

    # Nut "Uu tien" — ben trai nut Phat. Bat/tat doc lap voi trang thai Phat
    # (co the bat truoc khi bam Phat) — xem toggle_priority_manual_only().
    # Mau nau (khop ID_PANEL_LINE_COLOR) khi BAT — cùng tông với đường nối
    # bảng ID (vốn chỉ dùng cho track do chính tay xác nhận), gợi liên tưởng
    # đúng ý nghĩa "ưu tiên mục tiêu chọn tay".
    pbx2 = bx1 - 4;  pbx1 = pbx2 - _BTN_AUTO_W
    if _priority_manual_only:
        pbtn_bg, pbtn_bdr, pbtn_txt = (20, 45, 75), ID_PANEL_LINE_COLOR, "■  UU TIEN (BAT)"
    else:
        pbtn_bg, pbtn_bdr, pbtn_txt = (38, 38, 38), (90, 90, 90), ">  UU TIEN"
    cv2.rectangle(canvas, (pbx1, by1), (pbx2, by2), pbtn_bg, -1)
    cv2.rectangle(canvas, (pbx1, by1), (pbx2, by2), pbtn_bdr, 1)
    cv2.putText(canvas, pbtn_txt, (pbx1 + 7, by2 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.44, (225, 225, 225), 1, cv2.LINE_AA)

    _draw_id_panel(canvas, tm)

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
        cname, color, _ = _track_display(info)
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
        cells = [(str(i+1),(180,180,180)), (cname,color), (did,color),
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

# BUG/tối ưu đã sửa: đo bằng cProfile trên dữ liệu thật — `write_live_outputs()`
# ghi 2 file (JSON + HTML) bằng `open()+write()+os.replace()` NGAY TRONG vòng
# lặp chính mỗi chu kỳ detect — thao tác ĐĨA (I/O) này BLOCK hẳn luồng chính
# trong lúc chờ hệ điều hành hoàn tất, đo được tới ~10-20ms/lần riêng cho
# `os.replace()` (24 lần gọi/12 chu kỳ = 2 lần/chu kỳ, tổng có lúc đo được
# 0.29s/12 chu kỳ) — CHÍNH LÀ 1 nguồn "lag" thực tế, vì mọi bước còn lại của
# vòng lặp (đọc khung hình tiếp theo, vẽ, xử lý chuột/phím) phải ĐỢI xong I/O
# này trước khi tiếp tục. Nội dung 2 file (JSON/HTML) chỉ dùng để hiển thị
# cho công cụ NGOÀI app (trình duyệt/tool khác đọc `live_tracks.json`/`.html`)
# — độ trễ vài chục-trăm ms của các file này KHÔNG ảnh hưởng gì tới detect/
# tracking/TTS bên trong app, nên đây là ứng viên AN TOÀN để chuyển ra nền.
# Fix: `write_live_outputs()` vẫn đọc `tm.tracks` và DỰNG SẴN chuỗi JSON/HTML
# NGAY TRONG luồng chính như cũ (nhanh, chỉ là format chuỗi, không phải I/O)
# — chỉ chuyển đúng phần GHI RA ĐĨA (chậm) sang 1 luồng nền riêng
# (`_live_output_worker`), đánh thức bằng `threading.Event` mỗi khi có dữ
# liệu mới. Dùng "ô nhớ mới nhất" (`_live_output_pending`) thay vì hàng đợi
# không giới hạn — nếu luồng ghi đĩa có lỡ chậm hơn tốc độ chu kỳ detect, chỉ
# NỘI DUNG MỚI NHẤT được ghi (bỏ qua các phiên bản cũ hơn đang chờ), không
# bao giờ phình hàng đợi hay ghi dồn dữ liệu đã lỗi thời.
_live_output_pending = {"json": None, "html": None}
_live_output_lock  = threading.Lock()
_live_output_event = threading.Event()

def _live_output_write_one(path, text):
    try:
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(path + ".tmp", path)
    except PermissionError:
        try: os.remove(path + ".tmp")
        except OSError: pass

def _live_output_worker(stop_evt):
    while not stop_evt.is_set():
        if not _live_output_event.wait(timeout=1.0):
            continue
        _live_output_event.clear()
        with _live_output_lock:
            json_payload = _live_output_pending["json"]
            html_payload = _live_output_pending["html"]
            _live_output_pending["json"] = None
            _live_output_pending["html"] = None
        if json_payload is not None:
            _live_output_write_one(*json_payload)
        if html_payload is not None:
            _live_output_write_one(*html_payload)

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
        _dcname, _, _dloai = _track_display(info)
        lt[tid] = {"color": info["color"], "display_color": _dcname, "id_label": _dloai,
                   "dist_km":  round(float(np.sqrt(xkm**2+ykm**2)), 1),
                   "bearing":  round(compass_bearing(xkm, ykm), 1),
                   "speed_kmh": spd, "pos_px": [px, py],
                   "named": not tid.startswith("?"),
                   "display_id": display_id(tid),
                   "ocr_id": _ocr_confirmed.get(tid)}
    payload = {"frame": frame_idx, "t_sec": round(t_sec, 2), "km_px": round(KM_PX, 5), "tracks": lt}
    _p = os.path.join(_BASE_DIR, "live_tracks.json")
    json_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    rows = []
    for i, (tid, info) in enumerate(active, 1):
        if not info["history"]: continue
        _, xkm, ykm, _, _ = info["history"][-1]
        _cname, _, loai = _track_display(info)
        color = _CSS_COLOR.get(_cname, "#aaaaaa")
        did   = display_id(tid)
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
        '<meta http-equiv="refresh" content="2"><title>RadarVRS</title>'
        '<style>body{background:#0a0a0a;color:#ddd;font-family:monospace;margin:0;padding:12px}'
        'h2{color:#00dddd;margin:0 0 6px;font-size:16px;letter-spacing:2px}'
        '.info{color:#888;font-size:12px;margin-bottom:10px}'
        'table{border-collapse:collapse;width:100%;max-width:620px}'
        'th{background:#0d3333;color:#00dddd;padding:7px 10px;text-align:left;font-size:13px;border-bottom:1px solid #1a5555}'
        'td{padding:6px 10px;font-size:13px;border-bottom:1px solid #1a1a1a}'
        'tr:hover td{background:#111}</style></head><body>'
        '<h2>&#9632; RADARVRS — DANH SÁCH MỤC TIÊU</h2>'
        f'<div class="info">t={t_sec:.1f}s &nbsp;|&nbsp; '
        f'<b style="color:#44dd44">{n_named}</b>/{len(active)} mục tiêu &nbsp;|&nbsp; '
        '<span style="color:#555">tự cập nhật mỗi 2s</span></div>'
        '<table><thead><tr>'
        '<th>#</th><th>Loại</th><th>ID</th>'
        '<th>Cự ly(km)</th><th>Góc(°)</th><th>Tốc(km/h)</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table></body></html>'
    )
    with _live_output_lock:
        _live_output_pending["json"] = (_p, json_text)
        _live_output_pending["html"] = (_HTML_PATH, html)
    _live_output_event.set()

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
    """Ghi CX/CY/R_300KM moi nhat de lan chay sau tu dong dung.
    Ban dong goi (.exe): khong co file .py that tren dia de ghi de (ma nguon
    nam trong chinh exe) -> ghi ra calibration.json canh exe thay the (doc
    lai luc khoi dong, xem _load_calibration_override). Chay tu source: giu
    nguyen hanh vi cu, ghi thang vao file .py nay."""
    if getattr(sys, "frozen", False):
        try:
            with open(_CALIB_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump({"CX": cx, "CY": cy, "R_300KM": r}, f)
            print(f"[CALIB] Da ghi: {_CALIB_JSON_PATH}")
        except Exception as e:
            print(f"[CALIB] Loi ghi calibration.json: {e}")
        return
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

def calibrate_radar_center(cap, mon, frame, loop_video=False):
    """
    Hiển thị VIDEO TRỰC TIẾP (đọc frame mới từ `cap` mỗi vòng lặp) để user
    chỉnh tâm radar và bán kính 300km — không đóng băng ở đúng 1 khung hình
    tĩnh như trước (khung đầu tiên đọc được ngay sau khi mở thiết bị capture
    có thể đen/nhiễu do tín hiệu chưa ổn định, khiến cửa sổ chỉnh tâm trông
    như trống rỗng). `frame` chỉ dùng làm khung khởi tạo/hiển thị ngay trước
    khi có khung mới đầu tiên. `loop_video=True` (nguồn phát lại file) sẽ tua
    về đầu khi hết video thay vì dừng lại.
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
    _cur_frame = [frame]

    def draw_overlay():
        img  = cv2.resize(_cur_frame[0], (dw, dh), interpolation=cv2.INTER_LINEAR)
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
        ok, new_frame = cap.read()
        if not ok or new_frame is None:
            if loop_video:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, new_frame = cap.read()
        if ok and new_frame is not None:
            _cur_frame[0] = new_frame

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
# DÒ THIẾT BỊ VIDEO CAPTURE (HDMI/USB) — port từ radar_live_2.py, chỉ giữ lại
# phần VIDEO (không cần COM/Serial/PnP khác — không liên quan tới nguồn ảnh
# radar). Dò index 0..N-1 qua DirectShow, giữ lại thiết bị mở được và đọc
# được frame; yêu cầu CAPTURE_W x CAPTURE_H để lấy NGUYÊN khung hình gốc thay
# vì crop 640x480 mặc định của DirectShow.
# ══════════════════════════════════════════════════════════════════════════════
def _wmi_video_names():
    names = []
    try:
        wmi = win32com.client.GetObject("winmgmts:")
        where = "PNPClass='Camera' OR PNPClass='Image' OR PNPClass='MEDIA' OR PNPClass='AVC'"
        for it in wmi.ExecQuery(f"SELECT Name FROM Win32_PnPEntity WHERE {where}"):
            if getattr(it, "Name", None):
                names.append(it.Name)
    except Exception:
        pass
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

def show_video_device_dialog(devices):
    """Trả về {'index':int,'name':str,'res':str} hoặc None nếu huỷ. Tự động
    chọn luôn nếu chỉ có đúng 1 thiết bị dò được — khỏi cần hỏi."""
    if len(devices) == 1:
        return devices[0]

    result = {"value": None}
    root = tk.Tk()
    root.title("Chọn thiết bị video capture (USB/HDMI)")
    root.geometry("620x360")
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

    tk.Label(root, text="Các thiết bị video capture đã dò được — chọn rồi bấm Chọn:",
             bg="#111", fg="#00dddd", font=("Consolas", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 4))

    tree = ttk.Treeview(root, columns=("info",), show="tree headings", height=10)
    tree.heading("#0", text="Thiết bị")
    tree.heading("info", text="Chi tiết")
    tree.column("#0", width=340)
    tree.column("info", width=220)
    tree.pack(fill="both", expand=True, padx=12, pady=4)

    node_map = {}
    for d in devices:
        iid = tree.insert("", "end", text=d["name"], values=(f"index={d['index']}  {d['res']}",))
        node_map[iid] = d
    if not devices:
        tree.insert("", "end", text="(không tìm thấy thiết bị video capture nào)", values=("",))

    btn_frame = tk.Frame(root, bg="#111")
    btn_frame.pack(fill="x", padx=12, pady=(4, 12))

    def on_select(_event=None):
        sel = tree.selection()
        if not sel or sel[0] not in node_map:
            tkinter.messagebox.showwarning("Chưa chọn", "Hãy chọn một thiết bị cụ thể.", parent=root)
            return
        result["value"] = node_map[sel[0]]
        root.destroy()

    def on_cancel():
        root.destroy()

    tk.Button(btn_frame, text="Chọn", width=12, bg="#005555", fg="#ffffff",
              font=("Consolas", 10), relief="flat", command=on_select).pack(side="right", padx=4)
    tk.Button(btn_frame, text="Huỷ", width=12, bg="#553300", fg="#ffffff",
              font=("Consolas", 10), relief="flat", command=on_cancel).pack(side="right", padx=4)
    tree.bind("<Double-1>", on_select)
    root.mainloop()
    return result["value"]

# ══════════════════════════════════════════════════════════════════════════════
# LETTERBOX: hiện khung hình fullscreen GIỮ NGUYÊN TỈ LỆ GỐC (đệm viền đen 2
# bên thay vì kéo giãn méo) — KHÔI PHỤC lại y hệt `radar_live_4.py` (bản tham
# chiếu). User từng yêu cầu đổi sang "ép lấp đầy" (`_stretch_frame`, xem lịch
# sử ngay trên trong CLAUDE.md) rồi lập tức phản hồi lại "hiện tại đang đầy
# màn hình á. Khôi phục để màn hình như bản cũ radar_live_4" — tức là YÊU CẦU
# TRƯỚC bị hiểu SAI hướng (tưởng "ép lại như cũ" nghĩa là bỏ letterbox, thực
# ra "như cũ" ám chỉ đúng trạng thái letterbox đang có sẵn ở v4). Khôi phục
# nguyên trạng: `_letterbox_transform()` là nguồn DUY NHẤT tính tỉ lệ/offset —
# dùng CHUNG cho cả `_letterbox_frame()` (vẽ) và `click_to_frame()` (ánh xạ
# click ngược) để không bao giờ lệch nhau.
# ══════════════════════════════════════════════════════════════════════════════
def _letterbox_transform(src_w, src_h, dst_w, dst_h):
    """Tỉ lệ co giãn GIỮ NGUYÊN TỈ LỆ GỐC để vừa trong (dst_w,dst_h), cùng
    kích thước ảnh sau co giãn và độ đệm (viền đen) mỗi bên."""
    scale = min(dst_w / max(src_w, 1), dst_h / max(src_h, 1))
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))
    pad_x = (dst_w - new_w) // 2
    pad_y = (dst_h - new_h) // 2
    return scale, new_w, new_h, pad_x, pad_y

# Tối ưu: giữ 1 canvas DÙNG CHUNG qua các lần gọi (viền đen chỉ tô lại khi
# kích thước đổi — hiếm), mỗi khung chỉ `cv2.resize(..., dst=...)` ghi THẲNG
# vào đúng vùng ảnh bên trong canvas đó — không cấp phát gì thêm mỗi khung.
_letterbox_cache = {"key": None, "canvas": None}

def _letterbox_frame(img, dst_w, dst_h):
    """Co giãn `img` GIỮ NGUYÊN TỈ LỆ để vừa khung (dst_w,dst_h), đệm viền
    đen 2 bên thay vì kéo méo tỉ lệ — trả về canvas đúng (dst_h,dst_w,3)."""
    h, w = img.shape[:2]
    scale, new_w, new_h, pad_x, pad_y = _letterbox_transform(w, h, dst_w, dst_h)
    key = (dst_w, dst_h, w, h)
    if _letterbox_cache["key"] != key:
        _letterbox_cache["canvas"] = np.zeros((dst_h, dst_w, 3), np.uint8)
        _letterbox_cache["key"] = key
    canvas = _letterbox_cache["canvas"]
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    cv2.resize(img, (new_w, new_h), dst=canvas[pad_y:pad_y+new_h, pad_x:pad_x+new_w],
               interpolation=interp)
    return canvas

# ══════════════════════════════════════════════════════════════════════════════
# CHUYỂN TỌA ĐỘ CLICK TOÀN CỤC (pynput, toạ độ màn hình vật lý) → FRAME SPACE
# ══════════════════════════════════════════════════════════════════════════════
def click_to_frame(sx, sy, fs_mon, frame_shape):
    fh, fw = frame_shape[:2]
    fl, ft = fs_mon["left"], fs_mon["top"]
    fw_d, fh_d = fs_mon["width"], fs_mon["height"]
    scale, new_w, new_h, pad_x, pad_y = _letterbox_transform(fw, fh, fw_d, fh_d)
    rel_x, rel_y = sx - fl, sy - ft
    # Click rơi vào viền đen letterbox (ngoài vùng ảnh thật) — không có blip
    # nào ở đó, coi như không hit.
    if not (pad_x <= rel_x < pad_x + new_w and pad_y <= rel_y < pad_y + new_h):
        return None
    return int((rel_x - pad_x) / scale), int((rel_y - pad_y) / scale)

# ══════════════════════════════════════════════════════════════════════════════
# CHẠY PIPELINE RADAR TỪ THIẾT BỊ VIDEO CAPTURE (HDMI/USB) — vd USB_Video
# capture card, giữ NGUYÊN khung hình gốc (không crop/scale), như
# radar_live_2.py. Khác radar_live_2.py: giữ lại toàn bộ pipeline nâng cao của
# v4 (mốc tỉ lệ ORB/AKAZE tự-làm-mới, 3 lớp lọc nhiễu) — vì nguồn thật (phần
# mềm ATC) qua capture card vẫn có thể đổi tầm quan sát (zoom) giữa chừng
# giống hệt phong_to.mp4, không phải giả định "khung hình cố định" của
# radar_live_2.py gốc.
#
# Click chuột bắt qua HOOK TOÀN CỤC (pynput) thay vì cv2.setMouseCallback cục
# bộ: cửa sổ chạy true fullscreen (`cv2.WINDOW_FULLSCREEN`) trên đúng monitor
# xuất hình signal ra ngoài — kế thừa nguyên nhân từ radar_live_2.py (bấm
# chuột lúc cửa sổ ở chế độ này không phải lúc nào Qt/HighGUI cũng chuyển sự
# kiện click về đúng callback cục bộ). Vị trí con trỏ (để hiện tooltip khi
# rê chuột, không cần bấm) vẫn dùng cv2.setMouseCallback bình thường — chỉ
# MOVE mới cần, không phải click, nên không gặp vấn đề trên.
# ══════════════════════════════════════════════════════════════════════════════
def run_radar_from_capture(device_index, device_label):
    cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"[LOI] Khong mo duoc thiet bi #{device_index} ({device_label})")
        return
    _auto_pick_capture_resolution(cap)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 1 or fps > 120:
        fps = float(TARGET_FPS)
    print(f"[OK] Nguon: {device_label}  (index={device_index})  {actual_w}x{actual_h}  ~{fps:.0f}fps bao cao")

    ok, first = cap.read()
    if not ok or first is None:
        print("[LOI] Khong doc duoc khung hinh dau tien tu thiet bi.")
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
        f"Nguồn mới ({device_label}) có thể có bố cục khác — "
        f"nếu không chắc, bấm Không để chỉnh lại.",
        parent=_root,
    )
    _root.destroy()

    if not _keep:
        calibrate_radar_center(cap, fs_mon, first)

    # ── Mốc tỉ lệ (zoom): thử TỰ ĐỘNG chọn trước (quét trong AUTO_REF_RADIUS_KM
    # quanh tâm, xem auto_pick_reference_region()) — chỉ cần giữ CHUỘT GIỮA
    # kéo chọn tay nếu tự động không tìm được vùng nào đủ đặc trưng (không còn
    # bảng thông báo chặn màn hình — chỉ in trạng thái ra console).
    _auto_ok = auto_pick_reference_region(first)
    if _auto_ok:
        print(f"[MOC-TY-LE] Da tu dong chon 1 moc tham chieu trong "
              f"{AUTO_REF_RADIUS_KM:.0f}km quanh tam radar.")
    else:
        print(f"[MOC-TY-LE] Khong tu dong tim duoc vung nao du dac trung trong "
              f"{AUTO_REF_RADIUS_KM:.0f}km quanh tam — giu CHUOT GIUA keo chon tay.")

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
    static_bg      = StaticBackgroundMask()
    table_img      = build_table(tm, 0)
    table_scroll_y = [0]
    # True = nội dung "Bang thong tin" cần vẽ lại ở khung hình kế tiếp — chỉ
    # đổi khi build_table() chạy (chu kỳ detect) hoặc user cuộn bảng, KHÔNG
    # đổi ở 4/5 khung hình không-detect còn lại (xem tối ưu imshow_bang).
    # Khởi tạo True để khung hình ĐẦU TIÊN vẫn hiện đúng bảng ban đầu.
    _table_dirty   = [True]
    _selected_tid  = [None]
    cv_mouse       = [0, 0]

    _ocr_stop = threading.Event()
    if _HAS_TESSERACT:
        for _wid in range(OCR_WORKER_COUNT):
            threading.Thread(target=_id_ocr_worker,
                              args=(_ocr_stop, tm, _wid, OCR_WORKER_COUNT),
                              daemon=True).start()
        print(f"[OCR] {OCR_WORKER_COUNT} luong doc so hieu (Tesseract) chay nen OK")
    else:
        print("[OCR] Khong co pytesseract — bo qua nhan dien so hieu (pip install pytesseract)")

    _live_output_stop = threading.Event()
    threading.Thread(target=_live_output_worker, args=(_live_output_stop,), daemon=True).start()

    def on_cv_mouse(event, x, y, flags, param):
        # x,y đến từ cửa sổ ĐÃ letterbox (đúng kích thước fs_mon, xem
        # _letterbox_frame() ở vòng lặp chính) — quy đổi ngược về toạ độ
        # frame gốc bằng ĐÚNG phép biến đổi _letterbox_transform() dùng khi
        # vẽ, để tooltip hover so khớp đúng vị trí track (vốn tính bằng toạ
        # độ frame gốc). Rê chuột vào viền đen letterbox: giữ nguyên vị trí
        # hover cũ (không có gì để trỏ tới ở đó).
        scale, new_w, new_h, pad_x, pad_y = _letterbox_transform(
            actual_w, actual_h, fs_mon["width"], fs_mon["height"])
        if pad_x <= x < pad_x + new_w and pad_y <= y < pad_y + new_h:
            cv_mouse[0] = int((x - pad_x) / scale)
            cv_mouse[1] = int((y - pad_y) / scale)

    def on_table_scroll(event, x, y, flags, param):
        if event == cv2.EVENT_MOUSEWHEEL:
            step = TABLE_ROW_H * 3
            if flags > 0: table_scroll_y[0] = max(0, table_scroll_y[0] - step)
            else:          table_scroll_y[0] += step
            _table_dirty[0] = True

    WIN_MAIN = "RadarVRS (USB capture)"
    cv2.namedWindow(WIN_MAIN, cv2.WINDOW_NORMAL)
    cv2.moveWindow(WIN_MAIN, fs_mon["left"], fs_mon["top"])
    cv2.setWindowProperty(WIN_MAIN, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback(WIN_MAIN, on_cv_mouse)

    cv2.namedWindow("Bang thong tin", cv2.WINDOW_AUTOSIZE)
    cv2.moveWindow("Bang thong tin", tbl_mon["left"] + 10, tbl_mon["top"] + 10)
    cv2.setMouseCallback("Bang thong tin", on_table_scroll)

    frame_idx = 0
    FRAME_DT  = 1.0 / fps
    print(f"[OK] Chay {fps:.1f} fps.  Chuot TRAI: phat   Shift+Trai: bam muc tieu   "
          f"Giu+keo Chuot GIUA: dat moc ty le   Delete: xoa muc tieu   "
          f"Shift+Delete: xoa + loai tru vinh vien   "
          f"Chuot PHAI: ID/hen gio   -/=: chinh tay ty le   Q/Esc: thoat\n")

    # ── CHẨN ĐOÁN TẠM THỜI (`[DO-THOI-GIAN]`) — user báo "chưa mượt lắm" sau
    # nhiều vòng tối ưu (throttle StaticBackgroundMask, dedup khác màu, bỏ AA
    # vòng tròn...) đều đo riêng lẻ là rẻ. Lịch sử điều tra sâu trước đây trên
    # ĐÚNG Wyse 5070 ("Kết quả đo thứ 4" trong CLAUDE.md) đã kết luận nghi vấn
    # `waitKey()`/hiển thị là giới hạn DRIVER/GPU thật của máy đó, không phải
    # chỗ tối ưu được từ code Python — nhưng kết luận đó đo TRƯỚC khi có các
    # bổ sung gần đây (vòng tròn, chẩn đoán màu/loại trừ...). Thêm lại đo thời
    # gian TẠM THỜI, dạng TÓM TẮT mỗi ~3 giây (không phải mỗi khung hình, đỡ
    # spam console) để xác nhận: bottleneck còn ở waitKey/hiển thị như trước
    # hay đã dịch sang bước khác (vd ve_canvas, nơi vòng tròn mới nằm trong)
    # — xem cùng nguyên tắc "đo trước khi kết luận" đã áp dụng xuyên suốt file
    # này. Sẽ gỡ lại sau khi xác định xong (giống các lần đo thời gian trước).
    _perf_sum = {"doc_va_xuly": 0.0, "ve_canvas": 0.0, "imshow_chinh": 0.0,
                 "imshow_bang": 0.0, "waitkey": 0.0, "tong": 0.0}
    _perf_max = {"tong": 0.0}
    _perf_n = 0
    _perf_last_report = time.time()
    PERF_REPORT_SEC = 3.0

    # ── CHẨN ĐOÁN TẠM THỜI (`[<MAU>-CHAN-DOAN]`/`[<MAU>-PHEU-LOC]`) — ban đầu
    # chỉ đo GREEN (user báo "thiếu lục") — đã xác định KHÔNG PHẢI
    # detect_blips() thiếu (10-15 blip GREEN/chu kỳ, dư dả), mà bị lọc ở các
    # bước SAU (StaticNoiseFilter/StaticBackgroundMask, đã fix bằng "hạn sử
    # dụng" — xem STATIC_EXPIRE_SEC). User báo TIẾP: MAGENTA cũng "thiếu
    # track/không bắt được" — cùng LOẠI triệu chứng, nhưng CHƯA có số liệu
    # riêng cho MAGENTA để biết có phải CÙNG cơ chế hay không (fix static-
    # expiry vốn ÁP DỤNG CHUNG cho mọi màu, nhưng chưa có bằng chứng trực
    # tiếp xác nhận MAGENTA cũng nghẽn ở ĐÚNG chỗ đó). Tổng quát hoá chẩn
    # đoán để đo CẢ 2 màu cùng lúc thay vì chỉ GREEN — mỗi chu kỳ detect đo
    # qua TỪNG BƯỚC lọc (`_color_diag_stage_counts` + đếm `unmatched` sau mỗi
    # bước), gom + in mỗi PERF_REPORT_SEC giây (cùng nhịp DO-THOI-GIAN, không
    # spam) — biết candidate mất Ở ĐÂU cho ĐÚNG màu đang nghi vấn, không đoán
    # mù dựa trên số liệu của màu KHÁC.
    _DIAG_COLORS = ("GREEN", "MAGENTA")
    _color_diag_sum = {c: {"raw_px": 0, "shape_ok": 0, "after_artifact": 0, "final": 0}
                        for c in _DIAG_COLORS}
    _color_diag_n = {c: 0 for c in _DIAG_COLORS}
    _color_funnel_sum = {c: {"sau_khop_track": 0, "sau_loc_mat_do": 0,
                              "sau_loc_nen_tinh": 0, "sau_loc_nen_px": 0}
                         for c in _DIAG_COLORS}
    _color_funnel_n = {c: 0 for c in _DIAG_COLORS}
    _DIAG_TAG = {"GREEN": "LUC", "MAGENTA": "TIM"}   # nhãn Việt cho tên dòng log

    try:
        while True:
            t0 = time.perf_counter()

            ok, frame = cap.read()
            if not ok or frame is None:
                print("\r[CANH BAO] Mat tin hieu tu thiet bi, dang thu lai...", end="", flush=True)
                time.sleep(0.2)
                continue
            frame_idx += 1
            _latest_frame_for_ocr[0] = frame.copy()

            if frame_idx % DETECT_EVERY == 0:
                # 1 lần HSV + mặt nạ màu thô cho cả chu kỳ detect — dùng
                # chung cho cả 3 hàm dưới đây (xem docstring _compute_color_masks()).
                _masks_cache = _compute_color_masks(frame)
                zoom_changed = update_scale_from_reference(frame, precomputed=_masks_cache)
                if zoom_changed:
                    noise_filter.reset()
                    static_bg.reset()
                    _reset_discovery_snapshot()
                static_bg.update(frame, precomputed=_masks_cache)
                blips = detect_blips(frame, precomputed=_masks_cache)
                for _dc in _DIAG_COLORS:
                    _g_raw_px, _g_shape_ok, _g_after_artifact = _color_diag_stage_counts(
                        _dc, _masks_cache, *frame.shape[:2])
                    _color_diag_sum[_dc]["raw_px"] += _g_raw_px
                    _color_diag_sum[_dc]["shape_ok"] += _g_shape_ok
                    _color_diag_sum[_dc]["after_artifact"] += _g_after_artifact
                    _color_diag_sum[_dc]["final"] += sum(1 for b in blips if b[5] == _dc)
                    _color_diag_n[_dc] += 1
                unmatched = tm.update(frame_idx, blips)
                for _dc in _DIAG_COLORS:
                    _color_funnel_sum[_dc]["sau_khop_track"] += sum(1 for b in unmatched if b[5] == _dc)
                unmatched = filter_dense_candidates(unmatched)
                for _dc in _DIAG_COLORS:
                    _color_funnel_sum[_dc]["sau_loc_mat_do"] += sum(1 for b in unmatched if b[5] == _dc)
                unmatched = noise_filter.filter(unmatched, static_bg=static_bg)
                for _dc in _DIAG_COLORS:
                    _color_funnel_sum[_dc]["sau_loc_nen_tinh"] += sum(1 for b in unmatched if b[5] == _dc)
                unmatched = static_bg.filter(unmatched)
                for _dc in _DIAG_COLORS:
                    _color_funnel_sum[_dc]["sau_loc_nen_px"] += sum(1 for b in unmatched if b[5] == _dc)
                    _color_funnel_n[_dc] += 1
                auto_confirm_nearby(tm, frame_idx, unmatched, static_bg=static_bg, frame=frame)
                table_img = build_table(tm, frame_idx)
                _table_dirty[0] = True
                write_live_outputs(tm, frame_idx, fps)
                print(f"\r  frame={frame_idx}  tracks={len(tm.tracks):3d}  km/px={KM_PX:.4f}", end="", flush=True)

            _id_panel_activate_next(tm)

            # ── Bàn phím: nhập ID mục tiêu mới (bảng _id_panel, hook toàn cục
            # pynput — cửa sổ fullscreen không đáng tin cậy nhận focus cục bộ) ─
            while not _id_panel_key_q.empty():
                _k = _id_panel_key_q.get_nowait()
                if not _id_panel["active"]:
                    continue
                if _k == pkeyboard.Key.backspace:
                    _id_panel_feed_control("backspace", tm)
                elif _k == pkeyboard.Key.enter:
                    _id_panel_feed_control("enter", tm)
                elif _k == pkeyboard.Key.esc:
                    _id_panel_feed_control("esc", tm)
                elif _k == pkeyboard.Key.tab:
                    _id_panel_feed_control("tab", tm)
                elif _k == pkeyboard.Key.left:
                    _id_panel_feed_control("left", tm)
                elif _k == pkeyboard.Key.right:
                    _id_panel_feed_control("right", tm)
                elif _k == pkeyboard.Key.space:
                    _id_panel_feed_char(" ")
                else:
                    _ch = getattr(_k, "char", None)
                    if _ch and 32 <= ord(_ch) <= 126:
                        _id_panel_feed_char(_ch)
                    else:
                        # Chẩn đoán: phím không khớp bất kỳ nhánh nào ở trên
                        # (vd numpad Backspace, phím tổ hợp lạ...) — in ra để
                        # biết chính xác cần thêm nhánh xử lý nào.
                        print(f"\n[ID-PANEL] Phim khong nhan dien duoc: {_k!r}", flush=True)

            # ── Chuột TRÁI: button / Shift+Trái bám mục tiêu / Trái phát track ─
            while not _left_click_q_g.empty():
                sx, sy = _left_click_q_g.get_nowait()
                coords = click_to_frame(sx, sy, fs_mon, frame.shape)
                # Log chẩn đoán "chọn nhầm mục tiêu" sau khi thêm letterbox —
                # user nghi đây là lỗi thuật toán chọn gần nhất chứ không
                # phải toạ độ click sai (ảnh đã hết mờ/méo). In toạ độ RAW
                # (màn hình vật lý) + toạ độ đã quy đổi (frame) NGAY LÚC
                # CLICK, để đối chiếu bằng mắt: nếu (lx,ly) không khớp đúng
                # chỗ user vừa bấm trên màn hình thật → lỗi toạ độ; nếu khớp
                # đúng nhưng track được chọn lại đứng xa hẳn (lx,ly) → lỗi
                # thuật toán chọn.
                print(f"[CLICK-CHAN-DOAN] man_hinh=({sx},{sy}) "
                      f"fs_mon=({fs_mon['left']},{fs_mon['top']},{fs_mon['width']}x{fs_mon['height']}) "
                      f"frame_shape={frame.shape[1]}x{frame.shape[0]} -> frame={coords}", flush=True)
                if coords:
                    lx, ly = coords
                    fw_f = frame.shape[1]
                    if fw_f - _BTN_AUTO_W - 4 <= lx <= fw_f - 4 and 0 <= ly <= _BTN_AUTO_H:
                        cycle_play_button(tm)
                    elif fw_f - 2*_BTN_AUTO_W - 8 <= lx <= fw_f - _BTN_AUTO_W - 8 and 0 <= ly <= _BTN_AUTO_H:
                        toggle_priority_manual_only(tm)
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
                                _nb_info = tm.tracks[nearby]
                                _nb_px = to_px(_nb_info["history"][-1][1], _nb_info["history"][-1][2])
                                print(f"[CLICK-CHAN-DOAN] mau={color} chon={nearby} "
                                      f"vi_tri_track={_nb_px} khoang_cach_toi_click="
                                      f"{np.hypot(lx-_nb_px[0], ly-_nb_px[1]):.1f}px", flush=True)
                            # Shift+Click: ưu tiên mục tiêu vừa chọn — hiện
                            # ngay bảng ID + chu kỳ phát góc trên-trái, khỏi
                            # cần thêm bước chuột phải riêng (xem open_id_panel()).
                            if _selected_tid[0]:
                                open_id_panel(_selected_tid[0], tm)
                    else:
                        hit = find_nearest_blip(lx, ly, tm, frame_idx)
                        if hit:
                            _h_info = tm.tracks[hit]
                            _h_px = to_px(_h_info["history"][-1][1], _h_info["history"][-1][2])
                            print(f"[CLICK-CHAN-DOAN] chon={hit} vi_tri_track={_h_px} "
                                  f"khoang_cach_toi_click={np.hypot(lx-_h_px[0], ly-_h_px[1]):.1f}px", flush=True)
                            speak_target(hit, tm.tracks[hit])
                            _selected_tid[0] = hit

            # ── Chuột PHẢI: mở bảng ID + chu kỳ phát cho mục tiêu dưới trỏ ────
            while not _right_click_q_g.empty():
                sx, sy = _right_click_q_g.get_nowait()
                coords = click_to_frame(sx, sy, fs_mon, frame.shape)
                if coords:
                    lx, ly = coords
                    hit = find_nearest_blip(lx, ly, tm, frame_idx)
                    if hit:
                        open_id_panel(hit, tm)

            # ── Chuột GIỮA (giữ + kéo): đặt/đặt lại mốc tham chiếu tỉ lệ ─────
            if _mid_drag_g["pending_rect"] is not None:
                (sx0, sy0), (sx1, sy1) = _mid_drag_g["pending_rect"]
                _mid_drag_g["pending_rect"] = None
                c0 = click_to_frame(sx0, sy0, fs_mon, frame.shape)
                c1 = click_to_frame(sx1, sy1, fs_mon, frame.shape)
                if c0 and c1:
                    set_reference_region(frame, c0[0], c0[1], c1[0], c1[1])

            # ── Delete: ưu tiên xoá track mà bảng ID đang trỏ tới (nếu bảng
            # đang mở) — user báo cần cách xoá NHANH mục tiêu vừa bắt nhầm
            # ngay lúc thấy trên bảng, không phải track đã chọn từ trước bằng
            # chuột. Không đè lên Backspace (đang dùng để sửa ô nhập chữ số
            # trong bảng) để tránh xung đột — chỉ Delete mới xoá hẳn track.
            while not _delete_key_q.empty():
                _do_exclude = _delete_key_q.get_nowait()
                _tid = _id_panel["tid"] if _id_panel["active"] else _selected_tid[0]
                if _tid and _tid in tm.tracks:
                    _info = tm.tracks[_tid]
                    # Shift+Delete: ĐÁNH DẤU VĨNH VIỄN vị trí này "không phải
                    # mục tiêu" (ghi ra auto_exclude.json, còn mãi qua các
                    # lần chạy sau) TRƯỚC KHI xoá — dùng cho vật cố định trên
                    # bản đồ/giao diện bị "Phát tự động" xác nhận nhầm (dấu
                    # chấm than, mũi biển, đường viền khu vực bám sát...) —
                    # xem docstring `_auto_exclude_zones`. Delete THƯỜNG (không
                    # giữ Shift) vẫn chỉ xoá như cũ, không đánh dấu gì thêm.
                    # Loại trừ áp dụng cho MỌI MÀU tại vị trí đó, và TỰ NỐI với
                    # các điểm loại trừ khác đủ gần thành 1 dải liên tục — đánh
                    # dấu vài điểm rải dọc 1 đường viền là đủ che phủ cả đoạn.
                    if _do_exclude and _info.get("history"):
                        _, _edx, _edy, _, _ = _info["history"][-1]
                        _add_auto_exclude_zone(_info["color"], _edx, _edy)
                        print(f"\n[LOAI-TRU] {_tid} (vi tri, moi mau) — da danh dau VINH VIEN "
                              f"khong nhan dien tai day (luu vao auto_exclude.json, tong "
                              f"{len(_auto_exclude_zones)} diem)", flush=True)
                    stop_auto_speak(_tid)
                    del tm.tracks[_tid]
                    print(f"\n[XOA] {_tid}", flush=True)
                    if _id_panel["active"] and _id_panel["tid"] == _tid:
                        _id_panel["active"] = False
                        _id_panel_activate_next(tm)
                    if _selected_tid[0] == _tid:
                        _selected_tid[0] = None
                    _selected_tid[0] = None

            t_doc_xuly = time.perf_counter()

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

            t_ve = time.perf_counter()

            cv2.imshow(WIN_MAIN, _letterbox_frame(canvas, fs_mon["width"], fs_mon["height"]))

            t_imshow_chinh = time.perf_counter()

            # "Bang thong tin" chỉ THỰC SỰ đổi nội dung khi build_table() vừa
            # chạy (chu kỳ detect) hoặc khi user cuộn bảng (on_table_scroll)
            # — trước đây cv2.imshow() cho cửa sổ này chạy lại MỖI khung hình
            # dù nội dung y hệt lần trước, thuần tuý lãng phí.
            if _table_dirty[0]:
                _max_s = max(0, table_img.shape[0] - TABLE_WIN_H)
                table_scroll_y[0] = min(table_scroll_y[0], _max_s)
                _view = table_img[table_scroll_y[0] : table_scroll_y[0] + TABLE_WIN_H]
                if _view.shape[0] < TABLE_WIN_H:
                    _pad  = np.zeros((TABLE_WIN_H - _view.shape[0], TABLE_W, 3), np.uint8)
                    _view = np.vstack([_view, _pad])
                cv2.imshow("Bang thong tin", _view)
                _table_dirty[0] = False

            t_imshow_bang = time.perf_counter()

            key = cv2.waitKey(1) & 0xFF
            if not _id_panel["active"]:
                if key in (ord('q'), 27):
                    break
                elif key == ord('-'):
                    nudge_km_px(REF_MANUAL_STEP)      # muc tieu ve GAN tam hon
                elif key == ord('='):
                    nudge_km_px(1.0 / REF_MANUAL_STEP)  # muc tieu ve XA tam hon

            elapsed = time.perf_counter() - t0

            # CHẨN ĐOÁN TẠM THỜI — xem khối comment "[DO-THOI-GIAN]" trước
            # vòng lặp. Gom trung bình + đỉnh (max) mỗi PERF_REPORT_SEC giây
            # THẬT (không phải mỗi N khung hình — đúng nguyên tắc throttle
            # theo thời gian thật đã rút ra nhiều lần trong file này).
            t_waitkey = time.perf_counter()
            _perf_sum["doc_va_xuly"]  += t_doc_xuly - t0
            _perf_sum["ve_canvas"]    += t_ve - t_doc_xuly
            _perf_sum["imshow_chinh"] += t_imshow_chinh - t_ve
            _perf_sum["imshow_bang"]  += t_imshow_bang - t_imshow_chinh
            _perf_sum["waitkey"]      += t_waitkey - t_imshow_bang
            _perf_sum["tong"]         += elapsed
            _perf_max["tong"] = max(_perf_max["tong"], elapsed)
            _perf_n += 1
            _now_perf = time.time()
            if _now_perf - _perf_last_report >= PERF_REPORT_SEC and _perf_n > 0:
                print(f"\n[DO-THOI-GIAN] {_perf_n} khung/{_now_perf - _perf_last_report:.1f}s "
                      f"tracks={len(tm.tracks)} ocr_lan_doc={_ocr_calls_since_report[0]} — "
                      f"TB: doc_xuly={_perf_sum['doc_va_xuly']/_perf_n*1000:.1f}ms "
                      f"ve_canvas={_perf_sum['ve_canvas']/_perf_n*1000:.1f}ms "
                      f"imshow_chinh={_perf_sum['imshow_chinh']/_perf_n*1000:.1f}ms "
                      f"imshow_bang={_perf_sum['imshow_bang']/_perf_n*1000:.1f}ms "
                      f"waitkey={_perf_sum['waitkey']/_perf_n*1000:.1f}ms "
                      f"TONG={_perf_sum['tong']/_perf_n*1000:.1f}ms  dinh_TONG={_perf_max['tong']*1000:.1f}ms",
                      flush=True)
                for k in _perf_sum:
                    _perf_sum[k] = 0.0
                _perf_max["tong"] = 0.0
                _perf_n = 0
                _perf_last_report = _now_perf
                _ocr_calls_since_report[0] = 0
                for _dc in _DIAG_COLORS:
                    _tag = _DIAG_TAG[_dc]
                    if _color_diag_n[_dc] > 0:
                        _n = _color_diag_n[_dc]
                        _s = _color_diag_sum[_dc]
                        print(f"[{_tag}-CHAN-DOAN] {_n} chu ky detect — {_dc} trung binh/chu ky: "
                              f"pixel_tho={_s['raw_px']/_n:.0f} "
                              f"blob_hinh_dang_ok={_s['shape_ok']/_n:.2f} "
                              f"sau_loc_artifact={_s['after_artifact']/_n:.2f} "
                              f"blip_cuoi_cung={_s['final']/_n:.2f}",
                              flush=True)
                        for k in _s:
                            _s[k] = 0
                        _color_diag_n[_dc] = 0
                    if _color_funnel_n[_dc] > 0:
                        _n = _color_funnel_n[_dc]
                        _s = _color_funnel_sum[_dc]
                        print(f"[{_tag}-PHEU-LOC] {_n} chu ky detect — {_dc} con lai "
                              f"trung binh/chu ky sau TUNG BUOC: "
                              f"sau_khop_track={_s['sau_khop_track']/_n:.2f} "
                              f"sau_loc_mat_do={_s['sau_loc_mat_do']/_n:.2f} "
                              f"sau_loc_nen_tinh={_s['sau_loc_nen_tinh']/_n:.2f} "
                              f"sau_loc_nen_px={_s['sau_loc_nen_px']/_n:.2f}",
                              flush=True)
                        for k in _s:
                            _s[k] = 0
                        _color_funnel_n[_dc] = 0

            if elapsed < FRAME_DT:
                time.sleep(FRAME_DT - elapsed)

    except KeyboardInterrupt:
        pass
    finally:
        _stop_all_audio_now()      # tắt ngay âm thanh đang phát khi thoát (ESC/Q)
        m_listener.stop()
        k_listener.stop()
        _ocr_stop.set()
        _live_output_event.set()   # cho luồng ghi nền cơ hội xả nốt lần cuối
        _live_output_stop.set()
        cap.release()
        _global_auto_stop.set()
        _global_auto_slow_stop.set()
        stop_auto_speak()
        cv2.destroyAllWindows()
        _audio_queue.put(None)
        print(f"\n[OK] Xong. Tổng tracks: {len(tm.tracks)}")

        out = {}
        for tid, info in tm.tracks.items():
            out[tid] = {"color": info["color"], "display_color": _track_display(info)[0], "history": [
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
        calibrate_radar_center(cap, mon, first, loop_video=True)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    # ── Mốc tỉ lệ (zoom): thử TỰ ĐỘNG chọn trước (quét trong AUTO_REF_RADIUS_KM
    # quanh tâm, xem auto_pick_reference_region()) — chỉ cần giữ CHUỘT GIỮA
    # kéo chọn tay nếu tự động không tìm được vùng nào đủ đặc trưng (không còn
    # bảng thông báo chặn màn hình — chỉ in trạng thái ra console).
    _auto_ok = auto_pick_reference_region(first)
    if _auto_ok:
        print(f"[MOC-TY-LE] Da tu dong chon 1 moc tham chieu trong "
              f"{AUTO_REF_RADIUS_KM:.0f}km quanh tam radar.")
    else:
        print(f"[MOC-TY-LE] Khong tu dong tim duoc vung nao du dac trung trong "
              f"{AUTO_REF_RADIUS_KM:.0f}km quanh tam — giu CHUOT GIUA keo chon tay.")

    # Audio
    try:
        pygame.mixer.init()
        print("[AUDIO] OK")
    except Exception as e:
        print(f"[AUDIO] Lỗi: {e}")
    threading.Thread(target=_audio_worker, daemon=True).start()

    # pynput — dung cho phim Delete + Shift+Delete (loai tru vinh vien). Truoc
    # day chi dang ky on_press ("chi con dung cho phim Delete") — nhung
    # Shift+Delete can biet trang thai Shift qua _shift_state, ma bien nay
    # CHI duoc RESET ve False boi on_release (xem _on_key_release()) — thieu
    # on_release se khien _shift_state["held"] "dinh" True vinh vien sau lan
    # bam Shift DAU TIEN trong che do video (video mode truoc day khong can
    # bien nay vi tu doc flag rieng cua cv2 cho Shift+Click). Them on_release
    # de Shift+Delete hoat dong dung trong CA 2 che do.
    k_listener = pkeyboard.Listener(on_press=_on_key_press, on_release=_on_key_release)
    k_listener.start()
    print("[INPUT] Keyboard listener OK (Delete/Shift+Delete)")

    tm             = TrackManager(fps)
    noise_filter   = StaticNoiseFilter()
    static_bg      = StaticBackgroundMask()
    table_img      = build_table(tm, 0)
    table_scroll_y = [0]
    _selected_tid  = [None]
    cv_mouse       = [0, 0]

    _ocr_stop = threading.Event()
    if _HAS_TESSERACT:
        for _wid in range(OCR_WORKER_COUNT):
            threading.Thread(target=_id_ocr_worker,
                              args=(_ocr_stop, tm, _wid, OCR_WORKER_COUNT),
                              daemon=True).start()
        print(f"[OCR] {OCR_WORKER_COUNT} luong doc so hieu (Tesseract) chay nen OK")
    else:
        print("[OCR] Khong co pytesseract — bo qua nhan dien so hieu (pip install pytesseract)")

    _live_output_stop = threading.Event()
    threading.Thread(target=_live_output_worker, args=(_live_output_stop,), daemon=True).start()

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

    WIN_MAIN = "RadarVRS (video)"
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
          f"Shift+Delete: xoa + loai tru vinh vien   "
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
                # 1 lần HSV + mặt nạ màu thô cho cả chu kỳ detect — dùng
                # chung cho cả 3 hàm dưới đây (xem docstring _compute_color_masks()).
                _masks_cache = _compute_color_masks(frame)
                zoom_changed = update_scale_from_reference(frame, precomputed=_masks_cache)
                if zoom_changed:
                    noise_filter.reset()
                    static_bg.reset()
                    _reset_discovery_snapshot()
                static_bg.update(frame, precomputed=_masks_cache)
                blips = detect_blips(frame, precomputed=_masks_cache)
                unmatched = tm.update(frame_idx, blips)
                unmatched = filter_dense_candidates(unmatched)
                unmatched = noise_filter.filter(unmatched, static_bg=static_bg)
                unmatched = static_bg.filter(unmatched)
                auto_confirm_nearby(tm, frame_idx, unmatched, static_bg=static_bg, frame=frame)
                table_img = build_table(tm, frame_idx)
                write_live_outputs(tm, frame_idx, fps)
                print(f"\r  frame={frame_idx}/{total_frames}  t={frame_idx/fps:6.1f}s  "
                      f"tracks={len(tm.tracks):3d}  km/px={KM_PX:.4f}", end="", flush=True)

            _id_panel_activate_next(tm)
            # Chế độ phát file dùng cv2.waitKey cục bộ (cửa sổ có focus thật)
            # để gõ ID — xả rỗng hàng đợi phím toàn cục pynput (chỉ dùng ở chế
            # độ capture) mỗi khung để tránh phình bộ nhớ qua 1 phiên chạy dài.
            while not _id_panel_key_q.empty():
                _id_panel_key_q.get_nowait()

            # ── Chuột TRÁI: button / Shift+Trái bám mục tiêu / Trái phát track ─
            while not _left_click_q.empty():
                lx, ly, shift_held = _left_click_q.get_nowait()
                fw_f = frame.shape[1]
                if fw_f - _BTN_AUTO_W - 4 <= lx <= fw_f - 4 and 0 <= ly <= _BTN_AUTO_H:
                    cycle_play_button(tm)
                elif fw_f - 2*_BTN_AUTO_W - 8 <= lx <= fw_f - _BTN_AUTO_W - 8 and 0 <= ly <= _BTN_AUTO_H:
                    toggle_priority_manual_only(tm)
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
                        # Shift+Click: ưu tiên mục tiêu vừa chọn — hiện ngay
                        # bảng ID + chu kỳ phát góc trên-trái, khỏi cần thêm
                        # bước chuột phải riêng (xem open_id_panel()).
                        if _selected_tid[0]:
                            open_id_panel(_selected_tid[0], tm)
                else:
                    hit = find_nearest_blip(lx, ly, tm, frame_idx)
                    if hit:
                        speak_target(hit, tm.tracks[hit])
                        _selected_tid[0] = hit

            # ── Chuột PHẢI: mở bảng ID + chu kỳ phát cho mục tiêu dưới trỏ ────
            while not _right_click_q.empty():
                lx, ly = _right_click_q.get_nowait()
                hit = find_nearest_blip(lx, ly, tm, frame_idx)
                if hit:
                    open_id_panel(hit, tm)

            # ── Chuột GIỮA (giữ + kéo): đặt/đặt lại mốc tham chiếu tỉ lệ ─────
            if _mid_drag["pending_rect"] is not None:
                (rx0, ry0), (rx1, ry1) = _mid_drag["pending_rect"]
                _mid_drag["pending_rect"] = None
                set_reference_region(frame, rx0, ry0, rx1, ry1)

            # ── Delete: ưu tiên xoá track mà bảng ID đang trỏ tới (nếu bảng
            # đang mở) — user báo cần cách xoá NHANH mục tiêu vừa bắt nhầm
            # ngay lúc thấy trên bảng, không phải track đã chọn từ trước bằng
            # chuột. Không đè lên Backspace (đang dùng để sửa ô nhập chữ số
            # trong bảng) để tránh xung đột — chỉ Delete mới xoá hẳn track.
            while not _delete_key_q.empty():
                _do_exclude = _delete_key_q.get_nowait()
                _tid = _id_panel["tid"] if _id_panel["active"] else _selected_tid[0]
                if _tid and _tid in tm.tracks:
                    _info = tm.tracks[_tid]
                    # Shift+Delete: ĐÁNH DẤU VĨNH VIỄN vị trí này "không phải
                    # mục tiêu" (ghi ra auto_exclude.json, còn mãi qua các
                    # lần chạy sau) TRƯỚC KHI xoá — dùng cho vật cố định trên
                    # bản đồ/giao diện bị "Phát tự động" xác nhận nhầm (dấu
                    # chấm than, mũi biển, đường viền khu vực bám sát...) —
                    # xem docstring `_auto_exclude_zones`. Delete THƯỜNG (không
                    # giữ Shift) vẫn chỉ xoá như cũ, không đánh dấu gì thêm.
                    # Loại trừ áp dụng cho MỌI MÀU tại vị trí đó, và TỰ NỐI với
                    # các điểm loại trừ khác đủ gần thành 1 dải liên tục — đánh
                    # dấu vài điểm rải dọc 1 đường viền là đủ che phủ cả đoạn.
                    if _do_exclude and _info.get("history"):
                        _, _edx, _edy, _, _ = _info["history"][-1]
                        _add_auto_exclude_zone(_info["color"], _edx, _edy)
                        print(f"\n[LOAI-TRU] {_tid} (vi tri, moi mau) — da danh dau VINH VIEN "
                              f"khong nhan dien tai day (luu vao auto_exclude.json, tong "
                              f"{len(_auto_exclude_zones)} diem)", flush=True)
                    stop_auto_speak(_tid)
                    del tm.tracks[_tid]
                    print(f"\n[XOA] {_tid}", flush=True)
                    if _id_panel["active"] and _id_panel["tid"] == _tid:
                        _id_panel["active"] = False
                        _id_panel_activate_next(tm)
                    if _selected_tid[0] == _tid:
                        _selected_tid[0] = None
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
            if _id_panel["active"]:
                # Backspace: 8 (BS chuẩn) hoặc 127 (DEL — 1 số layout/backend
                # trả về mã này thay vì 8) — chấp nhận cả 2 vì chưa có cách
                # kiểm chứng trực tiếp mã thật trên máy operator.
                if key in (8, 127):
                    _id_panel_feed_control("backspace", tm)
                elif key in (13, 10):
                    _id_panel_feed_control("enter", tm)
                elif key == 27:
                    _id_panel_feed_control("esc", tm)
                elif key == 9:
                    _id_panel_feed_control("tab", tm)
                elif key == 81:
                    _id_panel_feed_control("left", tm)
                elif key == 83:
                    _id_panel_feed_control("right", tm)
                elif 32 <= key <= 126:
                    _id_panel_feed_char(chr(key))
                elif key != 255:
                    # Chẩn đoán: phím không khớp bất kỳ nhánh nào ở trên —
                    # in ra mã thật để biết chính xác cần thêm nhánh xử lý
                    # nào (vd nếu Backspace ở đây thật ra trả về 1 mã khác).
                    print(f"\n[ID-PANEL] Phim khong nhan dien duoc: key={key}", flush=True)
            elif key in (ord('q'), 27):
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
        _stop_all_audio_now()      # tắt ngay âm thanh đang phát khi thoát (ESC/Q)
        k_listener.stop()
        _ocr_stop.set()
        _live_output_event.set()   # cho luồng ghi nền cơ hội xả nốt lần cuối
        _live_output_stop.set()
        cap.release()
        _global_auto_stop.set()
        _global_auto_slow_stop.set()
        stop_auto_speak()
        cv2.destroyAllWindows()
        _audio_queue.put(None)
        print(f"\n[OK] Xong. Tổng tracks: {len(tm.tracks)}")

        out = {}
        for tid, info in tm.tracks.items():
            out[tid] = {"color": info["color"], "display_color": _track_display(info)[0], "history": [
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
    print("=== RadarVRS (khong tu bat bang ID cho auto-scan) ===\n")

    # Truyen duong dan file video qua tham so dong lenh de phat lai file (vd
    # de test lai voi phong_to.mp4) — mac dinh KHONG co tham so: dò và chạy
    # thẳng từ thiết bị video capture (USB/HDMI, vd capture card "USB_Video"),
    # lấy NGUYÊN khung hình gốc như radar_live_2.py.
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
        if not os.path.exists(video_path):
            print(f"[LOI] Khong tim thay file video: {video_path}")
            return
        run_radar_from_video(video_path)
        return

    print("[SCAN] Dang do thiet bi video capture (HDMI/USB)...", flush=True)
    devices = list_video_capture_devices()
    if not devices:
        print("[LOI] Khong tim thay thiet bi video capture nao "
              "(kiem tra day USB_Video da cam vao chua, hoac thu lai sau vai giay).")
        return
    print(f"[SCAN] Tim thay {len(devices)} thiet bi:")
    for d in devices:
        print(f"    #{d['index']}: {d['name']}  ({d['res']})")

    choice = show_video_device_dialog(devices)
    if choice is None:
        print("[HUY] Nguoi dung thoat.")
        return
    run_radar_from_capture(choice["index"], choice["name"])

if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        # Giữ cửa sổ console mở lại để đọc thông báo/lỗi khi chạy .exe đóng
        # gói (double-click) — cửa sổ console vốn tự đóng ngay khi script
        # kết thúc, kể cả khi main() return sớm do lỗi (không tìm thấy
        # thiết bị capture...) chứ không chỉ khi crash. Bỏ qua khi chạy
        # không tương tác (vd gọi từ script khác).
        try:
            if sys.stdin and sys.stdin.isatty():
                input("\nNhan Enter de dong cua so...")
        except Exception:
            pass
