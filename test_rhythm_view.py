import unittest
from copy import deepcopy
from fractions import Fraction
from rhythm_view import rhythm_hints,rest_symbols,beat_label,display_fraction

class RhythmTests(unittest.TestCase):
    def test_silence_not_attack_gap(self):
        score={'exact':True,'duration':[8,1], 'measures':[{'number':1,'onset':[0,1],'duration':[4,1]},{'number':2,'onset':[4,1],'duration':[4,1]}], 'notes':[{'onset':[1,1],'duration':[4,1]},{'onset':[2,1],'duration':[1,2]}]}
        hints=rhythm_hints(score)
        self.assertEqual(hints[0]['rests'],[{'onset':0.0,'beat':'1','duration':'1','symbols':[{'kind':'quarter','dots':0}]}])
        self.assertEqual(hints[1]['rests'],[{'onset':5.0,'beat':'2','duration':'3','symbols':[{'kind':'half','dots':1}]}])
        score['exact']=False
        self.assertEqual(rhythm_hints(score),[])

    def test_silent_measure(self):
        score={'exact':True,'duration':[4,1],'measures':[{'number':1,'onset':[0,1],'duration':[4,1]}],'notes':[]}
        self.assertEqual(rhythm_hints(score)[0]['rests'][0]['duration'],'4')
        self.assertEqual(rhythm_hints(score)[0]['rests'][0]['symbols'],[{'kind':'whole','dots':0}])

    def test_midi_articulation_gaps_only_hidden_in_presentation(self):
        score={'exact':True,'duration':[3,1],'parts':[{'midi_channel':0}],
               'measures':[{'number':1,'onset':[0,1],'duration':[3,1]}],
               'notes':[{'onset':[0,1],'duration':[479,480]}, {'onset':[1,1],'duration':[239,480]},
                        {'onset':[2,1],'duration':[1,1]}]}
        original=deepcopy(score);rests=rhythm_hints(score)[0]['rests']
        self.assertEqual(len(rests),1)
        self.assertEqual(rests[0]['duration'],'1/2')
        self.assertEqual(rests[0]['beat'],'2½')
        self.assertEqual(rests[0]['symbols'],[{'kind':'eighth','dots':0}])
        self.assertEqual(score,original)
        score['parts']=[]
        self.assertEqual(len(rhythm_hints(score)[0]['rests']),2,'non-MIDI rests are not thresholded')

    def test_display_rounding_is_bounded(self):
        tolerance=Fraction(1,240)
        self.assertEqual(display_fraction(Fraction(479,480),tolerance),1)
        self.assertEqual(beat_label(Fraction(5,2)),'2½')
        self.assertEqual(beat_label(Fraction(7,3)),'2⅓')
        self.assertEqual(display_fraction(Fraction(119,120),tolerance),Fraction(119,120))
        self.assertEqual(display_fraction(Fraction(479,480)),Fraction(479,480))

    def test_rest_shapes_and_honest_nonstandard_fallback(self):
        for duration,kind in ((4,'whole'),(2,'half'),(1,'quarter'),(Fraction(1,2),'eighth'),(Fraction(1,4),'sixteenth')):
            self.assertEqual(rest_symbols(duration),[{'kind':kind,'dots':0}])
        self.assertEqual(rest_symbols(Fraction(3,2)),[{'kind':'quarter','dots':1}])
        self.assertEqual(rest_symbols(Fraction(1,3)),[{'kind':'eighth','dots':0,'tuplet':3}])
        self.assertEqual(rest_symbols(5),[{'kind':'whole','dots':0},{'kind':'quarter','dots':0}])
        self.assertTrue(rest_symbols(Fraction(1,5))[0]['approximate'])

    def test_sustained_bass_means_no_silence_and_clock_keeps_real_end(self):
        score={'exact':True,'duration':[4,1],'measures':[{'number':1,'onset':[0,1],'duration':[4,1]}],
               'notes':[{'onset':[0,1],'duration':[4,1]}, {'onset':[0,1],'duration':[1,2]},
                        {'onset':[2,1],'duration':[1,2]}]}
        self.assertFalse(rhythm_hints(score)[0]['rests'])
        score['notes']=score['notes'][1:]
        rests=rhythm_hints(score,lambda beat:float(beat*2))[0]['rests']
        self.assertEqual((rests[0]['start'],rests[0]['end']),(1.0,4.0))
        self.assertEqual((rests[1]['start'],rests[1]['end']),(5.0,8.0))
