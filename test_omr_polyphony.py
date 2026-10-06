"""Image-gated voice hints on synthetic engraving, not private score data."""
import unittest

import test_omr_duration as engraving
from omr_duration import verify_polyphonic_staves


class PolyphonyTests(unittest.TestCase):
    def setUp(self):
        self.drawing=engraving.DurationTests();self.drawing.setUp()
        from homr.transformer.vocabulary import EncodedSymbol
        self.symbols=[EncodedSymbol(n.rhythm,n.pitch,n.lift,n.articulation,n.slur,n.position)
                      for n in self.drawing.symbols()]
        self.symbols[5].rhythm="note_4";self.symbols[7].rhythm="note_2"

    def hints(self):
        return verify_polyphonic_staves(self.drawing.image,self.drawing.systems,self.symbols)

    def test_opposed_stems_at_one_column_enable_a_hint_without_mutating_tokens(self):
        self.drawing.head(150,72,filled=True);self.drawing.head(150,80,stem="down")
        result=self.hints()
        self.assertTrue(getattr(result[5],"_vpa_polyphonic",False))
        self.assertFalse(getattr(self.symbols[5],"_vpa_polyphonic",False))
        self.assertEqual([(s.rhythm,s.pitch,s.position) for s in result],[(s.rhythm,s.pitch,s.position) for s in self.symbols])

    def test_same_stem_direction_is_not_independent_voice_evidence(self):
        self.drawing.head(150,72,filled=True);self.drawing.head(150,80)
        self.assertFalse(any(getattr(s,"_vpa_polyphonic",False) for s in self.hints()))

    def test_different_columns_cannot_be_joined_as_one_attack(self):
        self.drawing.head(150,72,filled=True);self.drawing.head(180,80,stem="down")
        self.assertFalse(any(getattr(s,"_vpa_polyphonic",False) for s in self.hints()))

    def test_missing_bar_alignment_does_not_guess_voices(self):
        self.drawing.head(150,72,filled=True);self.drawing.head(150,80,stem="down")
        self.drawing.cv2.line(self.drawing.image,(190,48),(190,152),0,1)
        self.assertFalse(any(getattr(s,"_vpa_polyphonic",False) for s in self.hints()))


if __name__=="__main__":unittest.main()
