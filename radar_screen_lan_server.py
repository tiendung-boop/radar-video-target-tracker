"""
radar_screen_lan_server.py — máy NGUỒN cho radar_live_5.py.

Chạy trên máy đang mở phần mềm ATC (màn hình "đang làm việc"). Chụp lại
NGUYÊN TRẠNG màn hình đó (không crop/scale — đúng nguyên tắc mọi nguồn khác
trong project: capture card v2-v4, LAN v5 đều "lấy nguyên trạng dữ liệu màn
hình nguồn") và phát lên mạng LAN dưới dạng luồng MJPEG-qua-HTTP tại
http://<ip>:<port>/video — đúng định dạng mà radar_live_5.py mong đợi
(`_open_lan_capture()` mở bằng `cv2.VideoCapture(url, cv2.CAP_FFMPEG)`, có
fallback backend mặc định nếu FFMPEG không mở được URL đó).

Vì sao MJPEG-over-HTTP chứ không phải RTSP thật: dựng 1 RTSP server đúng
nghĩa cần phần mềm ngoài project (GStreamer / mediamtx / live555, chưa có
sẵn trong .venv). MJPEG-over-HTTP (định dạng mjpg-streamer/IP-camera đời cũ:
mỗi khung hình là 1 phần multipart/x-mixed-replace, ngăn nhau bằng
boundary) là chuẩn lâu đời mà chính FFmpeg (backend `cv2.CAP_FFMPEG` đang
dùng ở phía nhận) đọc được thẳng qua giao thức http:// tiêu chuẩn, không
cần cài thêm gói nào ngoài mss/opencv/numpy — cả 3 đã có sẵn trong project
(radar_live_5.py đã import mss/cv2/numpy). Nếu sau này cần RTSP thật (vd để
nhiều client cùng xem hiệu quả hơn), chỉ cần thay lớp phát ở FILE NÀY —
phía radar_live_5.py không cần đổi gì (chỉ đổi URL http:// → rtsp://).

Cách dùng — máy NGUỒN (nơi có phần mềm ATC đang mở):
    python radar_screen_lan_server.py                  # man hinh chinh (mss monitor 1), cong 8080
    python radar_screen_lan_server.py --monitor 2       # man hinh thu 2, neu phan mem ATC o do
    python radar_screen_lan_server.py --port 8090 --fps 15 --quality 80
    python radar_screen_lan_server.py --region 0,0,1920,1080   # chi 1 vung cu the thay vi ca man hinh

Rồi ở máy PHÂN TÍCH (chạy radar_live_5.py), dán đúng URL mà script này in ra
console lúc khởi động:
    python radar_live_5.py http://<IP_may_nguon>:8080/video
(hoặc nhập vào dialog khi chạy `python radar_live_5.py` không tham số).

Có thể mở thử URL gốc (không phải /video) bằng trình duyệt bất kỳ trên cùng
mạng LAN để xem trực tiếp — hữu ích để kiểm tra nhanh trước khi cắm vào
radar_live_5.py.
"""

import argparse
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import mss
import numpy as np

BOUNDARY = "radarframe"


