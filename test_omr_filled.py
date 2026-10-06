"""Synthetic filled/hollow engraving and ambiguous repeated-pitch regressions."""
import unittest
import test_omr_duration as duration_fixture
from omr_duration import verify_filled_durations,_plain_filled_stem


class FilledTests(unittest.TestCase):
    def test_ambiguous_four_pixel_rule_does_not_hide_a_thin_flag(self):
        import cv2,numpy as np
        image=np.full((180,260),255,np.uint8);lines=[50,70,90,110,130]
        for y in lines:image[y:y+4]=0
        cv2.ellipse(image,(130,51),(14,7),-15,0,360,0,-1)
        cv2.line(image,(117,49),(117,123),0,2)
        head=(130,51,116,144);stems=[(117,49,123)]
        self.assertIsNone(_plain_filled_stem(image,head,stems,19.88,staff_lines=lines))
        cv2.ellipse(image,(123,105),(9,19),15,270,90,0,3)
        self.assertIsNone(_plain_filled_stem(image,head,stems,19.88,staff_lines=lines))

    def test_rule_evidence_preserves_returning_flags_and_beams_both_directions(self):
        import cv2,numpy as np
        for direction in ('down','up'):
            for shape in ('quarter','flag','beam','dot','hidden-tip'):
                with self.subTest(direction=direction,shape=shape):
                    image=np.full((160,200),255,np.uint8);lines=[45,55,65,75,85]
                    for y in lines:cv2.line(image,(0,y),(199,y),0,1)
                    tip=75 if shape=='hidden-tip' else 80
                    cv2.ellipse(image,(80,40),(7,4),-15,0,360,0,-1)
                    cv2.line(image,(74,40),(74,tip),0,1)
                    if shape=='flag':cv2.ellipse(image,(77,69),(5,11),15,270,90,0,2)
                    if shape=='beam':cv2.line(image,(74,80),(93,80),0,3)
                    if shape=='dot' and direction=='down':cv2.circle(image,(94,40),2,0,-1)
                    head=(80,40,73,87);stems=[(74,40,tip)]
                    if direction=='up':
                        image=cv2.flip(image,-1);head=(119,119,112,126)
                        stems=[(125,159-tip,119)];lines=[159-y for y in lines]
                        if shape=='dot':cv2.circle(image,(133,119),2,0,-1)
                    result=_plain_filled_stem(image,head,stems,10,staff_lines=lines)
                    self.assertEqual(result,direction if shape=='quarter' else None)

    def setUp(self):
        self.f=duration_fixture.DurationTests();self.f.setUp()
        self.symbols=self.f.symbols();self.symbols[7].rhythm="note_2"

    def check(self):
        return verify_filled_durations(self.f.image,self.f.systems,self.symbols,self.f.findings)

    def test_plain_filled_head_corrects_half_without_changing_input(self):
        self.f.head(filled=True);result,audit=self.check()
        self.assertEqual(result[7].rhythm,"note_4");self.assertEqual(self.symbols[7].rhythm,"note_2")
        self.assertIsNone(result[7]._duration);self.assertEqual(audit[0]["reason"],"filled-head-unflagged-stem")

    def test_plain_quarter_misread_as_eighth_is_not_left_short(self):
        self.f.head(filled=True);self.symbols[7].rhythm="note_8"
        self.f.findings=[{"part":1,"measure":2,"actual":[7,2],"expected":[4,1]}]
        result,audit=self.check();self.assertEqual(result[7].rhythm,"note_4")
        self.assertEqual(audit[0]["from"],"note_8");self.assertEqual(self.symbols[7].rhythm,"note_8")

    def test_repeated_pitch_is_matched_in_order_not_to_the_last_note(self):
        self.f.head(filled=True)
        for x in (175,200):self.f.head(x=x,filled=True)
        self.f.cv2.line(self.f.image,(180,53),(205,53),0,3)
        for index in (10,11):self.symbols[index].pitch="E4";self.symbols[index].rhythm="note_8"
        result,audit=self.check();self.assertEqual(len(audit),1);self.assertEqual(result[7].rhythm,"note_4")
        self.assertEqual([result[i].rhythm for i in (10,11)],["note_8","note_8"])

    def test_plain_quarter_misread_as_sixteenth_needs_the_same_image_evidence(self):
        self.f.head(filled=True);self.symbols[7].rhythm="note_16"
        result,audit=self.check();self.assertEqual(result[7].rhythm,"note_4")
        self.assertEqual(audit[0]['from'],'note_16')
        self.f.cv2.line(self.f.image,(155,53),(174,53),0,3)
        self.f.cv2.line(self.f.image,(155,58),(174,58),0,3)
        self.assertEqual(self.check()[1],[])

    def test_hollow_beamed_flagged_and_dotted_notes_are_not_plain_quarters(self):
        for shape in ("hollow","beam","flag","dot"):
            with self.subTest(shape=shape):
                self.setUp();self.f.head(filled=shape!="hollow")
                if shape=="beam":self.f.cv2.line(self.f.image,(155,53),(174,53),0,3)
                if shape=="flag":self.f.cv2.ellipse(self.f.image,(157,59),(5,7),-15,260,90,0,2)
                if shape=="dot":self.f.cv2.circle(self.f.image,(163,80),2,0,-1)
                self.assertEqual(self.check()[1],[])

    def test_missing_head_duplicate_stem_and_wrong_pitch_keep_tokens(self):
        self.f.head(filled=True);self.symbols[10].pitch="E4";self.assertEqual(self.check()[1],[])
        self.setUp();self.f.head(filled=True);self.f.cv2.line(self.f.image,(145,80),(145,107),0,1)
        self.assertEqual(self.check()[1],[])
        self.setUp();self.f.head(y=76,filled=True);self.assertEqual(self.check()[1],[])


    def test_scale_and_audit_budget(self):
        self.f.head(filled=True);base=self.f.image.copy()
        for scale in (2,3):
            systems=[(20*scale,220*scale,[y*scale for y in self.f.systems[0][2]])]
            image=self.f.cv2.resize(base,None,fx=scale,fy=scale,interpolation=self.f.cv2.INTER_NEAREST)
            result,audit=verify_filled_durations(image,systems,self.symbols,self.f.findings)
            self.assertEqual(result[7].rhythm,"note_4");self.assertEqual(len(audit),1)
        self.assertEqual(verify_filled_durations(base,self.f.systems,self.symbols,self.f.findings,limit=0)[1],[])


if __name__=="__main__":unittest.main()
