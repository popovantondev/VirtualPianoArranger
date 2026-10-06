# Replacing open-source libraries in the Windows portable package

VPA imposes no prohibition on modification of its open-source dependencies, or on reverse engineering needed to debug such modifications. The original VPA code remains MIT-licensed; each dependency keeps its own license. Keep a backup of the complete portable directory before making changes.

## Qt, PySide and Shiboken

The package is an unpacked PyInstaller `onedir` distribution, not a single-file executable. The dynamically loaded Qt DLLs and PySide bindings are under `_internal/PySide6`; plugins are in `_internal/PySide6/plugins`. Shiboken files are under `_internal/shiboken6`. Chromium resources and translations are under the corresponding PySide directories. WebEngine also uses its supplied helper process.

Build your modified Qt/PySide/Shiboken sources for Windows x64 with the same compiler ABI and Python 3.14 ABI as the package. Qt/PySide/Shiboken 6.11.2 are the baseline. Follow the upstream build instructions in the accompanying source archives. Replace compatible DLLs/PYD files, plugins, helper process and resources as a consistent set in your backup copy; do not mix incompatible architectures or Qt versions. Python 3.11 recognition libraries belong to the separate runtime below, not to the Qt host.

For changes that require different Python bindings, module layout or dependencies, rebuild VPA from the published source using `BUILDING.md` and the supplied PyInstaller spec. Do not remove native QtQml/QtQuick DLLs solely because no QML user interface is present: WebEngine can depend on them. The application does not use Qt Charts, Qt Data Visualization or Qt Virtual Keyboard; their Python bindings and input plugin are excluded by the spec.

## Recognition runtime

HOMR and its weights use AGPL, separately from VPA's own MIT code. The child interpreter is CPython 3.11.9 under `runtimes/recognition/win-x64/python`; recognition packages and models are under `runtimes/recognition/win-x64/site-packages`. Replace compatible Python 3.11 packages/models there, or prepare a replacement child runtime using `packaging/prepare_recognition.ps1`. Do not copy its native modules into the Python 3.14 host.

## Verification and limitations

After replacement, check startup, WebEngine piano display/audio, PDF loading, and recognition before using the modified application. `verify_packaged.py` performs isolated startup, sample-decoding, original test-PDF rasterization and HOMR/XML import checks. It does not certify musical accuracy, audible quality or compatibility of every modified library. No end-to-end modified-library replacement is claimed as tested merely because the package is `onedir`.

This instruction is technical guidance, not a substitute for the complete original licenses and notices accompanying the downloadable distribution.
