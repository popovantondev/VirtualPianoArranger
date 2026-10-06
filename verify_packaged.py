"""Verify the actual Studio/WebEngine/resources and bundled recognition runtime."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


root = Path(__file__).resolve().parent
package = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / "dist" / "VirtualPianoArranger"
exe = package / "VirtualPianoArranger.exe"
if not exe.is_file():
    raise SystemExit(f"Missing packaged EXE: {exe}")
if (package / "_internal" / "icuuc.dll").exists():
    raise SystemExit("Conflicting icuuc.dll was bundled with Qt")
for resource in ("docs/design/dark.html", "docs/design/dark.css", "docs/design/dark.js",
                 "docs/design/document-ui.js", "docs/design/recording-ui.js", "assets/icons/vpa.ico",
                 "recognition_app/homr_runner.py", "recognition_app/omr_layout.py", "recognition_app/omr_quality.py",
                 "recognition_app/omr_duration.py", "recognition_app/omr_timing.py", "recognition_app/omr_heads.py",
                 "recognition_app/omr_notation.py"):
    if not (package / "_internal" / resource).is_file():
        raise SystemExit("Missing Studio resource: " + resource)
if not (package / "runtimes/recognition/win-x64/python/python.exe").is_file():
    raise SystemExit("Bundled recognition Python is missing")

with tempfile.TemporaryDirectory(prefix="vpa-exe-check-") as folder:
    for platform in ("offscreen", "windows"):
        environment = os.environ.copy()
        environment["QT_QPA_PLATFORM"] = platform
        # The host must run without finding the build venv or a system Python.
        for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
            environment.pop(key, None)
        environment["PATH"] = str(Path(environment.get("SystemRoot", "C:/Windows")) / "System32")
        report=Path(folder)/f"{platform}.json"
        try:
            result = subprocess.run([str(exe), "--studio-self-test", "--test-report", str(report)],
                                    cwd=folder, env=environment, timeout=75)
        except subprocess.TimeoutExpired:
            raise SystemExit(f"Packaged Studio did not finish its {platform} self-test")
        if result.returncode != 0 or not report.is_file():
            detail=report.read_text(encoding="utf-8") if report.exists() else "no report"
            raise SystemExit(f"Packaged Studio failed {platform}: {result.returncode}; {detail}")
        data=json.loads(report.read_text(encoding="utf-8"))
        if not data.get("ok") or not data.get("recognitionXml"):
            raise SystemExit(f"Studio reported failure: {data}")
        print(f"PASS {platform}: Studio, 61 keys, {data['ui']['samples']} decoded samples, bundled HOMR/XML imports ({data['seconds']}s)")
print("PASS: standalone Studio EXE verified; musical recognition accuracy and audible quality require owner review")
