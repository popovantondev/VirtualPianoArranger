import copy
import unittest
from letter_practice import parse_letters,text_events,render_letters
from practice import musical_groups,practice_score,fit_registers
from music_time import validate_score
from test_arrangement import score
from project_io import validate_project


class LetterPracticeTests(unittest.TestCase):
    labels={36:'1',48:'2',60:'a',61:'A',64:'d',67:'g',72:'h'}

    def test_accompaniment_fullness_for_txt_no_pitch_or_time_invention(self):
        tokens=parse_letters('[2aAdg]\n[aAdg]',self.labels);before=copy.deepcopy(tokens)
        for mode in ('keyboard','balanced','musical'):
            full=text_events(tokens,mode,0,100);low=text_events(tokens,mode,0,0)
            self.assertEqual([e['notes'] for e in low],[[67],[67]])
            self.assertGreater(sum(len(e['notes']) for e in full),sum(len(e['notes']) for e in low))
            for token,event in zip(tokens,full):
                self.assertTrue(set(event['notes'])<=set(token['notes']))
                self.assertEqual(event['duration'],0)
            self.assertEqual(text_events(tokens,'off',0,0),text_events(tokens,'off',0,100))
        self.assertEqual(tokens,before)

    def test_both_chord_syntaxes_and_literal_parenthesis(self):
        labels={**self.labels,70:'('}
        text='[aAdg]  (adg)\n('
        tokens=parse_letters(text,labels)
        self.assertEqual([t['notes'] for t in tokens],[[60,61,64,67],[60,64,67],[70]])
        self.assertEqual([t['line'] for t in tokens],[1,1,2])
        with self.assertRaises(ValueError):parse_letters('[a?]',labels)

    def test_musical_reduction_uses_original_tones_no_new_pitch_or_fake_clock(self):
        text='[2aAdg]\n[aAdg]';tokens=parse_letters(text,self.labels);before=copy.deepcopy(tokens)
        events=text_events(tokens,'musical',0,100)
        self.assertEqual(events[0]['notes'],[48,67])
        for original,event in zip(tokens,events):
            self.assertTrue(set(event['notes'])<=set(original['notes']))
            self.assertEqual(len({p%12 in (1,3,6,8,10) for p in event['notes']}),1)
            self.assertEqual(event['duration'],0)
        self.assertEqual(tokens,before)
        self.assertEqual(render_letters(text,tokens,events,self.labels,0),'[2g]\n[ag]')

    def test_register_moves_complete_voice_by_octave_and_off_restores(self):
        original=score([(24,0,1),(28,1,1),(60,0,1),(64,1,1)])
        for n in original['notes']:n['staff']='2' if n['pitch']<36 else '1';n['voice']='1'
        before=copy.deepcopy(original);result=practice_score(original,'musical')
        changed=[n for n in result['notes'] if n['pitch']!=n['original_pitch']]
        self.assertEqual([n['pitch']-n['original_pitch'] for n in changed],[12,12])
        self.assertTrue(all(36<=n['pitch']<=96 for n in result['notes']))
        self.assertEqual(original,before);self.assertIs(practice_score(original,'off'),original)

    def test_unfit_wide_voice_is_not_individually_folded_or_retuned(self):
        source=score([(24,0,1),(100,1,1)])
        for n in source['notes']:n['staff']='1';n['voice']='1'
        result=practice_score(source,'musical')
        self.assertEqual([n['pitch'] for n in result['notes']],[24,100])

    def test_register_only_preserves_every_note_and_timing_field(self):
        source=score([(30,0,1),(33,2,1),(69,3,1),(86,0,1)])
        for n in source['notes']:
            n['staff']='2' if n['pitch']<=69 else '1';n['voice']='1'
        before=copy.deepcopy(source)
        notes=fit_registers(source['notes'],0)
        validate_score({**source,'notes':notes})
        self.assertEqual([n['pitch'] for n in notes],[42,45,81,86])
        self.assertEqual(len(notes),len(source['notes']))
        for original,adapted in zip(source['notes'],notes):
            self.assertEqual({k:v for k,v in original.items() if k!='pitch'},
                             {k:v for k,v in adapted.items() if k not in ('pitch','original_pitch')})
            self.assertEqual((adapted['pitch']-original['pitch'])%12,0)
        self.assertEqual(source,before)

    def test_source_text_project_bounds_and_version(self):
        value={'version':8,'events':[],'text_source':{'text':'[aA]','layout':'English'},'practice_mode':'musical'}
        self.assertEqual(validate_project(value),value)
        for bad in ({'text':'x','layout':'madeup'},{'text':3,'layout':'English'}):
            with self.assertRaises(ValueError):validate_project({**value,'text_source':bad})


if __name__=='__main__':unittest.main()
