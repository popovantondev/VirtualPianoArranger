"""Isolated live design preview; never opens or saves user projects."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt, QUrl, Slot, QSettings, Signal, QEvent
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInterceptor,QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from arrangement import arrange, playback_plan
from music_time import grouped_events, validate_score
from offline_piano import PianoBridge
from recording_bridge import RecordingBridge
from main import VP_MAP, render_key, find_best_transposition

LAYOUTS = {"ru": "Русская", "en": "English", "de": "Deutsch"}


def demo_score():
    """Original eight-bar example, not a user's score or downloaded music."""
    score = {"format": 1, "exact": True, "initial_tempo_explicit": True,
             "parts": [{"id": "demo", "name": "Midnight study"}], "notes": [],
             "measures": [{"number": m + 1, "onset": [m * 4, 1], "duration": [4, 1]} for m in range(8)],
             "tempos": [{"onset": [0, 1], "bpm": [110, 1]}], "duration": [32, 1], "warnings": []}
    chords = [(48, 55, 60, 64), (45, 52, 57, 60), (41, 48, 53, 57), (43, 50, 55, 59)] * 2
    melody = [(72, 76, 79, 76), (72, 76, 81, 79), (77, 76, 74, 72), (74, 78, 79, 71)] * 2
    def note(pitch, at, duration, measure, voice):
        score["notes"].append({"id": f"demo-{len(score['notes'])}", "part_id": "demo", "voice": voice,
                               "staff": voice, "pitch": pitch, "onset": [at, 1],
                               "duration": [duration, 1], "measure": measure})
    for m, (chord, line) in enumerate(zip(chords, melody)):
        for p in chord:
            note(p, m * 4, 3, m + 1, "2")
        for beat, p in enumerate(line):
            note(p, m * 4 + beat, 1, m + 1, "1")
    return validate_score(score)


class PreviewBridge(PianoBridge):
    windowActionRequested = Signal(str)
    windowStateChanged = Signal(bool)

    def __init__(self, parent=None, settings=None):
        self.source = demo_score()
        self.applied = (0, 0, "ru")
        super().__init__(VP_MAP, lambda: grouped_events(self.source), parent)
        self.settings = settings
        self.plan_provider = lambda: playback_plan(self.source, self.applied[0], self.applied[1])

    def result(self, shift, fullness, layout):
        if type(shift) is not int or not -12 <= shift <= 12 or type(fullness) is not int or not 0 <= fullness <= 100 or layout not in LAYOUTS:
            return {"error": "invalid"}
        selection = arrange(self.source, shift, 100 - fullness)
        plan = playback_plan(self.source, shift, 100 - fullness)
        by_id = {n["id"]: n for n in plan["notes"]}
        tokens, lines = [], {}
        for event in selection["attacks"]:
            pitches = event["notes"]
            chars = [render_key(VP_MAP[p]["key"], VP_MAP[p]["shift"], LAYOUTS[layout]) for p in pitches]
            label = "?" if not chars else chars[0] if len(chars) == 1 else "[" + "".join(chars) + "]"
            start = min((by_id[i]["start"] for i in event["note_ids"]), default=event["time"] * 60 / 110)
            tokens.append({"label": label, "pitches": pitches, "measure": event["measure"], "start": start})
            lines.setdefault(event["measure"], []).append(label)
        return {"text": "\n".join(" ".join(line) for line in lines.values()), "tokens": tokens,
                "shift": shift, "fullness": fullness, "layout": layout, "duration": plan["duration"],
                "original": len(self.source["notes"]), "selected": len(selection["notes"]),
                "outside": len(selection["outside"]),
                "shiftKeys": sum(VP_MAP[n["pitch"]]["shift"] for n in selection["notes"])}

    @Slot(int, int, str, result=str)
    def preview(self, shift, fullness, layout):
        return json.dumps(self.result(shift, fullness, layout), ensure_ascii=False)

    @Slot(int, int, str, result=str)
    def apply(self, shift, fullness, layout):
        result = self.result(shift, fullness, layout)
        if "error" not in result:
            self.applied = (shift, 100 - fullness, layout)
        return json.dumps(result, ensure_ascii=False)

    @Slot(int, str, result=str)
    def best(self, fullness, layout):
        if not 0 <= fullness <= 100 or layout not in LAYOUTS:
            return json.dumps({"error": "invalid"})
        shift, _, _ = find_best_transposition(grouped_events(self.source), 100 - fullness, 50)
        return json.dumps(self.result(shift, fullness, layout), ensure_ascii=False)

    @Slot(result=int)
    def keyHeight(self):
        try:
            return max(112, min(260, int(self.settings.value("key-height", 220)))) if self.settings else 220
        except (ValueError, TypeError):
            return 220

    @Slot(int)
    def setKeyHeight(self, value):
        if self.settings and 112 <= value <= 260:
            self.settings.setValue("key-height", value)

    @Slot(str)
    def windowAction(self, action):
        if action in {"close", "minimize", "maximize", "move", "resize-n", "resize-s", "resize-w", "resize-e", "resize-nw", "resize-ne", "resize-sw", "resize-se"}:
            self.windowActionRequested.emit(action)

    @Slot(result=bool)
    def windowMaximized(self):
        return bool(self.parent() and self.parent().isMaximized())


