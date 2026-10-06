"""Local sampled piano, isolated from the retained online Virtual Piano panel."""

import base64
import json
import math
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl, Signal, Slot
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QToolButton, QVBoxLayout, QHBoxLayout, QWidget


ASSET_ROOT = Path(__file__).resolve().parent / "assets" / "offline_piano"
LABELS = {
    "Русский": ("Офлайн-пианино · Salamander", "Открыть офлайн-пианино", "Не удалось открыть локальное пианино. Проверьте файлы приложения."),
    "English": ("Offline piano · Salamander", "Open offline piano", "Could not open the local piano. Check the application files."),
    "Deutsch": ("Offline-Klavier · Salamander", "Offline-Klavier öffnen", "Lokales Klavier konnte nicht geöffnet werden. Anwendungsdateien prüfen."),
}


class PianoBridge(QObject):
    reported = Signal(str)
    configurationChanged = Signal(str)

    def __init__(self, mapping, score_provider, parent=None):
        super().__init__(parent)
        self.mapping = mapping
        self.score_provider = score_provider
        self.plan_provider = None
        self.language = "Русский"

    @Slot(result=str)
    def configuration(self):
        return json.dumps({"language": self.language, "mapping": self.mapping})

    @Slot(int, int, result=str)
    def sample(self, midi, layer):
        if midi not in range(21, 109, 3) or layer not in (3, 8, 13):
            return ""
        name = f"{('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')[midi % 12]}{midi // 12 - 1}v{layer}.mp3"
        try:
            return base64.b64encode((ASSET_ROOT / "samples" / name).read_bytes()).decode("ascii")
        except OSError:
            return ""

    @Slot(result=str)
    def score(self):
        """Validate the current legacy event model; never execute project content."""
        events = []
        try:
            for event in self.score_provider():
                onset, duration = float(event["time"]), float(event["duration"])
                if not math.isfinite(onset) or not math.isfinite(duration) or onset < 0 or duration <= 0:
                    continue
                notes = [int(n) for n in event["notes"] if isinstance(n, (int, float)) and math.isfinite(n) and 21 <= n <= 108]
                if notes:
                    events.append({"time": onset, "duration": duration, "notes": notes})
        except (TypeError, ValueError, KeyError):
            return "[]"
        return json.dumps(sorted(events, key=lambda e: e["time"]))

    @Slot(str)
    def report(self, value):
        self.reported.emit(value[:500])

    @Slot(result=str)
    def plan(self):
        try:
            plan = self.plan_provider() if self.plan_provider else None
            if not isinstance(plan, dict) or plan.get("version") != 1:
                raise ValueError("No exact playback plan")
            notes = plan.get("notes")
            duration = plan.get("duration")
            if not isinstance(notes, list) or len(notes) > 100000 or type(duration) not in (int, float) or not 0 <= duration <= 1e12 or not math.isfinite(duration):
                raise ValueError("Invalid plan")
            ids = set()
            for note in notes:
                if not isinstance(note, dict) or not isinstance(note.get("id"), str) or note["id"] in ids:
                    raise ValueError("Invalid note id")
                ids.add(note["id"])
                if 'velocity' in note and (type(note['velocity']) is not int or not 1<=note['velocity']<=127):raise ValueError('Invalid MIDI velocity')
                display=note.get("displayMidi")
                if 'audioOnly' in note and (type(note['audioOnly']) is not bool or not note['audioOnly'] or display is not None):
                    raise ValueError('Invalid audio-only note')
                if display is not None and (type(display) is not int or not 36<=display<=96):
                    raise ValueError("Invalid displayed key")
                low,high=(21,108) if display is not None or note.get('audioOnly') else (36,96)
                if type(note.get("midi")) is not int or not low <= note["midi"] <= high:
                    raise ValueError("Note outside keyboard")
                if any(type(note.get(k)) not in (int, float) or not 0 <= note[k] <= duration or not math.isfinite(note[k]) for k in ("start", "end")) or note["end"] <= note["start"]:
                    raise ValueError("Invalid note time")
            return json.dumps(plan, allow_nan=False)
        except (ValueError, TypeError, KeyError, OverflowError):
            return json.dumps({"version": 1, "error": "invalid", "notes": [], "duration": 0})


