"""Real WebEngine worklet -> Qt PCM -> verified export, without user files."""
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
import test_design_preview as preview_tests
from test_design_preview import Settings
from docs.design.preview_dark import PreviewWindow, ROOT


class RecordingPreviewTests(unittest.TestCase):
    wait = preview_tests.PreviewTests.wait
    evaluate = preview_tests.PreviewTests.evaluate
    action = preview_tests.PreviewTests.action

    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="vpa-record-ui-test-")
        self.window=PreviewWindow(Settings(), recording_folder=Path(self.temp.name)/"current")
        self.errors=[]
        self.window.page.javaScriptConsoleMessage=lambda _level,msg,_line,_source:self.errors.append(msg)
        self.window.resize(1366,768)
        self.window.show()
        self.wait(lambda:self.evaluate('Boolean(window.vpaRecording && vpaPreview.state().ready)'))

    def tearDown(self):
        if self.window.recorder.current.active:
            self.window.recorder.current.dispose(discard=True)
        self.window.recorder.current.saved=True
        self.window.close()
        self.app.processEvents()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.temp.cleanup()

    def native_click(self, selector):
        rect=json.loads(self.evaluate('JSON.stringify(document.querySelector('+json.dumps(selector)+').getBoundingClientRect().toJSON())'))
        target=self.window.view.focusProxy() or self.window.view
        QTest.mouseClick(target,Qt.LeftButton,Qt.NoModifier,QPoint(int(rect["x"]+rect["width"]/2),int(rect["y"]+rect["height"]/2)))

    def capture(self):
        self.native_click(".record")
        self.wait(lambda:self.evaluate('!["starting","idle"].includes(vpaRecording.state().phase)'),6)
        self.assertEqual(self.evaluate('vpaRecording.state().phase'),"recording",self.errors)
        self.evaluate('document.querySelector("#keys").focus();true')
        target=self.window.view.focusProxy() or self.window.view
        QTest.keyPress(target,Qt.Key_T)
        QTest.qWait(450)
        QTest.keyPress(target,Qt.Key_U)
        QTest.qWait(300)
        QTest.keyRelease(target,Qt.Key_T)
        QTest.keyRelease(target,Qt.Key_U)
        QTest.qWait(300)
        self.assertGreater(self.window.recorder.current.frames,0)
        self.action("record")
        self.wait(lambda:self.evaluate('vpaRecording.state().phase==="ready"'),8)
        self.assertFalse(self.window.recorder.current.active)
        return self.window.recorder.current.path

    def test_actual_stereo_capture_export_and_no_take_library(self):
        path=self.capture()
        with wave.open(str(path),"rb") as pcm:
            self.assertEqual((pcm.getnchannels(),pcm.getsampwidth()),(2,2))
            import array
            samples=array.array("h",pcm.readframes(pcm.getnframes()))
            rms=math.sqrt(sum(value*value for value in samples)/len(samples))/32768
            self.assertGreater(rms,.001,"worklet must record the actual sampler, not silence")
            self.assertLess(max(abs(value) for value in samples),32768)
            seconds=pcm.getnframes()/pcm.getframerate()
        self.assertGreater(seconds,1)
        self.assertEqual(len(list(path.parent.iterdir())),1)
        for width,height in ((960,680),(1366,768)):
            self.window.resize(width,height)
            QTest.qWait(150)
            self.assertTrue(self.evaluate('document.querySelectorAll("#keys .key").length===61'))
            self.assertTrue(self.evaluate('Array.from(document.querySelectorAll("#keys .key")).every(key=>{const r=key.getBoundingClientRect();return r.left>=0 && r.right<=innerWidth && r.bottom<=innerHeight})'))
        for lang,expected in (("en","Current recording"),("de","Aktuelle Aufnahme"),("ru","Текущая запись")):
            self.evaluate('document.querySelector("[data-lang='+lang+']").click();true')
            self.assertTrue(self.evaluate('document.querySelector("#recording-summary").textContent.includes('+json.dumps(expected)+')'))
        self.action("record")
        self.wait(lambda:self.evaluate('!document.querySelector("#record-replace-overlay").hidden'))
        self.assertTrue(self.evaluate('document.querySelector(".app").inert'))
        self.action("record-keep")
        self.assertTrue(path.is_file())
        self.action("export")
        self.assertFalse(self.evaluate('document.querySelector("#export-overlay").hidden'))
        self.assertTrue(self.evaluate('document.querySelector(".app").inert'))
        self.assertEqual(self.evaluate('document.querySelectorAll("#audio-format option").length'),7)
        target=Path(self.temp.name)/"real-piano.wav"
        with patch("recording_bridge.QFileDialog.getSaveFileName",return_value=(str(target),"")):
            self.action("export-file")
            try:
                self.wait(lambda:self.window.recorder.current.saved and self.evaluate('vpaRecording.state().exportPath==='+json.dumps(str(target))),8)
            except AssertionError:
                print("RECORD QT",self.window.recorder.info())
                print("RECORD JS",self.evaluate('JSON.stringify(vpaRecording.state())'))
                print("EXPORT UI",self.evaluate('document.querySelector("#export-status").textContent'))
                print("CONSOLE",self.errors)
                raise
        self.assertEqual(path.read_bytes(),target.read_bytes())
        self.assertTrue(self.evaluate('document.querySelector("#export-status").textContent.includes("проверен")'))
        with patch("recording_bridge.QFileDialog.getSaveFileName",return_value=(str(target),"")):
            self.action("export-file")
            self.wait(lambda:self.window.recorder.error=="exists",8)
        self.assertEqual(path.read_bytes(),target.read_bytes())
        self.action("export-close")
        self.native_click("[data-action=record-listen]")
        self.wait(lambda:self.evaluate('vpaRecording.state().listening'),4)
        self.evaluate('document.querySelector("#stop").click();true')
        self.assertFalse(self.evaluate('vpaRecording.state().listening'))
        if os.environ.get("VPA_RECORDING_EVIDENCE"):
            target_evidence=ROOT/"docs/feasibility/design-live/recording-current.wav"
            if not target_evidence.exists():
                self.window.recorder.exporter.export(path,target_evidence,"wav")
            QTest.qWait(200)
            screenshot=ROOT/"docs/feasibility/design-live/recording-current-controls.png"
            if not screenshot.exists():
                self.window.view.grab().save(str(screenshot))
        print(f"CAPTURE: real Salamander stereo PCM, {seconds:.3f}s, RMS={rms:.5f}")

    def test_unsaved_close_cancel_keeps_recording(self):
        path=self.capture()
        with patch("recording_bridge.QMessageBox.question",return_value=QMessageBox.No):
            self.window.close()
            self.app.processEvents()
        self.assertFalse(self.window.closed)
        self.assertTrue(path.is_file())

    def test_close_while_recording_finishes_before_discard(self):
        self.native_click(".record")
        self.wait(lambda:self.evaluate('vpaRecording.state().phase==="recording"'),6)
        self.evaluate('document.querySelector("#keys").focus();true')
        target=self.window.view.focusProxy() or self.window.view
        QTest.keyPress(target,Qt.Key_T)
        QTest.qWait(250)
        current=self.window.recorder.current
        with patch("recording_bridge.QMessageBox.question",return_value=QMessageBox.Yes):
            self.window.close()
            self.wait(lambda:self.window.closed,8)
        self.assertFalse(current.active)
        self.assertIsNone(current.path)
        self.assertFalse(current.folder.exists())


if __name__=="__main__":
    unittest.main()
