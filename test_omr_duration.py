"""Synthetic engraving only; no owner's score or transcription in fixtures."""
from fractions import Fraction
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from omr_duration import verify_hollow_durations


class DurationTests(unittest.TestCase):
    def setUp(self):
        try:
            import cv2
            import numpy as np
        except ImportError:self.skipTest("Run in the bundled recognition runtime (cv2/numpy)")
        self.cv2=cv2;self.np=np
        self.systems=[(20,220,[48,56,64,72,80,120,128,136,144,152])]
        self.image=np.full((210,250),255,dtype=np.uint8)
        for y in self.systems[0][2]:cv2.line(self.image,(20,y),(220,y),190,1)
        for x in (20,110,220):cv2.line(self.image,(x,48),(x,152),0,1)
        self.findings=[{"part":1,"measure":2,"actual":[6,1],"expected":[4,1]}]

    def head(self,x=150,y=80,stem="up",filled=False):
        cv2=self.cv2
        cv2.ellipse(self.image,(x,y),(5,3),-20,0,360,0,-1 if filled else 1)
        if stem=="up":cv2.line(self.image,(x+5,y),(x+5,y-27),0,1)
        if stem=="down":cv2.line(self.image,(x-5,y),(x-5,y+27),0,1)

    def symbols(self):
        s=lambda rhythm,pitch=".",position=".":SimpleNamespace(rhythm=rhythm,pitch=pitch,position=position,_duration="cached",lift="_",slur="_",articulation="_")
        return [s("clef_G2",position="upper"),s("chord"),s("clef_F4",position="lower"),
                s("note_1","E4","upper"),s("barline"),s("note_1","G4","upper"),s("chord"),
                s("note_1","E4","upper"),s("chord"),s("note_1","C3","lower"),
                s("note_4","D4","upper"),s("note_4","F4","upper"),s("barline"),s("newline")]

    def check(self,symbols=None):
        return verify_hollow_durations(self.image,self.systems,symbols or self.symbols(),self.findings)

    def test_attached_hollow_head_changes_only_half_note_and_not_input(self):
        self.head();self.head(170,64,stem=None);self.head(150,140,stem=None)
        before=self.symbols();after,audit=self.check(before)
        self.assertEqual([n.rhythm for n in before],[n.rhythm for n in self.symbols()])
        self.assertEqual([i for i,(a,b) in enumerate(zip(before,after)) if a.rhythm!=b.rhythm],[7])
        self.assertEqual(after[7].rhythm,"note_2");self.assertIsNone(after[7]._duration)
        self.assertEqual(before[7]._duration,"cached")
        self.assertEqual((audit[0]["measure"],audit[0]["reason"]),(2,"hollow-head-attached-stem"))
        self.assertEqual(self.check(after)[1],[])

    def test_whole_and_filled_heads_are_not_shortened_to_fit_bar(self):
        for filled in (False,True):
            with self.subTest(filled=filled):
                self.setUp();self.head(stem="up" if filled else None,filled=filled)
                self.assertEqual(self.check()[1],[])

    def test_downward_stem_on_ledger_note(self):
        self.head(y=88,stem="down");symbols=self.symbols();symbols[7].pitch="C4"
        after,audit=self.check(symbols)
        self.assertEqual(after[7].rhythm,"note_2");self.assertEqual(audit[0]["stemDirection"],"down")

    def test_wrong_pitch_nearby_stem_or_barline_is_not_evidence(self):
        self.head(y=76);self.assertEqual(self.check()[1],[])
        self.setUp();self.head(stem=None);self.cv2.line(self.image,(155,48),(155,152),0,1)
        self.assertEqual(self.check()[1],[])
        self.setUp();self.head(stem=None);self.cv2.line(self.image,(159,53),(159,80),0,1)
        self.assertEqual(self.check()[1],[])

    def test_repeated_pitch_multiple_heads_or_stems_are_ambiguous(self):
        self.head();symbols=self.symbols();symbols[10].pitch="E4"
        self.assertEqual(self.check(symbols)[1],[])
        self.setUp();self.head();self.head(x=185,stem=None)
        self.assertEqual(self.check()[1],[])
        self.setUp();self.head();self.cv2.line(self.image,(145,80),(145,107),0,1)
        self.assertEqual(self.check()[1],[])

    def test_bar_alignment_and_missing_system_are_not_guessed(self):
        self.head();self.cv2.line(self.image,(190,48),(190,152),0,1)
        self.assertEqual(self.check()[1],[])
        self.setUp();self.head();self.assertEqual(self.check(self.symbols()[:-1])[1],[])

    def test_unflagged_free_time_dots_grace_tuplets_and_clefs_stay_untouched(self):
        self.head();self.findings=[];self.assertEqual(self.check()[1],[])
        self.findings=[{"part":1,"measure":2,"actual":[6,1],"expected":[6,1]}];self.assertEqual(self.check()[1],[])
        self.head(x=60);self.findings=[{"part":1,"measure":1,"actual":[6,1],"expected":[4,1]}];self.assertEqual(self.check()[1],[])
        self.setUp();self.head()
        self.findings=[{"part":1,"measure":2,"actual":[6,1],"expected":[4,1]}]
        for rhythm in ("note_1.","note_1q","note_3","rest_1"):
            symbols=self.symbols();symbols[7].rhythm=rhythm
            self.assertEqual(self.check(symbols)[1],[])
        symbols=self.symbols();symbols[0].rhythm="clef_C3";self.assertEqual(self.check(symbols)[1],[])

    def test_same_evidence_at_two_and_three_times_resolution(self):
        self.head();base=self.image.copy()
        for scale in (2,3):
            with self.subTest(scale=scale):
                self.image=self.cv2.resize(base,None,fx=scale,fy=scale,interpolation=self.cv2.INTER_NEAREST)
                systems=[(20*scale,220*scale,[y*scale for y in [48,56,64,72,80,120,128,136,144,152]])]
                after,audit=verify_hollow_durations(self.image,systems,self.symbols(),self.findings)
                self.assertEqual(after[7].rhythm,"note_2");self.assertEqual(len(audit),1)

    def test_xml_recomputes_onsets_and_keeps_two_staff_held_notes(self):
        from homr.transformer.vocabulary import EncodedSymbol
        from homr.music_xml_generator import generate_xml,XmlGeneratorArguments
        from music_time import read_musicxml
        self.head();self.head(170,64,stem=None);self.head(150,140,stem=None)
        symbols=[EncodedSymbol(n.rhythm,n.pitch,n.lift,n.articulation,n.slur,n.position) for n in self.symbols()]
        self.assertEqual(symbols[7].get_duration().fraction,Fraction(1))
        verified,audit=self.check(symbols);self.assertEqual(len(audit),1)
        with tempfile.TemporaryDirectory(prefix="vpa-duration-test-") as folder:
            path=Path(folder)/"result.musicxml"
            generate_xml(XmlGeneratorArguments(False,None,None),[symbols],"").write(str(path))
            before=read_musicxml(path);self.assertEqual(before["measures"][1]["duration"],[6,1])
            generate_xml(XmlGeneratorArguments(False,None,None),[verified],"").write(str(path))
            after=read_musicxml(path);self.assertEqual(after["measures"][1]["duration"],[4,1])
        self.assertEqual(len(before["notes"]),len(after["notes"]))
        notes={n["pitch"]:n for n in after["notes"] if n["measure"]==2}
        self.assertEqual(notes[64]["duration"],[2,1])
        for pitch in (67,48):self.assertEqual(notes[pitch]["duration"],[4,1]);self.assertEqual(notes[pitch]["onset"],[4,1])
        self.assertEqual(notes[62]["onset"],[6,1]);self.assertEqual(notes[65]["onset"],[7,1])


if __name__=="__main__":unittest.main()
