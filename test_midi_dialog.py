"""Native dialog ergonomics and full-range MIDI playback regressions."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from midi_dialog import MidiPartsDialog
from midi_import import read_midi,select_parts
from midi_preview import original_plan
from offline_piano import PianoBridge
from test_midi_import import smf


class MidiDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def source(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'parts.mid'
            path.write_bytes(smf([[(480,b'\x90\x1d\x64'),(480,b'\x80\x1d\0')],[(0,b'\x91\x40\x40'),(960,b'\x81\x40\0')]]))
            s=read_midi(path)
        return select_parts(s,[p['id'] for p in s['parts']],True)

    def test_dialog_space_contrast_and_pointer_focus(self):
        source=self.source();source['exact']=False
        dialog=MidiPartsDialog(source,'Русский');dialog.show();QTest.qWait(100)
        try:
            available=dialog.screen().availableGeometry()
            self.assertGreaterEqual(dialog.width(),min(920,available.width()-64))
            self.assertLessEqual(dialog.width(),available.width())
            self.assertGreater(dialog.parts.height(),300)
            self.assertTrue(dialog.approximate.isVisible())
            self.assertIn('QLabel,QCheckBox{color:#eadfc9}',dialog.styleSheet())
            self.assertEqual(dialog.layout().contentsMargins().right(),24)
            QTest.mouseClick(dialog.parts.viewport(),Qt.LeftButton,pos=dialog.parts.visualItemRect(dialog.parts.item(0)).center())
            self.assertEqual(dialog.parts.currentRow(),0)
            QTest.keyClick(dialog.parts,Qt.Key_Down);self.assertEqual(dialog.parts.currentRow(),1)
            QTest.mouseClick(dialog.approximate,Qt.LeftButton);self.assertTrue(dialog.approximate.isChecked())
        finally:dialog.close()

    def test_original_midi_sound_keeps_low_bass_and_initial_rest(self):
        source=self.source();before=copy.deepcopy(source);plan=original_plan(source)
        bass=next(n for n in plan['notes'] if n['midi']==29)
        self.assertEqual((bass['start'],bass['end']),(0.5,1.0))
        self.assertEqual(source,before)
        bass['audioOnly']=True
        bridge=PianoBridge({},lambda:[]);bridge.plan_provider=lambda:plan
        self.assertEqual(json.loads(bridge.plan())['notes'],plan['notes'])
        for invalid in (False,1,'true'):
            bass['audioOnly']=invalid
            self.assertEqual(json.loads(bridge.plan())['error'],'invalid')


if __name__=='__main__':unittest.main()
