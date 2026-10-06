"""Official online piano for manual playing; no MIDI or page modification."""

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QToolButton,
    QVBoxLayout, QWidget,
)


PIANO_URL = "https://virtualpiano.net/"
TEXTS = {
    "Русский": {
        "open": "Открыть пианино", "retry": "Повторить",
        "expand": "Развернуть пианино", "zoom_out": "Уменьшить масштаб сайта",
        "zoom_in": "Увеличить масштаб сайта",
        "idle": "Онлайн-пианино для игры мышью и клавиатурой. Нужен интернет.",
        "loading": "Загрузка Virtual Piano…",
        "ready": "Нажмите на пианино, чтобы играть. Для букв сайта используйте английскую раскладку.",
        "error": "Не удалось загрузить пианино. Проверьте подключение к интернету и повторите.",
        "unavailable": "Браузерный компонент Qt WebEngine недоступен. Проверьте установку приложения.",
        "crashed": "Браузерный компонент остановился. Нажмите «Повторить».",
    },
    "English": {
        "open": "Open piano", "retry": "Retry",
        "expand": "Expand piano", "zoom_out": "Zoom out website",
        "zoom_in": "Zoom in website",
        "idle": "Online piano for mouse and keyboard playing. Internet required.",
        "loading": "Loading Virtual Piano…",
        "ready": "Click the piano to play. Use the English keyboard layout for the site's letters.",
        "error": "Could not load the piano. Check your internet connection and retry.",
        "unavailable": "Qt WebEngine is unavailable. Check the application installation.",
        "crashed": "The browser component stopped. Click Retry.",
    },
    "Deutsch": {
        "open": "Klavier öffnen", "retry": "Erneut versuchen",
        "expand": "Klavier vergrößern", "zoom_out": "Website verkleinern",
        "zoom_in": "Website vergrößern",
        "idle": "Online-Klavier für Maus und Tastatur. Internet erforderlich.",
        "loading": "Virtual Piano wird geladen…",
        "ready": "Zum Spielen auf das Klavier klicken. Für die Buchstaben der Website die englische Tastaturbelegung verwenden.",
        "error": "Klavier konnte nicht geladen werden. Internetverbindung prüfen und erneut versuchen.",
        "unavailable": "Qt WebEngine ist nicht verfügbar. Installation der Anwendung prüfen.",
        "crashed": "Die Browserkomponente wurde beendet. Erneut versuchen.",
    },
}


class VirtualPianoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.language = "Русский"
        self.state = "idle"
        self.view = None
        self.expanded_window = None
        self._closed = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self.toggle = QToolButton()
        self.toggle.setText("Virtual Piano")
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setCheckable(True)
        self.toggle.setArrowType(Qt.RightArrow)
        self.toggle.toggled.connect(self._set_expanded)
        self.open_button = QPushButton()
        self.open_button.clicked.connect(self.open_piano)
        header.addWidget(self.toggle)
        header.addStretch()
        self.zoom_out_button = QPushButton("−")
        self.zoom_in_button = QPushButton("+")
        self.zoom_out_button.setFixedWidth(32)
        self.zoom_in_button.setFixedWidth(32)
        self.zoom_out_button.clicked.connect(lambda: self._zoom(-0.1))
        self.zoom_in_button.clicked.connect(lambda: self._zoom(0.1))
        header.addWidget(self.zoom_out_button)
        header.addWidget(self.zoom_in_button)
        self.expand_button = QPushButton()
        self.expand_button.clicked.connect(self.expand_piano)
        header.addWidget(self.expand_button)
        header.addWidget(self.open_button)
        layout.addLayout(header)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.body_layout.addWidget(self.message)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        self.body_layout.addWidget(self.progress)
        layout.addWidget(self.body)
        self.body.hide()
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.setInterval(45000)
        self.timeout.timeout.connect(self._timed_out)
        self.set_language(self.language)

    def set_language(self, language):
        self.language = language if language in TEXTS else "English"
        texts = TEXTS[self.language]
        self.message.setText(texts[self.state])
        self.open_button.setText(texts["retry" if self.state in
                                      ("error", "unavailable", "crashed") else "open"])
        self.expand_button.setText(texts["expand"])
        self.zoom_out_button.setToolTip(texts["zoom_out"])
        self.zoom_in_button.setToolTip(texts["zoom_in"])
        self.zoom_out_button.setAccessibleName(texts["zoom_out"])
        self.zoom_in_button.setAccessibleName(texts["zoom_in"])

    def _zoom(self, delta):
        if self.view:
            self.view.setZoomFactor(max(0.5, min(1.5, round(self.view.zoomFactor() + delta, 2))))

    def expand_piano(self):
        if self._closed:
            return
        self.open_piano()
        if not self.view:
            return
        if self.expanded_window:
            self.expanded_window.raise_()
            self.expanded_window.activateWindow()
            return
        # Consent dialogs can be taller than the embedded viewport. Move the
        # existing browser, rather than reloading it or choosing consent for the user.
        dialog = QDialog(self)
        dialog.setWindowTitle("Virtual Piano")
        dialog.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        layout = QVBoxLayout(dialog)
        toolbar = QHBoxLayout()
        for text, delta in (("−", -0.1), ("+", 0.1)):
            button = QPushButton(text)
            button.setFixedWidth(32)
            key = "zoom_out" if delta < 0 else "zoom_in"
            button.setToolTip(TEXTS[self.language][key])
            button.setAccessibleName(TEXTS[self.language][key])
            button.clicked.connect(lambda _checked=False, step=delta: self._zoom(step))
            toolbar.addWidget(button)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        self.layout().removeWidget(self.body)
        layout.addWidget(self.body)
        self.body.show()
        self.expanded_window = dialog
        self.toggle.setEnabled(False)
        dialog.finished.connect(self._restore_embedded)
        dialog.showMaximized()

    def _restore_embedded(self, _result=0):
        dialog = self.expanded_window
        if dialog is None:
            return
        dialog.layout().removeWidget(self.body)
        self.layout().addWidget(self.body)
        self.body.setVisible(self.toggle.isChecked())
        self.toggle.setEnabled(True)
        self.expanded_window = None
        dialog.deleteLater()

    def _set_expanded(self, expanded):
        # Keep the same page alive: hiding the panel must not reset site settings.
        focus = self.focusWidget()
        if not expanded and self.view and (focus is self.view or
                                          (focus and self.view.isAncestorOf(focus))):
            self.toggle.setFocus()
        self.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.body.setVisible(expanded)

    def _create_view(self):
        # Lazy creation avoids Chromium startup or network access on app launch.
        from PySide6.QtWebEngineWidgets import QWebEngineView

        view = QWebEngineView(self.body)
        view.setMinimumHeight(280)
        view.setFocusPolicy(Qt.StrongFocus)
        view.loadStarted.connect(self._load_started)
        view.loadProgress.connect(self.progress.setValue)
        view.loadFinished.connect(self._load_finished)
        view.page().renderProcessTerminated.connect(self._renderer_stopped)
        self.body_layout.addWidget(view, 1)
        self.view = view

    def open_piano(self):
        if self._closed:
            return
        self.toggle.setChecked(True)
        if self.view is None:
            try:
                self._create_view()
            except (ImportError, OSError, RuntimeError):
                self._show_state("unavailable")
                return
        if self.state == "ready":
            self.view.setFocus()
            return
        if self.state == "loading":
            return
        self._load_started()
        self.view.load(QUrl(PIANO_URL))

    def _show_state(self, state):
        self.state = state
        loading = state == "loading"
        self.progress.setVisible(loading)
        self.open_button.setEnabled(not loading)
        if self.view:
            self.view.setVisible(state in ("loading", "ready"))
        self.set_language(self.language)

    def _load_started(self):
        if self._closed:
            return
        self.progress.setValue(0)
        self._show_state("loading")
        self.timeout.start()

    def _load_finished(self, ok):
        if self._closed or self.state != "loading":
            return
        self.timeout.stop()
        self._show_state("ready" if ok else "error")

    def _timed_out(self):
        self._show_state("error")
        if self.view:
            self.view.stop()

    def _renderer_stopped(self, _status, _code):
        if not self._closed:
            self.timeout.stop()
            self._show_state("crashed")

    def shutdown(self):
        self._closed = True
        self.timeout.stop()
        if self.expanded_window:
            self.expanded_window.close()
        if self.view:
            self.view.page().setAudioMuted(True)
            self.view.stop()
            self.body_layout.removeWidget(self.view)
            self.view.hide()
            self.view.deleteLater()
            self.view = None
