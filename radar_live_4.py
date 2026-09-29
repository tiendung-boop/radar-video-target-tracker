"""
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
        _delete_key_q.put(True)
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

# True  = "tự do quét" — lúc bật CHƯA có mục tiêu nào được chọn thủ công
#         (Shift+trái) → tự động dò + đọc mọi blip trong 150km.
# False = "chỉ mục tiêu đã chọn" — lúc bật ĐÃ có ít nhất 1 mục tiêu chọn thủ công.
_auto_scan_mode = False

def _start_auto_session(tm):
    global _auto_scan_mode
    _auto_scan_mode = not any(not info.get("auto", False) for info in tm.tracks.values())
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
            info = tm_ref.tracks.get(tid)
            if not info:
                continue
            # BUG đã sửa RỒI SAU ĐÓ ĐẢO LẠI theo yêu cầu user: trước đây track
            # auto-scan mới phát hiện bị ĐỌC NGAY ("thiếu ID vì OCR chưa kịp
            # đọc"), sau đó sửa thành PHẢI đợi Enter xác nhận qua bảng ID mới
            # đọc ("phải nhấn số ID rồi mới đọc chứ"). User yêu cầu quay lại:
            # "không còn cần bước xác nhận ban đầu nữa, cứ đọc thôi" — bỏ hẳn
            # việc GÁC đọc chờ Enter, đọc NGAY như thiết kế gốc. Bảng ID VẪN
            # được đẩy vào hàng đợi (`_id_panel_queue`, đúng 1 lần nhờ
            # `queued_for_panel`) để operator vẫn có thể xem/sửa ID/chu kỳ
            # bất cứ lúc nào (giữ nguyên nút ENTER xác nhận trong bảng) — chỉ
            # khác là việc đọc KHÔNG còn phụ thuộc vào việc đã bấm Enter đó
            # hay chưa.
            if info.get("auto") and not info.get("queued_for_panel") and not info.get("reviewed", True):
                info["queued_for_panel"] = True
                _id_panel_queue.put(tid)
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

def _reset_discovery_snapshot():
    """Gọi khi zoom đổi (cùng lúc với noise_filter.reset()/static_bg.reset())
    — toạ độ pixel của ảnh chụp cũ hết ý nghĩa sau khi tỉ lệ km/px đổi, so
    sánh xuyên qua 1 lần zoom sẽ coi MỌI thứ (kể cả nền tĩnh) là "đã dịch
    chuyển". Đặt `_discovery_last_time = now` (không phải 0) để delay đúng 1
    khoảng AUTO_DISCOVERY_INTERVAL_SEC trước khi ảnh chụp đầu tiên SAU zoom
    được lấy lại. Đặt `_discovery_primed = False` — xem docstring hằng số
    ngay trên — để vòng khám phá ĐẦU TIÊN sau zoom đó chỉ populate ảnh chụp
    (không xác nhận gì), tránh xác nhận mù."""
    global _discovery_last_time, _discovery_prev_snapshot, _discovery_primed
    _discovery_last_time = time.time()
    _discovery_prev_snapshot = {}
    _discovery_primed = False

def auto_confirm_nearby(tm, frame_idx, unmatched_blips, static_bg=None):
    """So ảnh chụp candidate hiện tại (trong bán kính GLOBAL_RADIUS) với ảnh
    chụp từ AUTO_DISCOVERY_INTERVAL_SEC giây trước — khi "Phát tự động"/chậm
    đang bật VÀ đang ở chế độ tự-do-quét, xác nhận (tạo track, auto=True)
    các candidate MỚI xuất hiện hoặc đã dịch chuyển kể từ lần trước. `unmatched_blips`
    đã được StaticNoiseFilter/StaticBackgroundMask lọc bỏ phần lớn nền tĩnh
    trước khi tới đây — xem docstring đầu file.

    ẢNH CHỤP NỀN LUÔN CHẠY, không phụ thuộc "Phát tự động" đang bật hay tắt
    (xem khối docstring lịch sử ngay trên, mục "vòng đầu tiên xác nhận mù").

    Tham số `static_bg`: chỉ gác cổng phần XÁC NHẬN (không gác phần duy trì
    ảnh chụp nền) — nếu `static_bg.n_updates < STATIC_BG_WARMUP_UPDATES`,
    không tạo track mới ở vòng này (xem lịch sử AUTO_DISCOVERY_INTERVAL_SEC
    vs STATIC_BG_WARMUP_UPDATES lệch pha trong CLAUDE.md).

    `_discovery_primed`: gác cổng XÁC NHẬN thêm 1 lớp nữa — `was_primed`
    đọc giá trị NGAY TRƯỚC KHI đặt lại `True` cho vòng này, nên vòng ĐẦU
    TIÊN sau mỗi lần `_reset_discovery_snapshot()` (zoom đổi) chỉ populate
    ảnh chụp (không xác nhận gì, dù static_bg đã sẵn sàng) — vòng KẾ TIẾP
    mới thực sự so sánh + xác nhận. Tránh xác nhận mù ngay sau zoom (xem
    docstring hằng số `_discovery_primed` phía trên)."""
    global _discovery_last_time, _discovery_prev_snapshot, _discovery_primed
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
        and (static_bg is None or static_bg.n_updates >= STATIC_BG_WARMUP_UPDATES)
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
        _new_confirmed = 0
        for bx, by, area, dist, bear, color, dx, dy in candidates:
            _seen_by_color[color] = _seen_by_color.get(color, 0) + 1
        for blip in candidates:
            bx, by, area, dist, bear, color, dx, dy = blip
            moved_or_new = True
            for (px, py) in prev.get(color, []):
                if abs(bx - px) < AUTO_DISCOVERY_STATIC_TOL_PX and abs(by - py) < AUTO_DISCOVERY_STATIC_TOL_PX:
                    moved_or_new = False
                    break
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
            for info in tm.tracks.values():
                if info["color"] != color or not info["history"]:
                    continue
                _, edx, edy, _, _ = info["history"][-1]
                epx, epy = to_px(edx, edy)
                if np.hypot(bx - epx, by - epy) < SHIFT_CLICK_SKIP_RADIUS:
                    too_close_to_existing = True
                    break
            if too_close_to_existing:
                _skip_close += 1
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
                print(f"[AUTO-CONFIRM-CHAN-DOAN] {color} @ px({bx},{by}) "
                      f"static_bg.n_updates={static_bg.n_updates} peak_ema={_peak_txt} "
                      f"(nguong={STATIC_BG_THRESHOLD})", flush=True)
            tm.confirm_candidate(frame_idx, bx, by, color, dx, dy, auto=True)

        print(f"[AUTO-SCAN-TONG-HOP] candidate_theo_mau={_seen_by_color} "
              f"xac_nhan_moi={_new_confirmed} bo_qua_dung_yen={_skip_unmoved} "
              f"bo_qua_da_co_track_gan={_skip_close}", flush=True)

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
    phát)."""
    if tid in tm.tracks:
        _id_panel_queue.put(tid)

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
STATIC_BG_WINDOW_UPDATES  = 300   # ~40-70s tuỳ nhịp detect thật (DETECT_EVERY
                                   # frame/lần) — số lần cập nhật để 1 pixel
                                   # TĨNH TUYỆT ĐỐI (luôn "on") đạt đúng
                                   # STATIC_BG_THRESHOLD, xem công thức alpha
                                   # ngay dưới.