class FrameBuffer:
    """Khung hình JPEG mới nhất, dùng chung giữa thread chụp màn hình và
    (nhiều) thread HTTP client — khoá bằng lock vì có thể nhiều client xem
    cùng lúc (trình duyệt để kiểm tra + radar_live_5.py cùng 1 lúc)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._jpeg = None
        self._frame_no = 0

    def update(self, jpeg_bytes):
        with self._lock:
            self._jpeg = jpeg_bytes
            self._frame_no += 1

    def get(self):
        with self._lock:
            return self._jpeg, self._frame_no


def _lan_ip_addresses():
    """Đoán các địa chỉ IP LAN của máy này để in gợi ý URL — không đảm bảo
    đúng 100% (máy nhiều card mạng), chỉ để tiện copy chứ không phải nguồn
    chân lý duy nhất."""
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # khong gui goi tin that, chi de OS chon interface
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)


def _capture_loop(buf, monitor, region, fps, quality, stop_evt):
    """Chạy trong 1 thread riêng — mss KHÔNG an toàn khi dùng chung 1
    instance giữa nhiều thread, nên tạo instance mss.mss() ngay trong chính
    thread này (khác thread chính và các thread HTTP client)."""
    interval = 1.0 / max(fps, 1e-3)
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]

    with mss.MSS() as sct:
        if region is not None:
            left, top, width, height = region
            grab_area = {"left": left, "top": top, "width": width, "height": height}
        else:
            mons = sct.monitors
            idx = monitor if 0 <= monitor < len(mons) else 1
            grab_area = mons[idx]
        print(f"[CAPTURE] Vung chup: {grab_area}")

        next_t = time.time()
        while not stop_evt.is_set():
            try:
                shot = sct.grab(grab_area)
                frame = np.array(shot)[:, :, :3]  # BGRA -> BGR
                ok, enc = cv2.imencode(".jpg", frame, encode_params)
                if ok:
                    buf.update(enc.tobytes())
            except Exception as exc:
                print(f"[CAPTURE] Loi chup man hinh: {exc}")
                time.sleep(0.5)

            next_t += interval
            delay = next_t - time.time()
            if delay > 0:
                time.sleep(delay)
            else:
                next_t = time.time()  # da tut lai qua xa, khong co gang bat kip


def _make_handler(buf, fps, path):
    frame_interval = 1.0 / max(fps, 1e-3)
    stream_path = "/" + path.strip("/")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # im lang — mac dinh se spam 1 dong/request, o day la nhieu dong/giay

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._serve_index()
            elif self.path.rstrip("/") == stream_path:
                self._serve_stream()
            elif self.path in ("/snapshot.jpg", "/snapshot"):
                self._serve_snapshot()
            else:
                self.send_error(404)

        def _serve_index(self):
            body = (
                "<html><body style='background:#111;margin:0'>"
                f"<img src='{stream_path}' style='width:100%;height:auto;display:block'>"
                "</body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_snapshot(self):
            jpeg, _ = buf.get()
            if jpeg is None:
                self.send_error(503, "Chua co khung hinh nao")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(jpeg)))
            self.end_headers()
            self.wfile.write(jpeg)

        def _serve_stream(self):
            self.send_response(200)
            self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Pragma", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()

            last_frame_no = -1
            try:
                while True:
                    jpeg, frame_no = buf.get()
                    if jpeg is not None and frame_no != last_frame_no:
                        last_frame_no = frame_no
                        self.wfile.write(f"--{BOUNDARY}\r\n".encode("ascii"))
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii"))
                        self.wfile.write(jpeg)
                        self.wfile.write(b"\r\n")
                    time.sleep(frame_interval)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # client (radar_live_5.py hoac trinh duyet) dong ket noi — binh thuong

    return Handler


def _parse_region(text):
    parts = [int(p) for p in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("can dung dinh dang left,top,width,height")
    return tuple(parts)


def main():
    ap = argparse.ArgumentParser(
        description="Phat man hinh dang lam viec len mang LAN (nguon cho radar_live_5.py).",
    )
    ap.add_argument("--monitor", type=int, default=1,
                     help="Chi so man hinh mss (1=man hinh chinh, 2=man hinh thu 2...). Mac dinh: 1.")
    ap.add_argument("--region", type=_parse_region, default=None,
                     help="Chup 1 vung cu the thay vi ca man hinh: left,top,width,height")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--path", type=str, default="/video", help="Duong dan luong MJPEG. Mac dinh: /video")
    ap.add_argument("--fps", type=float, default=15.0)
    ap.add_argument("--quality", type=int, default=80,
                     help="Chat luong JPEG 1-100 (mac dinh 80 — can bang bang thong/chat luong).")
    args = ap.parse_args()

    buf = FrameBuffer()
    stop_evt = threading.Event()
    cap_thread = threading.Thread(
        target=_capture_loop,
        args=(buf, args.monitor, args.region, args.fps, args.quality, stop_evt),
        daemon=True,
    )
    cap_thread.start()

    # Doi khung hinh dau tien de bao loi som neu --monitor/--region sai, thay
    # vi de HTTP server chay "thanh cong" nhung khong bao gio co frame nao.
    t0 = time.time()
    while buf.get()[0] is None and time.time() - t0 < 5:
        time.sleep(0.1)
    if buf.get()[0] is None:
        print("[LOI] Khong chup duoc khung hinh nao sau 5s — kiem tra lai --monitor/--region.")
        stop_evt.set()
        return 1

    try:
        server = ThreadingHTTPServer(("0.0.0.0", args.port), _make_handler(buf, args.fps, args.path))
    except OSError as exc:
        print(f"[LOI] Khong mo duoc cong {args.port}: {exc}")
        print("      (co the da co 1 phien radar_screen_lan_server.py khac dang chay, "
              "hoac cong dang bi chuong trinh khac dung — thu --port khac.)")
        stop_evt.set()
        return 1

    stream_path = "/" + args.path.strip("/")

    ips = _lan_ip_addresses() or ["<IP_may_nay>"]
    print("=" * 70)
    print("[OK] Dang phat man hinh len LAN. Dan 1 trong cac URL sau vao radar_live_5.py:")
    for ip in ips:
        print(f"     http://{ip}:{args.port}{stream_path}")
    print(f"[XEM THU] Mo trinh duyet tren cung mang LAN: http://{ips[0]}:{args.port}/")
    print("[DUNG] Ctrl+C de dung (hoac dong cua so nay).")
    print("=" * 70)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[DUNG] Dang tat server...")
    finally:
        stop_evt.set()
        server.shutdown()
        cap_thread.join(timeout=2)
    return 0


def _pause_before_exit():
    """Khi build thanh .exe roi chay bang double-click, cua so console se
    dong ngay lap tuc sau khi script ket thuc — nguoi dung khong kip doc
    thong bao loi. Dung lai cho toi khi bam Enter, nhung CHI KHI dang chay
    tuong tac that (isatty) de khong treo cac lan chay tu dong/test."""
    try:
        if sys.stdin is not None and sys.stdin.isatty():
            input("\nNhan Enter de dong cua so...")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        _exit_code = main()
    except Exception:
        import traceback
        traceback.print_exc()
        _exit_code = 1
    if _exit_code:
        _pause_before_exit()
    sys.exit(_exit_code or 0)