class LocalOnly(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.blocked = []

    def interceptRequest(self, info):
        if info.requestUrl().scheme() not in ("file", "qrc", "data", "blob"):
            self.blocked.append(info.requestUrl().scheme())
            info.block(True)


class PreviewWindow(QMainWindow):
    def __init__(self, settings=None, recording_folder=None, bridge_factory=None):
        super().__init__()
        self.closed = False
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowIcon(QIcon(str(ROOT / "assets" / "icons" / "vpa.ico")))
        self.setWindowTitle("VPA · Midnight Studio · Live preview")
        self.setMinimumSize(960, 680)
        self.resize(1440, 900)
        self.settings = settings or QSettings("LocalTools", "VPA-Design-Preview")
        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)
        self.profile = QWebEngineProfile(self)
        self.interceptor = LocalOnly(self.profile)
        self.profile.setUrlRequestInterceptor(self.interceptor)
        self.page = QWebEnginePage(self.profile, self.view)
        if getattr(self,'native_audio_controls',False):
            # Set before the document/AudioContext exists. Native MIDI Listen
            # buttons are explicit consent but not Chromium DOM gestures.
            # LocalOnly still blocks remote scripts; there is no auto-play.
            self.page.settings().setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture,False)
        self.page.setBackgroundColor(QColor("#101215"))
        self.view.setPage(self.page)
        self.bridge = (bridge_factory or PreviewBridge)(self, self.settings)
        self.bridge.windowActionRequested.connect(self._window_action)
        self.channel = QWebChannel(self.page)
        self.channel.registerObject("piano", self.bridge)
        self.recorder = RecordingBridge(ROOT, self, folder=recording_folder)
        self.channel.registerObject("recorder", self.recorder)
        self.page.setWebChannel(self.channel)
        self.page.renderProcessTerminated.connect(lambda *_: self.setWindowTitle("VPA preview · Browser stopped; reopen preview"))
        QApplication.instance().applicationStateChanged.connect(self._application_state)
        self.view.load(QUrl.fromLocalFile(str(Path(__file__).with_name("dark.html"))))

    def _window_action(self, action):
        if self.closed:
            return
        if action == "close":
            self.close()
        elif action == "minimize":
            self.showMinimized()
        elif action == "maximize":
            self.showNormal() if self.isMaximized() else self.showMaximized()
        elif action == "move" and not self.isMaximized() and self.windowHandle():
            self.windowHandle().startSystemMove()
        elif action.startswith("resize-") and not self.isMaximized() and self.windowHandle():
            edges = Qt.Edges()
            for direction in action.removeprefix("resize-"):
                edges |= {"n": Qt.TopEdge, "s": Qt.BottomEdge, "w": Qt.LeftEdge, "e": Qt.RightEdge}[direction]
            self.windowHandle().startSystemResize(edges)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange and hasattr(self, "bridge"):
            self.bridge.windowStateChanged.emit(self.isMaximized())

    def _application_state(self, state):
        if not self.closed:
            action="focusRestored" if state==Qt.ApplicationActive else "focusLost"
            self.page.runJavaScript(f"window.vpaPiano && vpaPiano.{action}()")

    def closeEvent(self, event):
        if self.closed:
            super().closeEvent(event)
            return
        if self.recorder.current.active:
            event.ignore()
            self.page.runJavaScript("window.vpaRecording && vpaRecording.requestClose()")
            return
        if not self.recorder.allow_close():
            event.ignore()
            return
        self.closed = True
        self.recorder.dispose()
        self.settings.setValue("geometry", self.saveGeometry())
        self.page.runJavaScript("window.vpaPiano && vpaPiano.panic()")
        self.page.setAudioMuted(True)
        self.view.stop()
        self.view.setPage(QWebEnginePage(self.view))
        self.page.deleteLater()
        self.profile.deleteLater()
        super().closeEvent(event)


if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("popovantondev.VPA.DesignPreview")
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(ROOT / "assets" / "icons" / "vpa.ico")))
    window = PreviewWindow()
    window.show()
    sys.exit(app.exec())
