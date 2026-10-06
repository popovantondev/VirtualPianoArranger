"""Controlled child process for lifecycle tests, not an OMR implementation."""
from pathlib import Path
import json
import sys
import time

image = Path(sys.argv[1])
mode = image.read_text()
print("Processing input", flush=True)
if mode == "wait":
    time.sleep(30)
elif mode == "fail":
    print("controlled failure", flush=True)
    sys.exit(4)
elif mode == "missing":
    pass
else:
    if mode == "log":
        for _ in range(1000):print("x" * 10000, flush=True)
    print("Writing XML", flush=True)
    fixture="page-2.musicxml" if mode=="score2" else "page-1.musicxml"
    xml = (Path(__file__).resolve().parents[2]/fixture).read_text(encoding="utf-8") if mode in ("score","score2","quality-score") else "<score-partwise/>"
    image.with_suffix(".musicxml").write_text(xml,encoding="utf-8")
    if mode=="quality-score":
        image.with_suffix(".recognition.json").write_text(json.dumps({"quality":{"version":1,"suspectCount":1,"suspectMeasures":[{"measure":2}]}}),encoding="utf-8")
