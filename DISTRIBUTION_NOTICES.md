# Virtual Piano Arranger — Windows Preview distribution notices

This free educational open-source project demonstrates offline piano playback, letter notation, MIDI part selection and experimental score recognition. It is not endorsed by Qt, Microsoft, Alexander Holm, HOMR, RapidAI or PaddlePaddle. Educational purpose is not a restriction on the freedoms granted by the applicable licenses.

## Original application

Original VPA code and original artwork: MIT, see `LICENSE`. This does not relicense libraries, samples or model weights. No warranty is provided. The EXE is unsigned. Extract the entire portable folder; do not distribute its EXE alone.

## Qt, PySide and Shiboken 6.11.2

**This application uses Qt and PySide open-source libraries under LGPLv3 and the additional licenses of their components.** Full original license texts and copyright notices are in `licenses/`. Qt WebEngine includes Chromium components; Qt PDF includes PDFium components with their own licenses. The source archives accompanying this release include QtBase, QtDeclarative, QtWebEngine, QtWebChannel, QtPositioning, QtSvg, QtSerialPort and PySide/Shiboken, version 6.11.2. Preserve those notices when redistributing.

Qt Charts, Qt Data Visualization and Qt Virtual Keyboard are not used or included. Native QtQml/QtQuick dependencies needed by WebEngine remain present. Libraries are supplied separately in the `_internal` directory. You may modify and replace compatible libraries, including reverse engineering needed to debug modifications; see `LIBRARY_REPLACEMENT.md`. VPA does not lock library loading to a signed or unmodifiable vendor build.

## Recognition

HOMR 0.7.0 and its model weights use AGPL. The full license, source tag, training/export code and original run 308/396 PyTorch checkpoints accompany the distribution materials. VPA's own recognition adapters are published in the application source. See `MODEL_PROVENANCE.md` for exact hashes and upstream references. Recognition is not claimed to be musically accurate in every score.

RapidOCR 3.9.2 and its listed ONNX weights use Apache-2.0. The original model-repository card, Apache license and applicable notices are preserved. The installed models match the official revision's hashes and are unmodified by VPA. ONNX Runtime 1.29.0 uses MIT with additional notices for its bundled dependencies. All installed recognition-package notices and the available exact-version source archives are included in the materials.

## OpenCV and bundled FFmpeg

The recognition runtime contains OpenCV packages 5.0.0.93 and 4.14.0.94 with their original licenses and third-party notices. Their Windows video-I/O plugins include FFmpeg under LGPL-2.1. This is distinct from the separately installed optional FFmpeg command-line tool used for additional audio export formats.

The supplied Windows DLLs match OpenCV's upstream download hashes. Corresponding materials include FFmpeg tag n7.1, libvpx v1.16.0, AOM v3.14.1, OpenH264 v2.5.0 API materials and the exact OpenCV binary-repository build scripts and wrapper source. The OpenH264 codec DLL itself is not included by VPA; the wrapper is dynamically loaded if a user separately supplies it. Preserve all original notices. Compatible modified video-I/O DLLs may be replaced under the runtime's `site-packages/cv2` directory; no reverse-engineering prohibition is imposed.

## Python and packaging

CPython 3.14.7 hosts the interface; CPython 3.11.9 runs recognition separately. Preserve Python's PSF and included-component notices. PyInstaller's bootloader is distributed under its GPL license with the bootloader exception; this exception does not relicense other bundled libraries. Original package notices and fixed build versions accompany the source materials. Microsoft runtime DLLs retain Microsoft's terms as supplied with the dependencies.

## Piano samples

Salamander Grand Piano V3 recordings: copyright Alexander Holm, CC BY 3.0 Unported. MP3 conversions were distributed by darosh / `@audio-samples/piano-mp3-velocity{3,8,13}` 1.0.5. The 90 MP3 files are unmodified. Playback applies interpolation/pitch shifting, envelopes, optional reverb and limiting. Keep `licenses/Salamander-ATTRIBUTION.md`, its license link, and the sample manifest. No endorsement is implied.

## Source and redistribution

Keep the accompanying source archives, original notices, this notice, model provenance and replacement instructions available with any redistributed package. The archive manifests give per-file hashes. A Git source snapshot alone does not contain the recognition runtimes/models or substitute for their accompanying materials. Do not assert that MIT alone covers the whole portable package.
