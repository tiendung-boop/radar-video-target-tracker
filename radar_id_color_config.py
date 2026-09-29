"""RadarIDColorConfig — cong cu cau hinh rieng, dat CANH RadarVRS.exe (ten
ung dung dong goi tu `radar_live_6.py`, spec `RadarVRS.spec`).

Cho phep operator tu chinh 2 quy tac ma RadarVRS (`radar_live_6.py`) doc luc
khoi dong (`_load_id_color_rules()`) va ap dung MOI KHI operator tu tay sua
ID qua bang xac nhan trong ung dung chinh (Shift+Click/chuot phai -> go ID ->
Enter):

1. "Chu so DAU cua ID -> mau hien thi" — vd ID bat dau bang "0" -> hien thi
   nhu muc tieu LUC (GREEN), bat dau "6" -> DO (RED), bat dau "8" -> TIM
   (MAGENTA). Day la META-DATA HIEN THI (vong tron, tooltip, bang, JSON/HTML)
   — KHONG BAO GIO doi mau THAT dung de nhan dien/bam theo pixel (HSV) cua
   track, vi thuat toan bam blip trong radar_live_6.py CAN mau that de khop
   dung pixel tren video — chi doi CACH HIEN THI cho operator sau khi ho da
   tu tay xac nhan dung ID that.
2. "Khoang ID -> loai muc tieu" — vd ID 025-029 la "Qua canh khu vuc A" — chi
   la nhan mo ta hien thi (tooltip/bang), khong anh huong logic nao khac.

File cau hinh: `id_color_rules.json`, dat CUNG THU MUC voi chinh file .exe
nay (hoac file .py nay khi chay tu source) — dung `_base_dir()` giong het
quy uoc `_BASE_DIR`/`calibration.json`/`auto_exclude.json` da co san trong
`radar_live_6.py`. RadarVRS CHI doc file nay 1 LAN LUC KHOI DONG (giong
calibration.json) — sua xong phai khoi dong lai RadarVRS.exe de ap dung,
KHONG tu dong nap lai giua chung.

Dat file .py nay + `RadarIDColorConfig.spec` canh nhau trong thu muc project
goc; build bang `python -m PyInstaller RadarIDColorConfig.spec --noconfirm`
se ra dung 1 file `dist/RadarIDColorConfig.exe` (onefile, khong can thu muc
_internal rieng) — sau do copy thu cong vao `dist/RadarVRS/` de nam CANH
`RadarVRS.exe`, dung y "ung dung trong folder RadarVRS" nguoi dung yeu cau.
"""
import sys
import os
import json
import traceback

import tkinter as tk
from tkinter import ttk, messagebox

COLORS = ["RED", "GREEN", "MAGENTA", "YELLOW", "CYAN"]


def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(_base_dir(), "id_color_rules.json")

DEFAULT_CONFIG = {
    "digit_color": {"0": "GREEN", "6": "RED", "8": "MAGENTA"},
    "id_ranges": [],
}


def load_config():
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            digit_color = data.get("digit_color", {})
            id_ranges = data.get("id_ranges", [])
            if isinstance(digit_color, dict) and isinstance(id_ranges, list):
                return {"digit_color": dict(digit_color), "id_ranges": list(id_ranges)}
        except Exception:
            pass
    return {"digit_color": dict(DEFAULT_CONFIG["digit_color"]), "id_ranges": []}


class DigitColorRow(ttk.Frame):
    def __init__(self, master, digit="", color="RED", on_remove=None):
        super().__init__(master)
        self.on_remove = on_remove
        self.digit_var = tk.StringVar(value=digit)
        self.color_var = tk.StringVar(value=color if color in COLORS else COLORS[0])
        ttk.Label(self, text="Chu so dau:").pack(side="left", padx=(0, 4))
        vcmd = (self.register(self._validate_digit), "%P")
        ttk.Entry(self, textvariable=self.digit_var, width=3,
                  validate="key", validatecommand=vcmd).pack(side="left")
        ttk.Label(self, text=" -> Mau:").pack(side="left", padx=(8, 4))
        ttk.Combobox(self, textvariable=self.color_var, values=COLORS,
                     width=10, state="readonly").pack(side="left")
        ttk.Button(self, text="Xoa", command=self._remove).pack(side="left", padx=(10, 0))

    @staticmethod
    def _validate_digit(proposed):
        return proposed == "" or (proposed.isdigit() and len(proposed) <= 1)

    def _remove(self):
        self.destroy()
        if self.on_remove:
            self.on_remove(self)

    def read(self):
        return self.digit_var.get().strip(), self.color_var.get().strip()


class RangeRow(ttk.Frame):
    def __init__(self, master, id_min="", id_max="", label="", on_remove=None):
        super().__init__(master)
        self.on_remove = on_remove
        self.min_var = tk.StringVar(value=str(id_min))
        self.max_var = tk.StringVar(value=str(id_max))
        self.label_var = tk.StringVar(value=label)
        ttk.Label(self, text="Tu ID:").pack(side="left")
        ttk.Entry(self, textvariable=self.min_var, width=7).pack(side="left", padx=(2, 6))
        ttk.Label(self, text="den ID:").pack(side="left")
        ttk.Entry(self, textvariable=self.max_var, width=7).pack(side="left", padx=(2, 6))
        ttk.Label(self, text="la muc tieu:").pack(side="left")
        ttk.Entry(self, textvariable=self.label_var, width=22).pack(side="left", padx=(2, 6))
        ttk.Button(self, text="Xoa", command=self._remove).pack(side="left", padx=(10, 0))

    def _remove(self):
        self.destroy()
        if self.on_remove:
            self.on_remove(self)


