"""Decode all bundled layers, exercise local controls and render audible PCM."""

import base64
import hashlib
import json
import os
import tempfile
from pathlib import Path
import time
import unittest
from unittest.mock import patch
import wave

# Keep hardware typing and the user's active windows out of the audio regression.
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QCoreApplication, QEvent, Qt, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import main
from offline_piano import ASSET_ROOT, PianoBridge
from test_virtual_piano_panel import MemorySettings, wait_for


class OfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def test_samples_and_invalid_requests(self):
        manifest = json.loads((ASSET_ROOT / "sample_manifest.json").read_text())
        self.assertEqual(len(manifest["files"]), 90)
        self.assertEqual(manifest["license"], "CC BY 3.0")
        for layer in (3, 8, 13):
            self.assertEqual(sum(item["layer"] == layer for item in manifest["files"]), 30)
        for item in manifest["files"]:
            data = (ASSET_ROOT / "samples" / item["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])
        bridge = PianoBridge({}, lambda: [{"time": float("nan"), "duration": 1, "notes": [60]},
                                          {"time": 0, "duration": 1, "notes": [60, -99, "bad"]}])
        self.assertEqual(bridge.sample(999, 8), "")
        self.assertEqual(bridge.sample(60, 999), "")
        self.assertEqual(json.loads(bridge.score()), [{"time": 0, "duration": 1, "notes": [60]}])

    def test_offline_audio_ui_and_online_retained(self):
        with patch.object(main, "QSettings", MemorySettings):
            window = main.MainWindow()
        panel = window.offline_panel
        try:
            window.resize(1200, 850)
            window.show()
            self.assertIsNone(panel.view)
            self.assertIsNone(window.piano_panel.view)
            panel.open_piano()
            console = []
            panel.view.page().javaScriptConsoleMessage = lambda *args: console.append(str(args))

            def evaluate(script):
                result = []
                panel.view.page().runJavaScript(script, result.append)
                self.assertTrue(wait_for(lambda: bool(result), 5000))
                return result[0]

            def await_js(expression, timeout=75000):
                deadline = time.monotonic() + timeout / 1000
                while time.monotonic() < deadline:
                    if evaluate(expression):
                        return
                    QTest.qWait(100)
                self.fail(f"JS condition timed out: {expression}; console={console}; status={panel.status.text()}")

            self.assertTrue(wait_for(lambda: panel.ready, 75000), panel.status.text())
            self.assertEqual(panel.view.url().scheme(), "file")
            class NetworkRequest:
                blocked = False

                def requestUrl(self):
                    return QUrl("https://example.com/not-needed-by-piano")

                def block(self, blocked):
                    self.blocked = blocked

            request = NetworkRequest()
            panel.interceptor.interceptRequest(request)
            self.assertTrue(request.blocked)
            state = lambda: json.loads(evaluate("JSON.stringify(vpaPiano.state())"))
            self.assertEqual(state()["cached"], 30)
            self.assertEqual(evaluate("document.querySelectorAll('.key').length"), 61)
            panel.view.setFocus()
            QTest.qWait(100)
            target = panel.view.focusProxy() or panel.view
            for key in (Qt.Key_T, Qt.Key_U, Qt.Key_O):
                QTest.keyPress(target, key)
            await_js("vpaPiano.state().voices === 3", 10000)
            self.assertEqual(state()["context"], "running")
            evaluate("vpaPiano.setSustain(true)")
            for key in (Qt.Key_T, Qt.Key_U, Qt.Key_O):
                QTest.keyRelease(target, key)
            self.assertTrue(state()["sustain"])
            self.assertEqual(state()["held"], 0)
            self.assertEqual(state()["voices"], 3, state())
            QTest.qWait(150)
            self.assertEqual(evaluate("document.querySelectorAll('.key.active').length"), 0)
            evaluate("vpaPiano.setSustain(false)")
            await_js("vpaPiano.state().voices === 0", 5000)

            QTest.keyPress(target, Qt.Key_T)
            await_js("vpaPiano.state().voices === 1", 5000)
            window.output.setFocus()
            QTest.keyClicks(window.output, "editor")
            await_js("vpaPiano.state().voices === 0", 5000)
            self.assertEqual(window.output.toPlainText(), "editor")
            self.assertFalse(state()["sustain"])
            self.assertIsNone(window.piano_panel.view)

            # Verify every bundled MP3 is supported by this Chromium build.
            for layer in (3, 13, 8):
                evaluate(f"vpaPiano.loadLayer({layer}); true")
                self.assertTrue(wait_for(lambda: panel.ready, 75000), panel.status.text())
                self.assertEqual(state()["layer"], layer)
            self.assertEqual(state()["cached"], 90)

            window.events = [{"measure": 1, "time": 0, "duration": 0.2, "notes": [60, 64, 67]}]
            window.chord_slider.setValue(0)
            panel.bridge.plan_provider = lambda: {"version":1, "duration":0.2,
                "notes":[{"id":str(p), "midi":p, "start":0, "end":0.2} for p in (60,64,67)]}
            panel.view.setFocus()
            evaluate("document.getElementById('play').click(); true")
            await_js("vpaPiano.state().voices > 0", 5000)
            await_js("!vpaPiano.state().playing && vpaPiano.state().voices === 0", 5000)

            # Stop must also terminate scheduled playback, not only held keys.
            window.events = [{"measure": 1, "time": 0, "duration": 8, "notes": [60]},
                             {"measure": 2, "time": 4, "duration": 8, "notes": [64]}]
            panel.bridge.plan_provider = lambda: {"version":1, "duration":12,
                "notes":[{"id":"a", "midi":60, "start":0, "end":8}, {"id":"b", "midi":64, "start":4, "end":12}]}
            evaluate("document.getElementById('play').click(); true")
            await_js("vpaPiano.state().playing && vpaPiano.state().voices > 0", 5000)
            evaluate("document.getElementById('pause').click(); true")
            await_js("vpaPiano.state().paused && vpaPiano.state().voices === 0", 5000)
            paused_position = state()["position"]
            QTest.qWait(100)
            self.assertAlmostEqual(state()["position"], paused_position, places=4)
            self.assertEqual(evaluate("document.querySelectorAll('.key.active').length"), 0)
            evaluate("document.getElementById('pause').click(); true")
            await_js("vpaPiano.state().playing && vpaPiano.state().voices > 0", 5000)
            panel.toggle.setChecked(False)
            await_js("!vpaPiano.state().playing && vpaPiano.state().voices === 0", 5000)
            panel.toggle.setChecked(True)

            evaluate("window.__demo=null; vpaPiano.renderDemo().then(result => {window.__demo=JSON.stringify(result)}); true")
            await_js("Boolean(window.__demo)", 20000)
            demo = json.loads(evaluate("window.__demo"))
            self.assertGreater(demo["rms"], 0.001)
            self.assertGreater(demo["peak"], 0.02)
            self.assertLess(demo["peak"], 0.999)
            evidence = tempfile.TemporaryDirectory(prefix="vpa-audio-test-")
            self.addCleanup(evidence.cleanup)
            output = Path(evidence.name)
            path = output / "offline-piano-demo.wav"
            path.write_bytes(base64.b64decode(demo["wave"]))
            with wave.open(str(path)) as recording:
                self.assertEqual(recording.getnchannels(), 2)
                self.assertEqual(recording.getframerate(), 48000)
            print(f"AUDIO: all 90 MP3 decoded; demo peak={demo['peak']:.4f}, RMS={demo['rms']:.4f}; {path}", flush=True)
            window.grab().save(str(output / "offline-piano.png"))

            page = panel.view.page()
            panel.toggle.setChecked(False)
            panel.toggle.setChecked(True)
            self.assertIs(panel.view.page(), page)
            self.assertFalse(state()["sustain"])
            for language in ("Русский", "English", "Deutsch"):
                window.ui_lang.setCurrentText(language)
                await_js(f"document.documentElement.lang === '{ {'Русский':'ru','English':'en','Deutsch':'de'}[language] }'", 5000)
            panel.shutdown()
            self.assertIsNone(panel.view)
        finally:
            window.piano_panel.shutdown()
            panel.shutdown()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


if __name__ == "__main__":
    unittest.main()
