"""Targeted panel checks with local content; --site checks live HTTPS loading.

No MIDI, remote debugging, site script injection or user settings are used.
"""

import sys
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import main
import virtual_piano_panel as piano


class MemorySettings:
    def __init__(self, *_args):
        pass

    def value(self, _key, default=None):
        return default


def wait_for(predicate, timeout_ms=30000):
    loop = QEventLoop()
    poll = QTimer()
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    poll.start(25)
    deadline.start(timeout_ms)
    loop.exec()
    poll.stop()
    deadline.stop()
    return bool(predicate())


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.panel = piano.VirtualPianoPanel()
        self.panel.resize(900, 500)
        self.panel.show()

    def tearDown(self):
        self.panel.shutdown()
        self.panel.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def load_local_page(self):
        self.panel.toggle.setChecked(True)
        self.panel._create_view()
        self.panel.view.setHtml('<input id="notes" autofocus><h1>Local panel test</h1>')
        self.assertTrue(wait_for(lambda: self.panel.state == "ready"))

    def test_lazy_creation_and_missing_component(self):
        self.assertIsNone(self.panel.view)
        with patch.object(self.panel, "_create_view", side_effect=ImportError):
            self.panel.open_button.click()
        self.assertEqual(self.panel.state, "unavailable")
        self.assertTrue(self.panel.open_button.isEnabled())

    def test_collapse_retains_page_and_input(self):
        self.load_local_page()
        view, page = self.panel.view, self.panel.view.page()
        view.setFocus()
        QTest.qWait(100)
        QTest.keyClicks(view.focusProxy() or view, "abc")
        result = []
        # Inspect only the local test document, never Virtual Piano's scripts.
        page.runJavaScript("document.getElementById('notes').value", result.append)
        self.assertTrue(wait_for(lambda: bool(result)))
        self.assertEqual(result[0], "abc")
        self.panel.toggle.setChecked(False)
        self.assertFalse(self.panel.body.isVisible())
        self.panel.toggle.setChecked(True)
        self.assertIs(self.panel.view, view)
        self.assertIs(self.panel.view.page(), page)
        result.clear()
        page.runJavaScript("document.getElementById('notes').value", result.append)
        self.assertTrue(wait_for(lambda: bool(result)))
        self.assertEqual(result[0], "abc")

    def test_failure_retry_and_timeout(self):
        with patch.object(piano, "PIANO_URL", "http://127.0.0.1:1/"):
            self.panel.open_button.click()
            self.assertTrue(wait_for(lambda: self.panel.state == "error"))
            view = self.panel.view
            self.panel.open_button.click()
            self.assertEqual(self.panel.state, "loading")
            self.assertIs(self.panel.view, view)
            self.assertTrue(wait_for(lambda: self.panel.state == "error"))
        self.panel._load_started()
        self.panel._timed_out()
        self.assertEqual(self.panel.state, "error")
        self.assertTrue(self.panel.open_button.isEnabled())
        self.assertFalse(self.panel.progress.isVisible())
        self.panel._renderer_stopped(None, 1)
        self.assertEqual(self.panel.state, "crashed")

    def test_expand_exposes_tall_consent_without_reloading(self):
        self.panel.toggle.setChecked(True)
        self.panel._create_view()
        # Reproduce a fixed consent overlay whose buttons are below a 280px viewport.
        self.panel.view.setHtml('''<style>body {margin:0}
            #consent {position:fixed;top:0;left:0;right:0;height:480px;background:white}
            button {position:absolute;top:430px}</style>
            <div id="consent"><h1>Privacy test</h1><button id="choice"
            onclick="document.getElementById('consent').remove()">Choose</button></div>''')
        self.assertTrue(wait_for(lambda: self.panel.state == "ready"))
        page = self.panel.view.page()
        self.panel.expand_button.click()
        self.assertTrue(wait_for(lambda: self.panel.view.height() > 480))
        self.assertIs(self.panel.view.page(), page)
        result = []
        page.runJavaScript("JSON.stringify({height:innerHeight, bottom:document.getElementById('choice').getBoundingClientRect().bottom})", result.append)
        self.assertTrue(wait_for(lambda: bool(result)))
        import json
        geometry = json.loads(result[0])
        self.assertLess(geometry["bottom"], geometry["height"])
        self.panel._zoom(-0.1)
        self.assertAlmostEqual(self.panel.view.zoomFactor(), 0.9)
        # A native mouse click on LOCAL test content, not an automatic site consent choice.
        from PySide6.QtCore import QPoint
        QTest.mouseClick(self.panel.view.focusProxy() or self.panel.view,
                         Qt.LeftButton, pos=QPoint(25, 395))
        result.clear()
        page.runJavaScript("document.getElementById('consent') === null", result.append)
        self.assertTrue(wait_for(lambda: bool(result)))
        self.assertTrue(result[0])
        self.panel.expanded_window.close()
        self.assertIsNone(self.panel.expanded_window)
        self.assertIs(self.panel.view.page(), page)
        self.assertIs(self.panel.body.parentWidget(), self.panel)
        self.panel.expand_piano()
        self.panel.shutdown()
        self.assertIsNone(self.panel.expanded_window)

    def test_main_editor_focus_translations_and_shutdown(self):
        with patch.object(main, "QSettings", MemorySettings):
            window = main.MainWindow()
        try:
            window.show()
            for language, label in (("Русский", "Открыть пианино"),
                                    ("English", "Open piano"),
                                    ("Deutsch", "Klavier öffnen")):
                window.ui_lang.setCurrentText(language)
                self.assertEqual(window.piano_panel.open_button.text(), label)
            window.output.setFocus()
            QTest.keyClicks(window.output, "abc")
            self.assertEqual(window.output.toPlainText(), "abc")
            self.assertIsNone(window.piano_panel.view)
            window.piano_panel._create_view()
            window.piano_panel.toggle.setChecked(True)
            view = window.piano_panel.view
            view.setHtml('<input id="notes" autofocus>')
            self.assertTrue(wait_for(lambda: window.piano_panel.state == "ready"))
            view.setFocus()
            QTest.qWait(100)
            QTest.keyClicks(view.focusProxy() or view, "piano")
            window.output.setFocus()
            QTest.keyClicks(window.output, "def")
            self.assertEqual(window.output.toPlainText(), "abcdef")
            result = []
            view.page().runJavaScript("document.getElementById('notes').value", result.append)
            self.assertTrue(wait_for(lambda: bool(result)))
            self.assertEqual(result[0], "piano")
            window.piano_panel.shutdown()
            self.assertIsNone(window.piano_panel.view)
            self.assertFalse(window.piano_panel.timeout.isActive())
            window.piano_panel.open_piano()
            self.assertIsNone(window.piano_panel.view)
        finally:
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def check_site():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    with patch.object(main, "QSettings", MemorySettings):
        window = main.MainWindow()
    window.resize(1200, 1000)
    window.show()
    panel = window.piano_panel
    panel.open_button.click()
    ok = wait_for(lambda: panel.state in ("ready", "error", "crashed", "unavailable"), 50000)
    print(f"LIVE: state={panel.state}, completed={ok}", flush=True)
    if panel.view:
        print(f"LIVE: url={panel.view.url().toString()}, title={panel.view.title()}", flush=True)
        if panel.state == "ready":
            page = panel.view.page()
            panel.toggle.setChecked(False)
            panel.toggle.setChecked(True)
            assert panel.view.page() is page
            print("LIVE: collapse/expand retained page; sound/manual play NOT VERIFIED", flush=True)
    success = ok and panel.state == "ready"
    panel.shutdown()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    return 0 if success else 1


if __name__ == "__main__":
    if "--site" in sys.argv:
        sys.exit(check_site())
    unittest.main()
