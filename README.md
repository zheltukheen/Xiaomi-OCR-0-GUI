# Xiaomi OCR GUI

A standalone desktop application (Python + PySide6) for OCR of PDFs, images
and documents, powered by the **Xiaomi-OCR-0** model (`SeerRay-Lab/Xiaomi-OCR-0`,
the same model showcased in [xiaomi-research/Xiaomi-OCR-0](https://huggingface.co/spaces/xiaomi-research/Xiaomi-OCR-0)).

The Hugging Face Space is a static showcase page with no live API, so this app
runs the actual model **locally and fully offline**: weights (≈1.5 GB, Apache-2.0)
are downloaded once from the official repo on first start and cached in the
standard Hugging Face cache.

## Features

- **Input**: PDF (page rendering at configurable DPI), images (JPG/PNG/TIF/WEBP/BMP/GIF),
  DOCX, PPTX, ODT, RTF, TXT, MD, HTML, CSV, JSON and other text formats.
  Scans and images go through OCR; text/office files are imported directly.
- **Model loads at startup**; download and loading progress is visible in the status bar.
- **Tabbed multi-file UI**: every opened file gets its own tab.
- **Recognition starts immediately** when a file is opened.
  Opening many files at once asks: *recognize each in its own tab*, or
  *recognize and export to one format*.
- **Two-pane synced comparison**: the original page and the recognized text panes
  scroll/pan together so the recognition can be compared against the original.
- **Stop button** fully cancels the analysis queue.
- **Export, user's choice**: pick any of TXT, MD, RTF, HTML, DOCX, ODT, PDF, EPUB, JSON.
- Tables are recognized in **OTSL** (the model's table format) and converted to
  HTML/DOCX tables automatically; formulas stay in **LaTeX**.
- Journal as a separate window (View → Journal).

## Requirements

- Python 3.10–3.13 (3.13 recommended — the verified combo `transformers==5.17.0`
  + `torch==2.14.0` targets it).
- ~4 GB RAM for the 0.8B model (works on Apple MPS and CUDA GPUs; CPU also works, slower).

## Running

```bash
./scripts/setup_and_run.sh      # or setup_and_run.bat on Windows
```

Or manually:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

## Building a release

- Local build for the current platform: `scripts/build_release.sh` (or `.bat`).
- Cross-platform builds are automated by GitHub Actions: pushing a tag
  `v*` builds **Windows, macOS and Linux** bundles and attaches them to a GitHub release.

## Project structure

```
run.py                    # entry point
setup_and_run.sh / .bat   # venv + deps + launch
scripts/build_release.*   # PyInstaller bundle for the current platform
.github/workflows/build.yml  # release builds for all platforms
xocr_app/
  prompts.py              # official Xiaomi-OCR-0 prompts
  model_engine.py         # model loading / inference
  model_manager.py        # startup loader with GUI progress
  ingest.py               # files → page images or text
  worker.py               # job queue, stop/cancel
  otsl.py                 # OTSL → HTML table converter
  exporters.py            # TXT/MD/RTF/HTML/DOCX/ODT/PDF/EPUB/JSON export
  settings.py             # persisted settings
  ui/                     # main window, tabs, dialogs, journal
```

## Notes

- The Space itself (`xiaomi-research/Xiaomi-OCR-0`) performs no online inference,
  which is why the app ships local inference; results follow the official
  task prompts and post-processing described in the model README.
- On macOS the unsigned release bundle may require right-click → Open on first launch.
