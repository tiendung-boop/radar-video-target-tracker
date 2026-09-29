# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['radar_live_6.py'],
    pathex=[],
    binaries=[],
    # Giong RadarLive.spec (v4): Tesseract OCR (nhe hon EasyOCR/torch cho CPU
    # yeu — xem CLAUDE.md) qua 'tesseract_bin', khong can hook easyocr.
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
    name='RadarVRS',
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
    name='RadarVRS',
)
