"""Targeted project/text checks: offscreen Qt, temporary files, isolated settings."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QWidget
import main as piano
import project_io


class MemorySettings:
    def __init__(self, *_args): pass
    def value(self, _key, default=None): return default
    def setValue(self, *_args): pass
    def sync(self): pass


class DummyPiano(QWidget):
    def __init__(self, *_args): super().__init__()
    def set_language(self, *_args): pass
    def shutdown(self): pass


class SafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.events = piano.parse_musicxml(Path(__file__).parent / "page-1.musicxml")

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        with patch.object(piano, "QSettings", MemorySettings), patch.object(piano, "OfflinePianoPanel", DummyPiano), patch.object(piano, "VirtualPianoPanel", DummyPiano):
            self.window = piano.MainWindow()
        self.addCleanup(self.window.deleteLater)
        self.window.events = copy.deepcopy(self.events)
        self.window.recompute(); self.window.mark_clean()

    def save(self, path):
        with patch.object(piano.QFileDialog, "getSaveFileName", return_value=(str(path), "")):
            return self.window.save_project()

    def open(self, path, proceed=True):
        with patch.object(piano.QFileDialog, "getOpenFileName", return_value=(str(path), "")), patch.object(self.window, "confirm_discard", return_value=proceed):
            return self.window.open_project()

    def test_manual_and_empty_survive_controls(self):
        for text in ("моя ручная правка", ""):
            self.window.output.setPlainText(text)
            for layout in ("English", "Deutsch", "Русская"):
                self.window.display_layout.setCurrentText(layout)
                self.window.transpose_spin.setValue(3)
                self.window.chord_slider.setValue(90)
                self.window.spacing_check.toggle()
                self.assertEqual(self.window.output.toPlainText(), text)
            self.assertIsNotNone(self.window._manual_text)
            self.assertFalse(self.window.text_conflict.isHidden())
            self.window.keep_text_btn.click()
            self.assertTrue(self.window.text_conflict.isHidden())
        self.window.replace_text_btn.click()
        self.assertEqual(self.window.output.toPlainText(), self.window._generated_text)
        self.assertIsNone(self.window._manual_text)

    def test_round_trip_and_old_v8(self):
        for language in ("Русский", "English", "Deutsch"):
            for text in ("ручной текст", ""):
                self.window.ui_lang.setCurrentText(language)
                self.window.output.setPlainText(text)
                target = self.root / "roundtrip.vpa.json"
                self.assertTrue(self.save(target))
                self.assertFalse(self.window._dirty)
                self.window.replace_generated_text()
                self.assertTrue(self.open(target))
                self.assertEqual(self.window.output.toPlainText(), text)
                self.assertFalse(self.window._dirty)
                self.window.transpose_spin.setValue(self.window.transpose_spin.value() + 1)
                self.assertEqual(self.window.output.toPlainText(), text)
        data = self.window.collect_state()
        data.pop("generated_transcription"); data.pop("transcription_is_manual")
        data["transcription"] = "legacy edit"
        project_io.write_project(target, data)
        self.assertTrue(self.open(target)); self.assertEqual(self.window.output.toPlainText(), "legacy edit")
        data.pop("transcription")
        project_io.write_project(target, data)
        self.assertTrue(self.open(target)); self.assertEqual(self.window.output.toPlainText(), self.window._generated_text)

    def test_invalid_and_cancel_do_not_change_document(self):
        self.window.output.setPlainText("keep me")
        before = self.window.collect_state()
        for content in ("{broken", '{"version":9,"events":[]}', '{"version":8,"events":[{"notes":[true],"time":0,"duration":1,"measure":1}]}'):
            target = self.root / "bad.json"
            project_io.atomic_write_text(target, content)
            with patch.object(piano.QMessageBox, "critical") as error:
                self.assertFalse(self.open(target))
                error.assert_called_once()
            self.assertEqual(self.window.collect_state(), before)
        target = self.root / "valid.json"
        project_io.write_project(target, before)
        self.assertFalse(self.open(target, proceed=False))
        self.assertEqual(self.window.collect_state(), before)
        with patch.object(self.window, "confirm_discard", return_value=False):
            self.assertFalse(self.window.load_musicxml(Path(__file__).parent / "page-2.musicxml"))
            with patch.object(piano.QFileDialog, "getOpenFileNames", return_value=([str(Path(__file__).parent / "page-2.musicxml")], "")):
                self.window.open_xml_multi()
            with patch.object(piano.QFileDialog, "getOpenFileName", return_value=("other.png", "")):
                self.window.open_score()
            event = QCloseEvent(); self.window.closeEvent(event)
            self.assertFalse(event.isAccepted())
        self.assertEqual(self.window.collect_state(), before)

    def test_failed_save_preserves_previous_file(self):
        target = self.root / "saved.vpa.json"
        self.assertTrue(self.save(target)); previous = target.read_bytes()
        self.window.output.setPlainText("unsaved edit")
        with patch.object(project_io.os, "replace", side_effect=PermissionError("test denial")), patch.object(piano.QMessageBox, "critical") as error:
            self.assertFalse(self.save(target)); error.assert_called_once()
        self.assertTrue(self.window._dirty)
        self.assertEqual(target.read_bytes(), previous)
        self.assertEqual(list(self.root.glob(".vpa-*.tmp")), [])
        with patch.object(piano.QFileDialog, "getSaveFileName", return_value=("", "")):
            self.assertFalse(self.window.save_project())
        self.assertTrue(self.window._dirty)

    def test_txt_exports_visible_text_without_marking_clean(self):
        self.window.output.setPlainText("моё\nисправление")
        target = self.root / "export.txt"
        with patch.object(piano.QFileDialog, "getSaveFileName", return_value=(str(target), "")):
            self.window.export_txt()
        self.assertEqual(target.read_text(encoding="utf-8"), self.window.output.toPlainText())
        self.assertTrue(self.window._dirty)

    def test_validation_rejects_bad_settings_and_nonfinite_time(self):
        data = self.window.collect_state()
        for change in ({"display_layout":[]}, {"comfort":999}, {"spacing":"false"}, {"transcription":None}, {"schema_version":9}):
            bad = copy.deepcopy(data); bad.update(change)
            with self.assertRaises(ValueError): project_io.validate_project(bad)
        bad = copy.deepcopy(data); bad["events"][0]["time"] = float("nan")
        with self.assertRaises(ValueError): project_io.validate_project(bad)
        bad["events"][0]["time"] = 10 ** 400
        with self.assertRaises(ValueError): project_io.validate_project(bad)
        nested = self.root / "nested.json"
        project_io.atomic_write_text(nested, '[' * 2000 + '0' + ']' * 2000)
        with self.assertRaises(ValueError): project_io.read_project(nested)

    def test_generated_text_and_empty_document_settings(self):
        for layout in ("Русская", "English", "Deutsch"):
            self.window.display_layout.setCurrentText(layout)
            expected = piano.render_events(self.window.events, self.window.transpose_spin.value(), layout,
                                            self.window.spacing_check.isChecked(), self.window.chord_slider.value())[0]
            self.assertEqual(self.window.output.toPlainText(), expected)
        data = self.window.collect_state(); data["transcription"] = "preserve despite stale flag"
        data["transcription_is_manual"] = False
        target = self.root / "flag.json"; project_io.write_project(target, data)
        self.assertTrue(self.open(target)); self.window.transpose_spin.setValue(5)
        self.assertEqual(self.window.output.toPlainText(), data["transcription"])
        self.window.events=[]; self.window.mark_clean(); self.window.spacing_check.toggle()
        self.assertTrue(self.window._dirty)

    def test_confirmation_save_discard_cancel(self):
        class Dialog:
            AcceptRole=piano.QMessageBox.AcceptRole
            DestructiveRole=piano.QMessageBox.DestructiveRole
            RejectRole=piano.QMessageBox.RejectRole
            selected=2
            def __init__(self, *_args): self.buttons=[]
            def setWindowTitle(self, *_args): pass
            def setText(self, *_args): pass
            def addButton(self, text, role): self.buttons.append(object()); return self.buttons[-1]
            def setDefaultButton(self, *_args): pass
            def setEscapeButton(self, *_args): pass
            def exec(self): pass
            def clickedButton(self): return self.buttons[self.selected]
        self.window.output.setPlainText("unsaved")
        with patch.object(piano, "QMessageBox", Dialog):
            for language in ("Русский", "English", "Deutsch"):
                self.window.ui_lang.setCurrentText(language)
                Dialog.selected=2; self.assertFalse(self.window.confirm_discard())
                Dialog.selected=1; self.assertTrue(self.window.confirm_discard())
                Dialog.selected=0
                for result in (True, False):
                    with patch.object(self.window, "save_project", return_value=result) as save:
                        self.assertEqual(self.window.confirm_discard(), result); save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
