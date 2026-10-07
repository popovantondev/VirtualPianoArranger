"""Resume official source downloads; verify upstream SHA-256 before acceptance.

Source archives are distribution materials, not installed executables/models.
Partial files are retained for a later retry, never accepted as complete.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

QT_BASE = "https://download.qt.io/archive/qt/6.11/6.11.2/submodules/"
PYSIDE_BASE = "https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/"
SOURCES = [(PYSIDE_BASE, "pyside-setup-everywhere-src-6.11.2.tar.xz")]
SOURCES += [(QT_BASE, f"{name}-everywhere-src-6.11.2.tar.xz") for name in
            ("qtbase", "qtdeclarative", "qtwebchannel", "qtpositioning", "qtsvg", "qtserialport", "qtwebengine")]


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--skip", nargs="*", default=[])
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    records = []
    for base, name in SOURCES:
        if name in args.skip:
            continue
        url = base + name
        target = args.destination / name
        with urllib.request.urlopen(url + ".sha256", timeout=25) as response:
            expected = response.read().decode("utf-8").split()[0].lower()
        if len(expected) != 64 or any(x not in "0123456789abcdef" for x in expected):
            raise ValueError("Invalid upstream hash for " + name)
        complete = target.is_file() and digest(target) == expected
        if not complete:
            result = subprocess.run(["curl.exe", "-sS", "-L", "--fail", "--continue-at", "-",
                                     "--connect-timeout", "15", "--max-time", str(args.seconds),
                                     "--output", str(target), url])
            complete = result.returncode == 0 and target.is_file() and digest(target) == expected
        records.append({"file": name, "source_url": url, "expected_sha256": expected,
                        "bytes": target.stat().st_size if target.exists() else 0,
                        "verified": complete})
        print(name, "VERIFIED" if complete else "PARTIAL", flush=True)
        (args.destination / "source-downloads.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    return 0 if all(x["verified"] for x in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