STATIC_BG_THRESHOLD       = 0.9   # ngưỡng EMA coi là "nền tĩnh" (đã quét
                                   # 0.90/0.95/0.98 trên dữ liệu thật — không
                                   # đổi kết quả, chọn 0.90 rộng rãi nhất)
# BUG đã sửa (tự phát hiện khi kiểm chứng lại trên đúng khung hình "CYAN lẫn
# bờ biển" — xem CLAUDE.md): công thức alpha=1/WINDOW cũ SAI toán học — với
# EMA `ema = ema*(1-alpha) + moi*alpha`, 1 pixel TĨNH TUYỆT ĐỐI (luôn "on")
# chỉ đạt `ema = 1-(1-alpha)^N` sau N lần cập nhật — với alpha=1/300, sau
# ĐÚNG 300 lần cập nhật chỉ đạt ~0.632, và cần tới ~690 lần mới chạm 0.9, KHÔNG
# PHẢI 300 như tưởng ban đầu. Hậu quả đo được: pixel bờ biển THẬT (xác nhận
# qua đo trực tiếp: EMA đúng bằng peak lý thuyết 1-(1-1/300)^334≈0.672 sau
# 334 lần cập nhật — khớp CHÍNH XÁC dự đoán toán học, tức pixel này "on" ở
# GẦN NHƯ MỌI khung hình) vẫn KHÔNG BAO GIỜ bị lọc vì EMA chưa kịp leo tới
# 0.9 — bộ lọc hoàn toàn không tác dụng dù dữ liệu tích luỹ đúng. Fix: giải
# ngược alpha từ đúng số lần cập nhật MONG MUỐN (`STATIC_BG_WINDOW_UPDATES`)
# để 1 pixel tĩnh tuyệt đối vừa chạm ngưỡng sau đúng ngần ấy lần cập nhật.
STATIC_BG_EMA_ALPHA = 1.0 - (1.0 - STATIC_BG_THRESHOLD) ** (1.0 / STATIC_BG_WINDOW_UPDATES)
STATIC_BG_WARMUP_UPDATES  = STATIC_BG_WINDOW_UPDATES  # < ngưỡng này: EMA
                                   # chưa đủ "chín" (mới reset/mới khởi động,
                                   # còn thiên lệch bởi vài mẫu đầu) — KHÔNG
                                   # lọc gì cả, để an toàn (thà bỏ sót nhiễu
                                   # còn hơn lỡ loại nhầm mục tiêu thật khi dữ
                                   # liệu tích luỹ chưa đủ).
