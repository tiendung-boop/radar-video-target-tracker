"""
Cong cu dat tam radar va moc 300km thu cong.
- Click trai: dat TAM RADAR
- Click phai: dat moc vong 300km (keo den vong ngoai cung)
- Mui ten WASD: di chuyen tam +/-1px
- +/-: tang/giam ban kinh 300km
- S: luu va thoat
- Q: thoat khong luu
"""
import cv2
import numpy as np

VIDEO_PATH = r"c:\Users\ygost\radar\thucte.mp4"

cx, cy   = 772, 522   # tam radar da can chinh
r_300km  = 484        # ban kinh vong 300km (pixel)

# Che do hien tai: 0 = dang chinh tam, 1 = dang chinh ban kinh
mode = 0

def draw(frame, cx, cy, r_300km, mode):
    img = frame.copy()
    h, w = img.shape[:2]

    # Vong 300km
    cv2.circle(img, (cx, cy), r_300km, (0, 180, 255), 2)

    # Nhan moc 300km (goc tren phai cua vong)
    lx = cx + int(r_300km * 0.707)
    ly = cy - int(r_300km * 0.707)
    cv2.putText(img, "300km", (lx + 4, ly - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 180, 255), 2)

    # Crosshair tam
    cv2.line(img, (0, cy), (w, cy), (0, 255, 255), 1)
    cv2.line(img, (cx, 0), (cx, h), (0, 255, 255), 1)
    cv2.circle(img, (cx, cy), 6,  (0, 255, 255), -1)
    cv2.circle(img, (cx, cy), 14, (0, 255, 255), 2)

    # Thong tin tren
    mode_str = "[CHINH TAM]" if mode == 0 else "[CHINH BAN KINH 300km]"
    col_mode = (0, 255, 255) if mode == 0 else (0, 180, 255)
    km_px = 300.0 / r_300km
    label = f"TAM: CX={cx} CY={cy}   R_300KM={r_300km}px  ({km_px:.4f} km/px)   {mode_str}"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    cv2.rectangle(img, (6, 6), (14 + tw, 16 + th), (0, 0, 0), -1)
    cv2.putText(img, label, (10, 10 + th),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, col_mode, 1)

    # Huong dan phia duoi
    g1 = "[Click T] dat tam   [Click P] dat moc 300km   [Tab] doi che do"
    g2 = "[WASD/Mui ten] tinh chinh tam   [+/-] ban kinh 300km   [S] Luu   [Q] Thoat"
    cv2.rectangle(img, (6, h - 42), (w - 6, h - 4), (0, 0, 0), -1)
    cv2.putText(img, g1, (10, h - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)
    cv2.putText(img, g2, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)

    return img


def on_mouse(event, x, y, flags, param):
    global cx, cy, r_300km, mode
    if event == cv2.EVENT_LBUTTONDOWN:
        # Click trai: dat tam
        cx, cy = x, y
        mode = 0
    elif event == cv2.EVENT_RBUTTONDOWN:
        # Click phai: dat ban kinh = khoang cach tu tam den diem click
        r_300km = max(10, int(np.sqrt((x - cx)**2 + (y - cy)**2)))
        mode = 1


cap = cv2.VideoCapture(VIDEO_PATH)
cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
ret, frame = cap.read()
cap.release()

if not ret:
    print("Khong doc duoc video!")
    exit(1)

WIN = "Dat Tam Radar"
cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
cv2.resizeWindow(WIN, frame.shape[1], frame.shape[0])
cv2.setMouseCallback(WIN, on_mouse)

print(f"Gia tri hien tai: CX={cx}, CY={cy}, R_300KM={r_300km}")

saved = False
while True:
    cv2.imshow(WIN, draw(frame, cx, cy, r_300km, mode))
    key = cv2.waitKey(30) & 0xFF

    if key == ord('q') or key == 27:
        break
    elif key == ord('s') or key == ord('S'):
        saved = True
        break
    elif key == 9:                        # Tab: doi che do
        mode = 1 - mode
    # Di chuyen tam
    elif key == 82 or key == ord('w'):
        cy -= 1
    elif key == 84 or key == ord('x'):
        cy += 1
    elif key == 81 or key == ord('a'):
        cx -= 1
    elif key == 83 or key == ord('d'):
        cx += 1
    # Ban kinh 300km
    elif key in (ord('+'), ord('=')):
        r_300km += 1
    elif key == ord('-'):
        r_300km = max(10, r_300km - 1)

cv2.destroyAllWindows()

if saved:
    km_px = 300.0 / r_300km
    print(f"\n=== KET QUA ===")
    print(f"CX, CY   = {cx}, {cy}")
    print(f"R_300KM  = {r_300km}   # {km_px:.4f} km/px")
    print(f"\nCopy vao radar_tracker.py:")
    print(f"CX, CY   = {cx}, {cy}")
    print(f"R_300KM  = {r_300km}          # ban kinh pixel cua vong 300km")
    print(f"KM_PX    = 300.0 / R_300KM   # {km_px:.4f} km/px")
else:
    print("Thoat khong luu.")
