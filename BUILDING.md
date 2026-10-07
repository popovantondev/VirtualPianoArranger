# Build and dependency notes

This is an educational, non-commercial Preview, not a claim that all recognition results are correct. The original application code is MIT; third-party licenses remain separate.

## Application

The current Windows x64 build environment uses CPython 3.14.7, PySide6/PySide6-Essentials/PySide6-Addons/Shiboken6 6.11.2 and PyInstaller 6.22.3. Use a dedicated virtual environment, install `pip install -r requirements-build.lock.txt`, then run `python main.py` from the source root. The included piano samples retain the attribution in `assets/offline_piano/ATTRIBUTION.md`.

To create a directory-based bundle, run `python -m PyInstaller --clean VirtualPianoArranger.spec`. QML Python modules are excluded because the UI uses Widgets/WebEngineWidgets and QtPdf; native DLL dependencies must not be manually removed. The bundle must be tested with `python verify_packaged.py path/to/VirtualPianoArranger` after preparing its recognition runtime.

## Experimental recognition

HOMR runs in a separate Python 3.11 process. The development runtime uses HOMR 0.7.0 and the exact ONNX files referenced by that version. `packaging/prepare_recognition.ps1` copies an already prepared Python installation and site-packages into `runtimes/recognition/win-x64`, without overwriting an existing runtime. Do not use a different model release silently. HOMR code and weights are AGPL-licensed; the original application MIT license does not replace those terms.

The verified child interpreter is Windows x64 CPython 3.11.9. `requirements-recognition.lock.txt` records the exact installed package versions. In a separate build environment, install those packages into a clean site-packages directory. The original runtime has both OpenCV distribution metadata records, but its active `cv2/version.py` identifies the non-headless 5.0.0.93 wheel; install the headless distribution first and overlay non-headless `opencv-python==5.0.0.93` last with `--no-deps`. Keep the original third-party notices of both DLLs. This describes the observed layout, not a claim that two overlapping OpenCV distributions are a preferred new design.

Place the unmodified HOMR ONNX files listed in `MODEL_PROVENANCE.md` into `homr/segmentation` (segnet) and `homr/transformer` (encoder/decoder). Keep RapidOCR's listed ONNX files under `rapidocr/models`. Verify their hashes before creating the child-runtime copy. The original PyTorch checkpoints are corresponding model-source materials, not files that must be executed by the end-user runtime. Use `packaging/prepare_recognition.ps1 -PythonHome <CPython311Directory> -SitePackages <PreparedPackagesDirectory>` from the source tree, then use `packaging/build_review.ps1 -BuildPython <HostPythonExecutable> -OutputDirectory <NewDirectoryUnderDist>` for an isolated build and startup/PDF smoke checks. Never overwrite an existing runtime or candidate.

Full binary distribution materials, dependency locks, corresponding sources and replacement instructions are being completed before the downloadable EXE is released. This source snapshot contains neither HOMR/model binaries nor Qt/Python runtime binaries. Audio/video transcription and YouTube import are not available; preparatory code does not establish those features as working.

## Verification

Run the relevant `test_*.py` tests with unittest. UI tests require Qt WebEngine support; packaged isolated-startup tests do not prove recognition accuracy, musical quality or compatibility with every Windows machine.

Do not bundle separately installed FFmpeg automatically. It is optional for non-WAV export and has its own distribution terms.