STATIC_BG_MATCH_RADIUS    = 3     # px — dò quanh centroid candidate (không
                                   # chỉ đúng 1 điểm) vì centroid sau dilate/
                                   # lọc hình dạng của detect_blips() có thể
                                   # lệch vài px so với mask màu thô gốc.

class StaticBackgroundMask:
    def __init__(self):
        self.ema = {}       # color_name -> np.float32 (h,w), None nếu chưa có
        self.n_updates = 0

    def reset(self):
        self.ema = {}
        self.n_updates = 0
        print("\n[LOC-NEN-PX] Reset mask nen tinh theo pixel (ty le km/px vua doi do zoom)",
              flush=True)

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
            self.ema[color_name] = cv2.accumulateWeighted(m, prev, STATIC_BG_EMA_ALPHA)
        self.n_updates += 1

    def is_static(self, color, x, y):
        if self.n_updates < STATIC_BG_WARMUP_UPDATES:
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

    def filter(self, unmatched_blips):
        if self.n_updates < STATIC_BG_WARMUP_UPDATES:
            return unmatched_blips
        return [b for b in unmatched_blips if not self.is_static(b[5], b[0], b[1])]

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
    best = min(groups, key=lambda g: sum(v*v for v in
               (grp_center(g)[0]-local_cx, grp_center(g)[1]-local_cy)))
    xs = [c[0] for c in best] + [c[0]+c[2] for c in best]
    ys = [c[1] for c in best] + [c[1]+c[3] for c in best]
    return (x0s+min(xs), y0s+min(ys), x0s+max(xs), y0s+max(ys))

# Cấu hình Tesseract: PSM 7 = coi cả vùng cắt là ĐÚNG 1 DÒNG chữ (khớp đúng
# bản chất 1 nhãn số hiệu — luôn nằm gọn 1 dòng, không xuống dòng) — khác
# EasyOCR (tự phát hiện NHIỀU mảnh chữ rồi phải tự chọn mảnh gần tâm nhất,
# xem lịch sử bug "nối nhầm nhiều dòng" đã sửa trước đây), Tesseract ở chế
# độ PSM 7 tự coi cả ảnh là 1 chuỗi nên không cần bước lọc-theo-khoảng-cách
# nữa. Whitelist chỉ chữ số — nhãn số hiệu không có chữ cái.
OCR_TESSERACT_CONFIG = "--psm 7 -c tessedit_char_whitelist=0123456789"

