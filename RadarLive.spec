# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['radar_live_4.py'],
    pathex=[],
    binaries=[],
    # easyocr/torch đã bị THAY BẰNG Tesseract OCR (nhẹ hơn nhiều cho CPU yếu
    # — xem CLAUDE.md, mục "thay EasyOCR bằng Tesseract") — không còn import
    # easyocr/torch trong code nên không cần 'easyocr_models' hay hook nữa;
    # 'tesseract_bin' (tesseract.exe + DLL cần thiết + tessdata/eng.traineddata,
    # đã rút gọn bỏ công cụ training/docs không cần lúc chạy) thay thế.
    datas=[('speak', 'speak'), ('tesseract_bin', 'tesseract_bin')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RadarLive',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='.',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RadarLive',
)
