"""Qt adapter for one recording; no project/take catalog or microphone."""
import json
from pathlib import Path
import tempfile

from PySide6.QtCore import QObject, QThread, QUrl, Signal, Slot, Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox

from audio_recording import AudioExporter, CurrentRecording, PROFILES, RecordingError, find_encoder

LABELS = {
    "ru": {"title":"Экспорт записи", "close":"Текущая запись не экспортирована. Закрыть и удалить её?", "busy":"Дождитесь окончания экспорта."},
    "en": {"title":"Export recording", "close":"This recording has not been exported. Close and discard it?", "busy":"Wait for the export to finish."},
    "de": {"title":"Aufnahme exportieren", "close":"Diese Aufnahme wurde nicht exportiert. Schließen und verwerfen?", "busy":"Warten Sie auf das Ende des Exports."},
}


class ExportJob(QThread):
    result = Signal(str)

    def __init__(self, exporter, source, target, format_id, parent=None):
        super().__init__(parent)
        self.exporter, self.source, self.target, self.format_id = exporter, source, target, format_id

    def run(self):
        try:
            self.exporter.export(self.source, self.target, self.format_id)
            self.result.emit(json.dumps({"ok":True, "path":str(self.target)}))
        except (OSError, ValueError, RecordingError) as error:
            self.result.emit(json.dumps({"error":error.code if isinstance(error, RecordingError) else "storage"}))


class RecordingBridge(QObject):
    changed = Signal(str)

    def __init__(self, root, parent=None, folder=None, encoder=None):
        super().__init__(parent)
        self.current = CurrentRecording(folder or tempfile.mkdtemp(prefix="vpa-current-recording-"))
        self.exporter = AudioExporter(encoder or find_encoder(root))
        self.job = None
        self.phase = "idle"
        self.error = ""
        self.export_path = ""
        self.language = "ru"

    @Slot(result=str)
    def info(self):
        c = self.current
        return json.dumps({"phase":self.phase, "seconds":c.seconds, "frames":c.frames, "saved":c.saved,
            "error":self.error, "exportPath":self.export_path, "formats":self.exporter.formats(),
            "url":QUrl.fromLocalFile(str(c.path)).toString() if c.path and not c.active and c.frames else ""})

    def emit_state(self):
        self.changed.emit(self.info())

    @Slot(str)
    def setLanguage(self, language):
        if language in LABELS:
            self.language = language

    @Slot(int, bool, result=str)
    def begin(self, rate, replace):
        if self.phase == "exporting" or self.job and self.job.isRunning():
            return json.dumps({"error":"busy"})
        try:
            session = self.current.begin(rate, replace)
            self.phase, self.error, self.export_path = "recording", "", ""
            self.emit_state()
            return json.dumps({"session":session})
        except (OSError, RecordingError) as error:
            return json.dumps({"error":error.code if isinstance(error, RecordingError) else "storage"})

    @Slot(str, int, str, result=str)
    def appendPcm(self, session, sequence, pcm):
        try:
            self.current.append(session, sequence, pcm)
            if self.current.frames == self.current._checkpoint_frames:
                self.emit_state()
            return "{}"
        except (OSError, RecordingError) as error:
            return json.dumps({"error":error.code if isinstance(error, RecordingError) else "storage"})

    @Slot(str, str, result=str)
    def finish(self, session, error):
        try:
            self.current.finish(session, error)
            self.phase, self.error = "ready", error
        except (OSError, RecordingError) as exc:
            self.phase = "error"
            self.error = exc.code if isinstance(exc, RecordingError) else "storage"
        self.emit_state()
        return self.info()

    @Slot(str, result=str)
    def exportAudio(self, format_id):
        if self.phase not in ("ready",) or not self.current.path:
            return json.dumps({"error":"busy"})
        available = {item["id"] for item in self.exporter.formats() if item["available"]}
        if format_id not in available:
            return json.dumps({"error":"encoder"})
        title = LABELS[self.language]["title"]
        path, _ = QFileDialog.getSaveFileName(self.parent(), title, "VPA-recording." + format_id,
            PROFILES[format_id][0] + " (*." + format_id + ")",
            options=QFileDialog.DontConfirmOverwrite)
        if not path:
            return json.dumps({"cancelled":True})
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix("." + format_id)
        return self.export_to(target, format_id)

    def export_to(self, target, format_id):
        if self.job and self.job.isRunning():
            return json.dumps({"error":"busy"})
        self.phase, self.error, self.export_path = "exporting", "", ""
        self.job = ExportJob(self.exporter, self.current.path, target, format_id, self)
        self.job.result.connect(self._export_done, Qt.QueuedConnection)
        self.job.finished.connect(self.job.deleteLater)
        self.job.finished.connect(self._export_thread_finished, Qt.QueuedConnection)
        self.job.start()
        self.emit_state()
        return "{}"

    @Slot()
    def _export_thread_finished(self):
        self.job = None

    @Slot(str)
    def _export_done(self, raw):
        result = json.loads(raw)
        self.phase, self.error = "ready", result.get("error", "")
        if result.get("ok"):
            self.current.saved = True
            self.export_path = result["path"]
        self.emit_state()

    def allow_close(self):
        text = LABELS[self.language]
        if self.phase == "exporting" or self.job and self.job.isRunning():
            QMessageBox.information(self.parent(), text["title"], text["busy"])
            return False
        if self.current.frames and not self.current.saved:
            if QMessageBox.question(self.parent(), text["title"], text["close"], QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return False
        return True

    def dispose(self):
        self.current.dispose(discard=True)
        try:
            self.current.folder.rmdir()
        except OSError:
            pass