def _make_ocr_reader():
    """Tesseract chạy qua `tesseract.exe` như 1 tiến trình HĐH riêng mỗi lần
    gọi (`pytesseract`) — không có state/model cần giữ lại giữa các lần đọc
    như `easyocr.Reader` trước đây, nên không có gì để "tạo" ở đây. Giữ lại
    hàm này (trả về giá trị bất kỳ khác None) chỉ để KHÔNG phải sửa lại chữ
    ký gọi hàm ở `_id_ocr_worker()`/mọi nơi khác đang gọi `_make_ocr_reader()`
    rồi truyền kết quả vào `_ocr_read_bbox(..., reader=...)`."""
    return True

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
    try:
        text = pytesseract.image_to_string(big, config=OCR_TESSERACT_CONFIG).strip()
    except Exception:
        return None
    return text if text else None

OCR_MAX_ATTEMPTS = 8    # số lần đọc tối đa trước khi CHỐT TẠM theo đa số
                        # phiếu hiện có (dù chưa đạt OCR_VOTE_CONFIRM) — nếu
                        # không, 1 track có phiếu rải rác đều (không lần nào
                        # trùng đủ OCR_VOTE_CONFIRM) sẽ bị đọc MÃI MÃI không
                        # bao giờ chốt, tốn tài nguyên vô ích và không bao
                        # giờ hiển thị ID dù đã đọc rất nhiều lần.
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
# Tối ưu thêm cho MÁY YẾU HƠN (ít core): 2 = số luồng đo được TỐI ƯU riêng
# cho 1 máy 8 core cụ thể — trên máy ít core hơn, mỗi luồng EasyOCR vẫn tự
# dùng torch với NHIỀU luồng nội bộ mặc định (xấp xỉ theo số core máy), nên
# 2 luồng OCR chạy song song có thể chiếm gần hết CPU của máy YẾU, làm giật/
# lag cả vòng lặp chính (detect/vẽ/tracking) — đúng thứ "máy nhẹ hơn cần chạy
# mượt" mà không liên quan gì tới độ chính xác nhận diện. Hạ về 1 luồng trên
# máy có ít hơn 6 core: OCR hội tụ ID chậm hơn đôi chút, nhưng không còn 2
# luồng tranh CPU với vòng lặp chính — đánh đổi hợp lý cho máy yếu.
_CPU_COUNT = os.cpu_count() or 4
OCR_WORKER_COUNT = 2 if _CPU_COUNT >= 6 else 1

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
        pending = [(tid, info) for tid, info in list(tm_ref.tracks.items())
                   if tid not in _ocr_confirmed and abs(hash(tid)) % worker_count == worker_id]
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
                text = _ocr_read_bbox(frame, bbox, reader=reader)
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
                    # kết quả. CHỈ áp dụng khi chữ số đầu đọc được KHÔNG PHẢI
                    # là 1 trong CÁC chữ số quy định (0/6/8) của BẤT KỲ màu
                    # nào — nếu nó ĐÃ là 1 trong 3 số đó (chỉ khác màu hiện
                    # tại), rất có thể đây không phải lỗi đọc số mà là lỗi
                    # PHÂN LOẠI MÀU (RED/MAGENTA vẫn còn nhầm lẫn nhẹ — xem
                    # CLAUDE.md) — ép theo màu lúc đó sẽ biến 1 lần đọc ĐÚNG
                    # thành SAI (đã bắt được ca thật: 1 icon đọc đúng "884"
                    # nhưng bị phân loại nhầm RED, ép thành "684" sai). An
                    # toàn hơn: chỉ sửa khi chữ số đầu rõ ràng KHÔNG hợp lệ ở
                    # BẤT KỲ màu nào (vd đọc ra "1", "9"...) — lúc đó chắc
                    # chắn là lỗi OCR, không phải lỗi màu.
                    expected0 = COLOR_ID_PREFIX.get(info["color"])
                    if expected0 is not None and text[0] not in COLOR_ID_PREFIX.values():
                        text = expected0 + text[1:]
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
        # đoán còn "tươi", đủ tin cậy). Vòng 2 (khác màu, hẹp hơn) + vòng 3
        # (cùng màu, RỘNG HƠN HẲN — bắt bước NHẢY VỊ TRÍ RỜI RẠC thật, xem
        # docstring trên ASSOC_DIST_WIDE) chỉ kích hoạt khi track đã trượt ≥1
        # chu kỳ (dự đoán "đóng băng", kém tin cậy hơn) — cả 2 đều qua
        # `_filter_ambiguous_pairs()` TRƯỚC khi gộp vào all_pairs: loại các
        # cặp có ứng viên khác cạnh tranh cùng blip/track ở khoảng cách gần
        # tương đương (xem docstring trên ROUND_AMBIG_MARGIN_PX) — thà track
        # "đứng hình" 1 chu kỳ còn hơn đoán nhầm sang mục tiêu khác trong khi
        # vẫn hiện đúng ID cũ.
        pairs2 = _filter_ambiguous_pairs(gen_pairs(False, ASSOC_DIST * 0.5, require_slipped=True))
        pairs3 = _filter_ambiguous_pairs(gen_pairs(True, ASSOC_DIST_WIDE, require_slipped=True))
        all_pairs = ([(d, bi, tid, 1) for d, bi, tid in gen_pairs(True, ASSOC_DIST)]
                     + [(d, bi, tid, 2) for d, bi, tid in pairs2]
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
    color  = COLOR_MAP.get(info["color"], UNKNOWN_COL)

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
    loai  = _LOAI_VN.get(info["color"], info["color"]).upper()
    title = loai + (f"  (+{pending} chờ)" if pending else "")
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

        # Lịch sử vòng khoanh màu quanh mục tiêu (đã bỏ HẲN, qua nhiều lần
        # chỉnh theo phản hồi user): ban đầu MỌI track bị khoanh tròn+dấu
        # cộng NGAY LẬP TỨC → chỉ khoanh khi đã "duyệt" hoặc đang được bảng
        # ID trỏ tới → tách dấu cộng khỏi vòng tròn khi CHƯA xác nhận (che
        # mất icon) → bỏ vòng tròn khi ĐÃ xác nhận (rối mắt, icon+đuôi vệt
        # bay+mũi tên dự đoán đã đủ) → user yêu cầu TIẾP: bỏ nốt cả trong lúc
        # ĐANG chờ xác nhận — không còn vẽ vòng tròn màu quanh mục tiêu ở
        # BẤT KỲ trạng thái nào nữa. Vị trí candidate đang chờ vẫn xác định
        # được qua đường nối + vòng tròn NÂU riêng của chính bảng ID
        # (`_draw_id_panel()`, ID_PANEL_LINE_COLOR) — không trùng với vòng
        # tròn MÀU TRACK đã bỏ ở đây.

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
        lt[tid] = {"color": info["color"],
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
# bên thay vì kéo giãn méo) — trước đây cv2.WINDOW_FULLSCREEN tự kéo giãn
# ảnh lấp đầy màn hình KHÔNG GIỮ TỈ LỆ, nếu màn hình xuất (vd 1280x1024,
# 5:4) khác tỉ lệ nguồn capture (vd 1920x1080, 16:9) thì ảnh bị MÉO — xem
# lịch sử đầy đủ trong CLAUDE.md (mục "letterbox"). Lần đầu áp dụng, user
# báo "chọn nhầm nhiều" — đã HUỶ tạm 1 lần, nhưng user xác nhận muốn GIỮ
# letterbox (ảnh không mờ/méo mới đúng) và nghi phần khớp/chọn mục tiêu
# (không phải toạ độ click) mới là nguyên nhân thật — áp dụng LẠI letterbox,
# kèm log chẩn đoán ở điểm xử lý click để xác định đúng nguyên nhân (toạ độ
# click sai hay thuật toán chọn gần nhất sai) thay vì đoán tiếp lần 2.
# `_letterbox_transform()` là nguồn DUY NHẤT tính tỉ lệ/offset — dùng CHUNG
# cho cả `_letterbox_frame()` (vẽ) và `click_to_frame()` (ánh xạ click
# ngược) để không bao giờ lệch nhau.
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

# Tối ưu: bản đầu tiên cấp phát MỘT canvas đen MỚI (np.zeros, ~vài MB tuỳ độ
# phân giải màn hình) + MỘT mảng resize riêng MỖI KHUNG HÌNH (mọi khung hình
# hiển thị, không chỉ chu kỳ detect — tần suất cao nhất trong toàn bộ vòng
# lặp chính) — thuần lãng phí trên CPU yếu vì viền đen letterbox KHÔNG BAO
# GIỜ đổi giữa các khung hình cùng phiên (chỉ phụ thuộc kích thước nguồn +
# kích thước màn hình xuất, cả 2 đều cố định sau khi mở thiết bị). Giữ lại 1
# canvas DÙNG CHUNG qua các lần gọi (viền đen chỉ tô 1 LẦN lúc kích thước đổi
# — hiếm, chỉ khi đổi độ phân giải capture hoặc màn hình xuất), mỗi khung chỉ
# `cv2.resize(..., dst=...)` ghi THẲNG vào đúng vùng ảnh bên trong canvas đó
# — không cấp phát gì thêm. An toàn vì nơi gọi DUY NHẤT (`cv2.imshow(...)`)
# không giữ lại tham chiếu nào tới canvas cho lần gọi sau.
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

    WIN_MAIN = "Radar Live v4 (USB capture)"
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
          f"Chuot PHAI: ID/hen gio   -/=: chinh tay ty le   Q/Esc: thoat\n")

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
                unmatched = tm.update(frame_idx, blips)
                unmatched = filter_dense_candidates(unmatched)
                unmatched = noise_filter.filter(unmatched)
                unmatched = static_bg.filter(unmatched)
                auto_confirm_nearby(tm, frame_idx, unmatched, static_bg=static_bg)
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
                _delete_key_q.get_nowait()
                _tid = _id_panel["tid"] if _id_panel["active"] else _selected_tid[0]
                if _tid and _tid in tm.tracks:
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
            drag_preview = None
            if _mid_drag_g["active"] and _mid_drag_g["p0"] is not None:
                c0 = click_to_frame(_mid_drag_g["p0"][0], _mid_drag_g["p0"][1], fs_mon, frame.shape)
                c1 = click_to_frame(_mid_drag_g["p1"][0], _mid_drag_g["p1"][1], fs_mon, frame.shape)
                if c0 and c1:
                    drag_preview = (c0, c1)
            draw_frame(canvas, frame_idx, tm, cv_mouse[0], cv_mouse[1],
                       source_label=device_label, paused=False, drag_rect=drag_preview)

            cv2.imshow(WIN_MAIN, _letterbox_frame(canvas, fs_mon["width"], fs_mon["height"]))

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

            key = cv2.waitKey(1) & 0xFF
            if not _id_panel["active"]:
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

    # pynput — chi con dung cho phim Delete
    k_listener = pkeyboard.Listener(on_press=_on_key_press)
    k_listener.start()
    print("[INPUT] Keyboard listener OK (Delete)")

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

    WIN_MAIN = "Radar Live v4 (video)"
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
                unmatched = noise_filter.filter(unmatched)
                unmatched = static_bg.filter(unmatched)
                auto_confirm_nearby(tm, frame_idx, unmatched, static_bg=static_bg)
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
                _delete_key_q.get_nowait()
                _tid = _id_panel["tid"] if _id_panel["active"] else _selected_tid[0]
                if _tid and _tid in tm.tracks:
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
    print("=== RADAR LIVE v4 (zoom + moc ORB/AKAZE) ===\n")

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
