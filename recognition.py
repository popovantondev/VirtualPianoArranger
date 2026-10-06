"""Cancellable HOMR process; originals and previous outputs are never touched."""
from collections import deque
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading

from PySide6.QtCore import QThread, Signal


def runtime_executable(app_dir):
    name = "win-x64" if os.name == "nt" else "mac-arm64"
    python = "python.exe" if os.name == "nt" else "bin/python3"
    return Path(app_dir) / "runtimes" / "recognition" / name / "python" / python


def homr_command(executable, image):
    executable = Path(executable).resolve()
    packages = executable.parent.parent / "site-packages"
    if executable.name.lower() == "python.exe" or executable.name == "python3":
        # -I ignores PYTHONPATH, user-site and the working directory. No venv
        # launcher with a baked-in path to the previous installation is used.
        if not (packages / "homr" / "main.py").is_file():
            raise RuntimeError("Recognition runtime is incomplete: HOMR is missing")
        required = (("homr/segmentation", "segnet_*.onnx"),
                    ("homr/transformer", "encoder_*.onnx"),
                    ("homr/transformer", "decoder_*.onnx"),
                    ("rapidocr/models", "*.onnx"))
        for directory,pattern in required:
            models=[p for p in (packages/directory).glob(pattern) if "_fp16" not in p.name and p.stat().st_size]
            if len(models)<(3 if directory=="rapidocr/models" else 1):
                raise RuntimeError("Recognition runtime is incomplete: local models are missing")
        runner_directory=Path(__file__).resolve().parent
        # The Qt host's _internal contains Python 3.14 extension modules.
        # Never put that binary directory on the child Python 3.11 import path.
        if getattr(sys,"frozen",False):runner_directory/= "recognition_app"
        runner=runner_directory/"homr_runner.py"
        if not all(runner.with_name(name).is_file() for name in ("homr_runner.py","omr_layout.py","omr_quality.py","omr_duration.py","omr_timing.py","omr_heads.py","omr_notation.py","omr_meter.py")):
            raise RuntimeError("Recognition runtime is incomplete: application runner is missing")
        return [str(executable), "-I", "-u", "-c",
                "import sys,runpy;sys.path.insert(0,sys.argv.pop(1));runner=sys.argv.pop(1);sys.path.insert(1,__import__('os').path.dirname(runner));runpy.run_path(runner,run_name='__main__')",
                str(packages), str(runner), str(image)]
    return [str(executable), str(image)]


class HomrWorker(QThread):
    done = Signal(str, str)
    batchDone = Signal(object, str)
    page = Signal(int, int)
    failed = Signal(str)
    cancelled = Signal()
    log = Signal(str)
    stage = Signal(str)

    def __init__(self, homr_exe, image_path):
        super().__init__()
        self.homr_exe, self.image_path = homr_exe, image_path
        self.image_paths = list(image_path) if isinstance(image_path, (list, tuple)) else [image_path]
        self._directory = None

    def cancel(self):
        self.requestInterruption()

    def cleanup(self):
        # Caller loads the XML synchronously before the queued finished signal.
        if self.isRunning():
            return
        if self._directory:
            self._directory.cleanup()
            self._directory = None

    def run(self):
        try:
            if not 1 <= len(self.image_paths) <= 50:
                raise ValueError("Select between 1 and 50 images")
            self._directory = tempfile.TemporaryDirectory(prefix="vpa-omr-")
            results, logs = [], deque(maxlen=5)
            self._meter_context=None
            for index, source in enumerate(self.image_paths, 1):
                if self.isInterruptionRequested():
                    self.cancelled.emit(); return
                self.page.emit(index, len(self.image_paths))
                directory = Path(self._directory.name) / f"page-{index:04d}"
                directory.mkdir()
                result = self._recognize_one(source, directory)
                if result is None:
                    self.cancelled.emit(); return
                path, log = result
                report=Path(path).with_suffix('.recognition.json')
                self._meter_context=None
                if report.is_file() and report.stat().st_size<=65536:
                    from omr_meter import valid_meter_context
                    try:value=json.loads(report.read_text(encoding='utf-8')).get('quality',{}).get('meterContext')
                    except (ValueError,TypeError,AttributeError):value=None
                    if valid_meter_context(value):self._meter_context=value
                results.append(path); logs.append(log)
            if self.isInterruptionRequested():
                self.cancelled.emit(); return
            if len(results) == 1:
                self.done.emit(results[0], "\n".join(logs)[-3000:])
            else:
                self.batchDone.emit(results, "\n".join(logs)[-3000:])
        except Exception as error:
            if self.isInterruptionRequested(): self.cancelled.emit()
            else: self.failed.emit(str(error)[-3000:])

    def _recognize_one(self, source, directory):
        process = None
        lines = deque(maxlen=80)
        reader = None
        try:
            self.stage.emit("preparing")
            image = directory / ("input" + Path(source).suffix.lower())
            shutil.copy2(source, image)
            if self.isInterruptionRequested():
                return None
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            env.pop('VPA_OMR_METER_CONTEXT',None)
            if getattr(self,'_meter_context',None):env['VPA_OMR_METER_CONTEXT']=json.dumps(self._meter_context)
            self.stage.emit("starting")
            process = subprocess.Popen(homr_command(self.homr_exe, image), cwd=image.parent,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            output = queue.Queue(maxsize=128)

            def read_output():
                for line in process.stdout:
                    try:
                        output.put_nowait(line[-2000:].rstrip())
                    except queue.Full:
                        pass  # Logs must not grow unbounded or block cancellation.

            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()
            self.stage.emit("processing")
            while process.poll() is None or reader.is_alive() or not output.empty():
                if self.isInterruptionRequested():
                    self.stage.emit("cancelling")
                    if process.poll() is None:
                        process.terminate()
                        try: process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill(); process.wait(timeout=3)
                    return None
                try:
                    line = output.get(timeout=.1)
                except queue.Empty:
                    continue
                lines.append(line)
                if "Writing XML" in line or "Result was written" in line:
                    self.stage.emit("reading")
            output_text = "\n".join(lines)[-5000:]
            self.log.emit(output_text)
            if process.returncode:
                raise RuntimeError(output_text or f"HOMR exit code {process.returncode}")
            xml = image.with_suffix(".musicxml")
            if not xml.is_file() or not xml.stat().st_size:
                raise RuntimeError("HOMR produced no MusicXML result.\n" + output_text[-2000:])
            if self.isInterruptionRequested():
                return None
            self.stage.emit("reading")
            return str(xml), output_text[-3000:]
        finally:
            if process:
                if process.poll() is None:
                    process.kill(); process.wait(timeout=3)
                if reader: reader.join(timeout=2)
                if process.stdout: process.stdout.close()