class App:
    def __init__(self, root):
        self.root = root
        root.title("Cau hinh Mau <-> So hieu (ID) — RadarVRS")
        root.geometry("640x580")

        cfg = load_config()

        intro = ttk.Label(
            root,
            text="Ap dung MOI KHI ban tu tay sua ID qua bang xac nhan trong RadarVRS\n"
                 "(khong doi cach nhan dien mau THAT tren video — chi doi cach HIEN THI).\n"
                 "Sua xong bam Luu roi KHOI DONG LAI RadarVRS.exe de ap dung.",
            justify="left", foreground="#555555")
        intro.pack(fill="x", padx=10, pady=(10, 0))

        f1 = ttk.LabelFrame(root, text="1) Chu so DAU cua ID -> mau hien thi")
        f1.pack(fill="x", padx=10, pady=(10, 4))
        self.digit_rows_container = ttk.Frame(f1)
        self.digit_rows_container.pack(fill="x")
        self.digit_rows = []
        for d, c in cfg["digit_color"].items():
            self._add_digit_row(d, c)
        ttk.Button(f1, text="+ Them dong", command=lambda: self._add_digit_row()).pack(anchor="w", pady=4)

        f2 = ttk.LabelFrame(root, text="2) Khoang ID -> loai muc tieu (chi de hien thi tooltip/bang)")
        f2.pack(fill="both", expand=True, padx=10, pady=4)
        canvas = tk.Canvas(f2, highlightthickness=0)
        scrollbar = ttk.Scrollbar(f2, orient="vertical", command=canvas.yview)
        self.range_rows_container = ttk.Frame(canvas)
        self.range_rows_container.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.range_rows_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.range_rows = []
        for r in cfg["id_ranges"]:
            self._add_range_row(r.get("min", ""), r.get("max", ""), r.get("label", ""))
        ttk.Button(f2, text="+ Them dong", command=lambda: self._add_range_row()).pack(anchor="w", pady=4)

        bottom = ttk.Frame(root)
        bottom.pack(fill="x", padx=10, pady=10)
        ttk.Button(bottom, text="Luu", command=self.save).pack(side="left")
        ttk.Label(bottom, text=f"File: {CONFIG_PATH}", foreground="#777777").pack(side="left", padx=12)

    def _add_digit_row(self, digit="", color="RED"):
        row = DigitColorRow(self.digit_rows_container, digit, color, on_remove=self._remove_digit_row)
        row.pack(fill="x", pady=2)
        self.digit_rows.append(row)

    def _remove_digit_row(self, row):
        if row in self.digit_rows:
            self.digit_rows.remove(row)

    def _add_range_row(self, id_min="", id_max="", label=""):
        row = RangeRow(self.range_rows_container, id_min, id_max, label, on_remove=self._remove_range_row)
        row.pack(fill="x", pady=2)
        self.range_rows.append(row)

    def _remove_range_row(self, row):
        if row in self.range_rows:
            self.range_rows.remove(row)

    def save(self):
        digit_color = {}
        for row in self.digit_rows:
            d, c = row.read()
            if not d:
                continue
            if not d.isdigit() or len(d) != 1:
                messagebox.showerror("Loi", f"'{d}' phai la dung 1 chu so (0-9)")
                return
            if c not in COLORS:
                messagebox.showerror("Loi", f"Mau '{c}' khong hop le")
                return
            digit_color[d] = c

        id_ranges = []
        for row in self.range_rows:
            mn, mx, lbl = row.min_var.get().strip(), row.max_var.get().strip(), row.label_var.get().strip()
            if not mn and not mx and not lbl:
                continue
            try:
                mn_i, mx_i = int(mn), int(mx)
            except ValueError:
                messagebox.showerror("Loi", f"Khoang ID '{mn}'-'{mx}' phai la so nguyen")
                return
            if mn_i > mx_i:
                messagebox.showerror("Loi", f"'Tu ID' ({mn_i}) phai <= 'den ID' ({mx_i})")
                return
            id_ranges.append({"min": mn_i, "max": mx_i, "label": lbl})

        data = {"digit_color": digit_color, "id_ranges": id_ranges}
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Loi", f"Khong ghi duoc file:\n{e}")
            return
        messagebox.showinfo(
            "Da luu",
            "Da luu cau hinh.\n\nKHOI DONG LAI RadarVRS.exe de ap dung "
            "(file chi duoc doc 1 lan luc khoi dong, giong calibration.json).")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


def _pause_before_exit():
    try:
        if sys.stdin is not None and sys.stdin.isatty():
            input("\nNhan Enter de dong cua so...")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        _pause_before_exit()
