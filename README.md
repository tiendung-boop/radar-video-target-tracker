# RadarVRS: Real-time Target Tracking from Radar Display Video

A Windows desktop app that **watches the video output of a radar / ATC display**, captured by an HDMI/USB capture card, streamed over LAN, or played back from a file. It **detects and tracks the targets on screen**, computes each target's **bearing and range**, reads target IDs with **OCR**, and **announces them by voice**. It needs no API or data feed from the source radar software. Everything comes from the pixels.

## Features

- **Blip detection**: HSV colour segmentation plus morphological filtering (`MORPH_OPEN` to drop 1-px noise, then dilate) on each frame.
- **Multi-target tracking**: global nearest-pair association, which matches same-colour tracks first and uses gating on a constant-velocity *predicted* position. A noise blip therefore can't "steal" a locked track, which was a bug in the earlier greedy matcher, reproduced and then fixed.
- **Polar conversion**: pixel → (bearing °, range km) around a calibrated radar centre.
- **Zoom-robust scale**: when the operator changes the display range (e.g. 360 km → 90 km), the km/px scale is re-estimated automatically by **feature matching (ORB/AKAZE)** on a reference region. Earlier versions used multi-scale template matching.
- **OCR of target IDs** with Tesseract in v6. Earlier versions used EasyOCR.
- **Voice announcements**: pre-recorded Vietnamese number/phrase clips (`speak/`), per-target repeat interval, slow/fast modes, and a "priority" mode that announces only operator-selected targets.
- **Keeps working in the background**: global mouse/keyboard hooks (`pynput`) and capture in worker threads mean processing continues when the window loses focus.
- **Multiple video sources**: capture card (DirectShow device picker), LAN MJPEG/RTSP stream, or video file playback with pause/speed control.
- **LAN screen sender** (`radar_screen_lan_server.py`) streams a monitor as MJPEG-over-HTTP, so the analysis can run on a second machine.
- **Live outputs**: `live_tracks.json` / `live_tracks.html` for other tools to consume.
- **Configurable ID rules**: a separate GUI (`radar_id_color_config.py`) maps the ID prefix to a display colour and ID ranges to target categories.
- **Packaged for operators** with PyInstaller (`*.spec`), as a single folder that runs without Python installed.

## Project evolution

| File | Stage |
|---|---|
| `radar_tracker.py`, `radar_tracker_v2.py`, `radar_tracker_screen.py` | First prototypes: blip detection, OCR, 30 s trajectory prediction, annotated video export |
| `radar_live.py`, `radar_live_capture.py` | Live mode from a capture card, TTS, target table |
| `radar_live_2.py` | Robust track association (global nearest-pair, colour priority, predicted gating) |
| `radar_live_3.py` | Video-file source plus handling of display zoom with template matching |
| `radar_live_4.py` | Zoom scale via ORB/AKAZE feature matching, wall-clock timing, performance work |
| `radar_live_5.py` | LAN video source (pairs with `radar_screen_lan_server.py`) |
| **`radar_live_6.py`** | **Current release (RadarVRS)**: auto-scan, priority mode, operator-driven ID panel |
| `set_tam_radar.py` | Tool for calibrating the radar centre and 300 km ring by hand |
| `radar_simulation*.html` | Browser-based radar simulation used for testing |

## Getting started

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python radar_live_6.py                 # choose the source in the start-up dialog
python radar_screen_lan_server.py      # on the source machine, to stream its screen over LAN
```

- **Tesseract**: install Tesseract-OCR, or put a portable copy (`tesseract.exe` + `tessdata/`) in `tesseract_bin/` next to the script or exe.
- **Build the operator package**: `python -m PyInstaller RadarVRS.spec --noconfirm` → `dist/RadarVRS/RadarVRS.exe`.

Operator controls (mouse, keyboard, the *Play* / *Priority* buttons) are described in [`Huong_dan.txt`](Huong_dan.txt), in Vietnamese.

> Sample videos, trained models and build output are not included in the repository because of their size.

## Tech stack

Python 3.12, OpenCV (contrib), NumPy, Tesseract, EasyOCR / PyTorch (earlier versions), pygame, Tkinter, mss, pynput, pywin32, edge-tts, PyInstaller