class OfflinePianoPanel(QWidget):
    def __init__(self, mapping, score_provider, parent=None):
        super().__init__(parent)
        self.view = None
        self.profile = None
        self.language = "Русский"
        self.ready = False
        self.closed = False
        self.bridge = PianoBridge(mapping, score_provider, self)
        self.bridge.reported.connect(self._reported)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.RightArrow)
        self.toggle.toggled.connect(self._expanded)
        self.open_button = QPushButton()
        self.open_button.clicked.connect(self.open_piano)
        header.addWidget(self.toggle)
        header.addStretch()
        header.addWidget(self.open_button)
        layout.addLayout(header)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.body_layout.addWidget(self.status)
        layout.addWidget(self.body)
        self.body.hide()
        self.set_language(self.language)
        QApplication.instance().focusChanged.connect(self._focus_changed)
        QApplication.instance().applicationStateChanged.connect(self._application_state)

    def set_language(self, language):
        self.language = language if language in LABELS else "English"
        self.bridge.language = self.language
        title, button, _error = LABELS[self.language]
        self.toggle.setText(title)
        self.open_button.setText(button)
        if self.view:
            self.bridge.configurationChanged.emit(self.bridge.configuration())

    def _expanded(self, expanded):
        self.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        if not expanded:
            self.panic()
        self.body.setVisible(expanded)

    def open_piano(self):
        if self.closed:
            return
        self.toggle.setChecked(True)
        if self.view:
            if self.status.text():
                self.status.clear()
                self.view.reload()
            self.view.setFocus()
            return
        try:
            from PySide6.QtWebChannel import QWebChannel
            from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInterceptor
            from PySide6.QtWebEngineWidgets import QWebEngineView

            class LocalOnly(QWebEngineUrlRequestInterceptor):
                def interceptRequest(self, info):
                    if info.requestUrl().scheme() not in ("file", "qrc", "data", "blob"):
                        info.block(True)

            self.profile = QWebEngineProfile(self)
            self.interceptor = LocalOnly(self.profile)
            self.profile.setUrlRequestInterceptor(self.interceptor)
            self.view = QWebEngineView(self.body)
            self.view.setMinimumHeight(350)
            page = QWebEnginePage(self.profile, self.view)
            self.view.setPage(page)
            self.channel = QWebChannel(page)
            self.channel.registerObject("piano", self.bridge)
            page.setWebChannel(self.channel)
            page.renderProcessTerminated.connect(lambda *_args: self._load_failed())
            self.view.loadFinished.connect(lambda ok: None if ok else self._load_failed())
            self.body_layout.addWidget(self.view)
            self.view.load(QUrl.fromLocalFile(str(ASSET_ROOT / "index.html")))
        except (ImportError, OSError, RuntimeError):
            self._load_failed()

    def _load_failed(self):
        self.ready = False
        self.status.setText(LABELS[self.language][2])

    def _reported(self, value):
        self.ready = value == "ready"
        if value.startswith("error:"):
            self.status.setText(value)
        elif value == "ready":
            self.status.clear()

    def _focus_changed(self, old, new):
        if self.view and old and (old is self.view or self.view.isAncestorOf(old)):
            if new is not self.view and not (new and self.view.isAncestorOf(new)):
                self.panic()

    def _application_state(self, state):
        if state != Qt.ApplicationActive:
            self.panic()

    def panic(self):
        if self.view and not self.closed:
            self.view.page().runJavaScript("window.vpaPiano && window.vpaPiano.panic()")

    def shutdown(self):
        self.panic()
        self.closed = True
        if self.view:
            self.view.page().setAudioMuted(True)
            self.view.stop()
            self.view.deleteLater()
            self.view = None
        if self.profile:
            # QWebEnginePage must be destroyed before its private profile.
            self.profile.deleteLater()
            self.profile = None
