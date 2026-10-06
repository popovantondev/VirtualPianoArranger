"""Synthetic image evidence only; no owner score/letters in fixtures."""
import unittest

import test_omr_duration as engraving
from omr_heads import verify_repeated_pitch,recover_repeated_bass_eighth
from omr_timing import _staff_schedule
from homr_runner import accept_geometry_alternative,replace_suspect_bars


class HeadTests(unittest.TestCase):
    def setUp(self):
        self.d=engraving.DurationTests();self.d.setUp()
        from homr.transformer.vocabulary import EncodedSymbol
        self.n=lambda r,p="_",s="upper",lift="_":EncodedSymbol(r,p,lift,"_","_",s)
        self.prefix=[self.n("clef_G2"),self.n("chord"),self.n("clef_F4",s="lower"),
                     self.n("keySignature_4"),self.n("note_1","E4"),self.n("barline")]
        self.targets=[{"part":1,"measure":2,"actual":[5,1],"expected":[4,1]}]

    def repeated(self):
        for x in (140,165,190):self.d.head(x,76,filled=True)
        self.d.head(210,88,filled=True)
        return self.prefix+[self.n("note_4","A4") for _ in range(3)]+[self.n("note_4","C4"),self.n("barline"),self.n("newline")]

    def pitch(self,tokens,targets=None,limit=200):
        return verify_repeated_pitch(self.d.image,self.d.systems,tokens,self.targets if targets is None else targets,limit)

    def test_repeated_head_cluster_corrects_pitch_and_key_without_mutating_source(self):
        tokens=self.repeated();result,audit=self.pitch(tokens)
        self.assertEqual(len(audit),3)
        self.assertEqual([(s.pitch,s.lift) for s in result[6:9]],[("F4","#")]*3)
        self.assertEqual([(s.pitch,s.lift) for s in tokens[6:9]],[("A4","_")]*3)
        self.assertEqual([s.rhythm for s in result],[s.rhythm for s in tokens])

    def test_pitch_repair_requires_run_key_reference_and_full_head_counts(self):
        for kind in ("lift","short","key","extra","reference","limit","grace","tuplet"):
            with self.subTest(kind=kind):
                self.setUp();tokens=self.repeated();targets=self.targets;limit=200
                if kind=="lift":tokens[6].lift="#"
                if kind=="short":tokens.pop(6)
                if kind=="key":tokens[3].rhythm="unknown"
                if kind=="extra":self.d.head(120,76,filled=True)
                if kind=="reference":targets=[]
                if kind=="limit":limit=2
                if kind=="grace":tokens[6].rhythm="note_4G"
                if kind=="tuplet":tokens[6].rhythm="note_6"
                self.assertEqual(self.pitch(tokens,targets,limit)[1],[])

    def bass(self,flag=True,dot=True):
        for x,y in ((140,72),(160,76),(195,68),(210,64)):self.d.head(x,y,filled=True)
        self.d.head(140,140,filled=True);self.d.head(177,140,filled=True)
        if dot:self.d.cv2.circle(self.d.image,(152,137),2,0,-1)
        if flag:
            import numpy as np
            self.d.cv2.polylines(self.d.image,[np.array([(182,113),(184,117),(189,121),(190,126),(187,130)])],False,0,2)
        return self.prefix+[self.n("note_4","G4"),self.n("chord"),self.n("note_4.","C3","lower"),
            self.n("note_4","F4"),self.n("note_4","A4"),self.n("chord"),self.n("note_2","D3","lower"),
            self.n("note_4","B4"),self.n("barline"),self.n("newline")]

    def recover(self,tokens,targets=None,limit=200):
        return recover_repeated_bass_eighth(self.d.image,self.d.systems,tokens,self.targets if targets is None else targets,limit)

    def test_visible_missing_bass_flag_is_inserted_at_the_correct_column(self):
        tokens=self.bass();result,audit=self.recover(tokens)
        self.assertEqual(len(audit),1)
        self.assertEqual(len(result),len(tokens)+1)
        self.assertEqual((result[10].pitch,result[10].rhythm,result[10].position),("C3","note_8","lower"))
        self.assertEqual(result[11].pitch,"A4")
        self.assertEqual(_staff_schedule(result,list(range(6,len(result)-2)))[1],4)
        self.assertFalse(any(s.rhythm=="note_8" for s in tokens))

    def test_no_guessed_bass_with_missing_flag_dot_or_conflicting_clocks(self):
        for kind in ("flag","dot","extra","clock","reference","limit","double"):
            with self.subTest(kind=kind):
                self.setUp();tokens=self.bass(flag=kind!="flag",dot=kind!="dot");targets=self.targets;limit=200
                if kind=="extra":self.d.head(200,140,filled=True)
                if kind=="clock":tokens[9].rhythm="note_2"
                if kind=="reference":targets=[]
                if kind=="limit":limit=0
                if kind=="double":
                    import numpy as np
                    self.d.cv2.polylines(self.d.image,[np.array([(182,120),(185,126),(190,131),(190,137),(187,140)])],False,0,2)
                self.assertEqual(self.recover(tokens,targets,limit)[1],[])

    def test_recovered_note_has_exact_musicxml_onset_and_does_not_lengthen_bar(self):
        from pathlib import Path
        import tempfile
        import xml.etree.ElementTree as ET
        from homr.music_xml_generator import generate_xml,XmlGeneratorArguments
        from music_time import read_musicxml
        from omr_timing import retime_independent_staves
        tokens=self.bass();result,audit=self.recover(tokens);self.assertEqual(len(audit),1)
        with tempfile.TemporaryDirectory(prefix="vpa-head-test-") as folder:
            path=Path(folder)/"result.musicxml"
            generate_xml(XmlGeneratorArguments(False,None,None),[result],"").write(str(path))
            tree=ET.parse(path);self.assertEqual(len(retime_independent_staves(tree.getroot(),result)),1)
            tree.write(path);score=read_musicxml(path)
        self.assertEqual(score["measures"][1]["duration"],[4,1])
        bass=[(n["onset"],n["duration"]) for n in score["notes"] if n["measure"]==2 and n["staff"]=="2"]
        self.assertEqual(bass,[([4,1],[3,2]),([11,2],[1,2]),([6,1],[2,1])])


