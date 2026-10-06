import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
import tempfile
import json
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QApplication, QWidget, QMessageBox, QInputDialog,QStyle,QStyleOptionFocusRect
from studio_dialogs import StudioDialogTheme
from docs.design.preview_dark import PreviewBridge
from test_design_preview import Settings
from pathlib import Path
from PySide6.QtTest import QTest
from PySide6.QtGui import QFontDatabase, QFont,QPixmap,QPainter


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        # Qt's Windows offscreen plugin has no system font database.
        if os.name=="nt" and not QFontDatabase.families():
            QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts/segoeui.ttf"))
            cls.app.setFont(QFont("Segoe UI",10))

    def test_theme_scoped_and_confirmation_semantics_preserved(self):
        root = QWidget()
        theme = StudioDialogTheme(root)
        dialog = QMessageBox(root)
        dialog.setText("Есть несохранённые изменения.\nСохранить перед продолжением?")
        save = dialog.addButton("Сохранить", QMessageBox.AcceptRole)
        discard = dialog.addButton("Не сохранять", QMessageBox.DestructiveRole)
        cancel = dialog.addButton("Отмена", QMessageBox.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.setEscapeButton(cancel)
        dialog.ensurePolished()
        self.assertTrue(dialog.windowFlags() & Qt.FramelessWindowHint)
        self.assertIs(dialog.defaultButton(), cancel)
        self.assertIs(dialog.escapeButton(), cancel)
        self.assertNotIn('border:2px solid',root.styleSheet())
        self.assertEqual(dialog.buttonRole(save), QMessageBox.AcceptRole)
        self.assertTrue(save.property("studioPrimary"))
        self.assertFalse(discard.property("studioPrimary"))
        dialog.show();self.app.processEvents()
        if os.environ.get('VPA_REG_EVIDENCE'):
            cancel.setFocus();self.app.processEvents()
            self.assertTrue(dialog.grab().save(str(Path(os.environ['VPA_REG_EVIDENCE'])/'cancel-no-frame.png')))
        if os.environ.get("VPA_DIALOG_EVIDENCE"):
            path=Path(__file__).resolve().parent/"docs/feasibility/design-live/dialog-unsaved-dark.png"
            self.assertTrue(dialog.grab().save(str(path)))
        QTest.keyClick(dialog,Qt.Key_Escape)
        self.assertIs(dialog.clickedButton(),cancel)
        other = QMessageBox()
        other.ensurePolished()
        self.assertFalse(other.windowFlags() & Qt.FramelessWindowHint)
        text = QInputDialog(root)
        text.ensurePolished()
        self.assertTrue(text.windowFlags() & Qt.FramelessWindowHint)
        self.app.removeEventFilter(theme)
        root.close()

    def test_native_focus_primitive_not_painted_and_global_style_untouched(self):
        from studio_dialogs import suppress_focus_frames
        original=self.app.style();root=QWidget();style=suppress_focus_frames(root)
        pixmap=QPixmap(80,40);pixmap.fill(Qt.black);before=pixmap.toImage()
        painter=QPainter(pixmap);option=QStyleOptionFocusRect();option.rect=pixmap.rect()
        style.drawPrimitive(QStyle.PE_FrameFocusRect,option,painter,root);painter.end()
        self.assertEqual(pixmap.toImage(),before)
        self.assertIs(self.app.style(),original)
        root.close()

    def test_key_height_default_saved_and_invalid(self):
        settings = Settings()
        bridge = PreviewBridge(settings=settings)
        self.assertEqual(bridge.keyHeight(), 220)
        bridge.setKeyHeight(240)
        self.assertEqual(PreviewBridge(settings=settings).keyHeight(), 240)
        bridge.setKeyHeight(999)
        self.assertEqual(bridge.keyHeight(), 240)
        settings.setValue("key-height", "invalid")
        self.assertEqual(bridge.keyHeight(), 220)

    def test_disk_settings_survive_new_bridge_instances(self):
        from studio_ui import StudioBridge
        with tempfile.TemporaryDirectory(prefix="vpa-settings-test-") as directory:
            path=str(Path(directory)/"settings.ini")
            root=QWidget();settings=QSettings(path,QSettings.IniFormat)
            first=StudioBridge(root,settings)
            preferences={"fontSize":30,"keyLabels":"de","piano":False,"follow":False,
                "volume":27,"speed":135,"layer":3,"reverbPreset":"hall","reverbAmount":45,
                "reducedMotion":True,"linkLanguageLayout":False}
            self.assertEqual(first.setView(json.dumps(preferences)),"{}")
            first.setKeyHeight(240);settings.sync()
            other_settings=QSettings(path,QSettings.IniFormat)
            second=StudioBridge(root,other_settings)
            self.assertEqual(second.view_preferences,{**preferences,'rhythmHints':True})
            self.assertEqual(second.keyHeight(),240)
            root.deleteLater();self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