class GeometrySelectionTests(unittest.TestCase):
    def test_no_note_loss_or_unchecked_histogram_can_choose_an_alternative(self):
        old={"measureCount":5,"checkedMeasures":5,"suspectCount":1,"durationCorrections":[],"pitchCorrections":[],"recoveredNotes":[]}
        new=dict(old,suspectCount=0,recoveredNotes=[{"measure":3}])
        self.assertTrue(accept_geometry_alternative((old,40),(new,40)))
        self.assertFalse(accept_geometry_alternative((old,40),(new,39)))
        for changed in (dict(new,measureCount=4),dict(new,checkedMeasures=0),dict(new,suspectCount=1),dict(new,recoveredNotes=[])):
            self.assertFalse(accept_geometry_alternative((old,40),(changed,40)))

    def test_retry_preserves_every_untargeted_bar_and_rejects_metadata_changes(self):
        from types import SimpleNamespace
        from omr_duration import _symbol_bars
        n=lambda r,p="_":SimpleNamespace(rhythm=r,pitch=p,lift="_",position="upper")
        original=[n("clef_G2"),n("note_4","C5"),n("barline"),n("note_4","D5"),n("barline"),n("newline")]
        alternative=[n("clef_G2"),n("note_2","F5"),n("barline"),n("note_4","E5"),n("note_4","G5"),n("barline"),n("newline")]
        candidate=replace_suspect_bars(original,_symbol_bars(original)[0],alternative,{1})
        self.assertTrue(all(a is b for a,b in zip(original[:3],candidate[:3])))
        self.assertEqual([s.pitch for s in candidate if s.rhythm.startswith("note_")],["C5","E5","G5"])
        self.assertEqual(original[3].pitch,"D5")
        alternative[0].rhythm="clef_F4"
        self.assertIsNone(replace_suspect_bars(original,_symbol_bars(original)[0],alternative,{0}))


if __name__=="__main__":unittest.main()
