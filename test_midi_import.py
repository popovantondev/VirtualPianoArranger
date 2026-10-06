"""Synthetic SMF data only, no owner files or MIDI dependencies."""
from pathlib import Path
import tempfile
import unittest
from midi_import import read_midi,select_parts
from arrangement import playback_plan
from music_time import validate_score


def vlq(value):
    data=[value&127];value>>=7
    while value:data.insert(0,(value&127)|128);value>>=7
    return bytes(data)


def smf(tracks,fmt=1,ppqn=480):
    data=b'MThd'+(6).to_bytes(4,'big')+fmt.to_bytes(2,'big')+len(tracks).to_bytes(2,'big')+ppqn.to_bytes(2,'big')
    for events in tracks:
        track=b''.join(vlq(delta)+event for delta,event in events)+b'\0\xff\x2f\0'
        data+=b'MTrk'+len(track).to_bytes(4,'big')+track
    return data


class MidiTests(unittest.TestCase):
    def test_audition_original_low_bass_trimmed_lead_no_document_changes(self):
        from midi_preview import preview_plan
        from copy import deepcopy
        source=self.read(smf([[(960,b'\x90\x1e\x64'),(480,b'\x80\x1e\0')]],fmt=0))
        before=deepcopy(source);plan=preview_plan(source,[source['parts'][0]['id']])
        self.assertEqual(plan['notes'][0]['midi'],30)
        self.assertEqual((plan['notes'][0]['start'],plan['notes'][0]['end']),(0,.5))
        self.assertTrue(plan['preview']);self.assertEqual(source,before)

    def test_one_zero_eot_padding_only_and_zero_duration_remains_playable(self):
        original=smf([[(0,b'\x90\x3c\x40'),(0,b'\x80\x3c\0'),(480,b'\x90\x40\x40'),(480,b'\x80\x40\0')]],fmt=0)
        length=int.from_bytes(original[18:22],'big')
        padded=original[:18]+(length+1).to_bytes(4,'big')+original[22:]+b'\0'
        result=self.read(padded)
        self.assertTrue(result['exact']);self.assertEqual(len(result['notes']),1)
        self.assertEqual(result['notes'][0]['onset'],[1,1])
        self.assertEqual(len(playback_plan(result,0,0)['notes']),1)
        self.assertTrue(any('padding' in w for w in result['warnings']))
        self.assertTrue(any('Zero-length' in w for w in result['warnings']))
        for tail in (b'\0\0',b'\x01',b'\0\x90\x3c\x40'):
            with self.assertRaises(ValueError):self.read(original[:18]+(length+len(tail)).to_bytes(4,'big')+original[22:]+tail)

    def test_approximate_playback_requires_consent_keeps_uncertainty_and_closed_notes(self):
        result=self.read(smf([[(0,b'\x90\x3c\x40'),(0,b'\xe0\x01\x40'),(480,b'\x80\x3c\0'),(0,b'\x90\x40\x40')]],fmt=0))
        ids=[p['id'] for p in result['parts']]
        self.assertEqual(playback_plan(select_parts(result,ids),0,0)['error'],'uncertain')
        selected=select_parts(result,ids,True);plan=playback_plan(selected,0,0)
        self.assertFalse(selected['exact']);self.assertTrue(plan['approximate'])
        self.assertEqual(len(plan['notes']),1);self.assertEqual(plan['notes'][0]['end'],.5)
        self.assertNotIn('midi_approximate_playback',result)
        with self.assertRaises(ValueError):validate_score({**selected,'parts':[{'id':ids[0],'name':'XML'}]})

    def test_note_off_on_other_track_matches_only_a_unique_channel_pitch(self):
        on=[(0,b'\x90\x3c\x40')];off=[(960,b'\x80\x3c\0')]
        result=self.read(smf([on,off]));self.assertTrue(result['exact'])
        self.assertEqual(result['notes'][0]['duration'],[2,1]);self.assertEqual(result['parts'][0]['midi_track'],0)
        result=self.read(smf([on,on,off]));self.assertFalse(result['exact']);self.assertEqual(result['notes'],[])
        self.assertTrue(any('ambiguous cross-track' in w for w in result['warnings']))

    def test_all_notes_off_respects_pedal_but_all_sound_off_does_not(self):
        for controller,end in [(123,[3,1]),(120,[1,1])]:
            result=self.read(smf([[(0,b'\xb0\x40\x7f'),(0,b'\x90\x3c\x40'),(480,bytes([0xb0,controller,0])),(960,b'\xb0\x40\0')]],fmt=0))
            self.assertTrue(result['exact']);self.assertEqual(result['notes'][0]['duration'],end)

    def test_ports_do_not_share_programs_or_pedals(self):
        first=[(0,b'\xff\x21\x01\x01'),(0,b'\xc0\x07'),(0,b'\xb0\x40\x7f'),(0,b'\x90\x3c\x40'),(480,b'\x80\x3c\0'),(960,b'\xb0\x40\0')]
        second=[(0,b'\xff\x21\x01\x02'),(0,b'\x90\x40\x40'),(480,b'\x80\x40\0')]
        result=self.read(smf([first,second]));self.assertTrue(result['exact'])
        self.assertEqual([(p['midi_port'],p['midi_program']) for p in result['parts']],[(1,7),(2,0)])
        by_pitch={n['pitch']:n for n in result['notes']}
        self.assertEqual(by_pitch[60]['duration'],[3,1]);self.assertEqual(by_pitch[64]['duration'],[1,1])
        with self.assertRaises(ValueError):self.read(smf([[(0,b'\xff\x21\x02\x01\x02')]]))

    def test_channel_pedal_on_separate_track_and_reset(self):
        controls=[(0,b'\xc0\x07'),(0,b'\xb0\x40\x7f'),(1440,b'\xb0\x79\0')]
        notes=[(0,b'\x90\x3c\x64'),(480,b'\x80\x3c\0')]
        result=self.read(smf([controls,notes]))
        self.assertEqual(result['parts'][0]['midi_program'],7)
        self.assertEqual(result['notes'][0]['duration'],[3,1])

    def read(self,data):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.mid';path.write_bytes(data);before=path.read_bytes()
            result=read_midi(path);self.assertEqual(path.read_bytes(),before);return result

    def test_format_zero_running_status_velocity_zero_and_silence(self):
        score=self.read(smf([[(480,b'\x90\x3c\x40'),(480,b'\x3c\x00'),(480,b'\xff\x01\x01x')]],fmt=0))
        self.assertTrue(score['exact']);self.assertEqual(score['notes'][0]['onset'],[1,1])
        self.assertEqual(score['notes'][0]['duration'],[1,1]);self.assertEqual(score['duration'],[3,1])
        plan=playback_plan(score,0,0);self.assertEqual(plan['notes'][0]['start'],.5)
        self.assertEqual(plan['notes'][0]['end'],1);self.assertEqual(plan['duration'],1.5)
        self.assertEqual(plan['notes'][0]['velocity'],64)

    def test_tracks_channels_programs_tempo_meter_and_selection(self):
        conductor=[(0,b'\xff\x51\x03\x07\xa1\x20'),(960,b'\xff\x51\x03\x0f\x42\x40'),(960,b'\xff\x58\x04\x03\x02\x18\x08')]
        treble=[(0,b'\xff\x03\x04Keys'),(0,b'\xc0\x00'),(0,b'\x90\x3c\x64'),(1440,b'\x80\x3c\0')]
        bass=[(480,b'\xc1\x20'),(0,b'\x91\x3c\x30'),(480,b'\x81\x3c\0')]
        score=self.read(smf([conductor,treble,bass]));validate_score(score)
        self.assertEqual(len(score['notes']),2);self.assertEqual(len(score['parts']),2)
        self.assertEqual(score['measures'][0]['duration'],[4,1])
        plan=playback_plan(score,0,0);self.assertEqual(plan['notes'][0]['end'],2)
        chosen=select_parts(score,[score['parts'][1]['id']]);self.assertEqual(len(chosen['notes']),1)
        self.assertEqual(chosen['duration'],score['duration']);self.assertEqual(len(score['notes']),2)
        with self.assertRaises(ValueError):select_parts(score,[])

    def test_sustain_extends_release_without_inventing_notes(self):
        score=self.read(smf([[(0,b'\xb0\x40\x7f'),(0,b'\x90\x3c\x40'),(480,b'\x80\x3c\0'),(480,b'\xb0\x40\0')]],fmt=0))
        self.assertTrue(score['exact']);self.assertEqual(score['notes'][0]['duration'],[2,1])

    def test_overlap_missing_off_bend_and_percussion_are_explicit(self):
        score=self.read(smf([[(0,b'\x90\x3c\x40'),(1,b'\x90\x3c\x40'),(1,b'\x80\x3c\0'),(1,b'\xe0\x01\x40'),(0,b'\x99\x24\x40'),(1,b'\x89\x24\0')]],fmt=0))
        self.assertFalse(score['exact']);self.assertEqual(len(score['notes']),1)
        self.assertEqual(score['notes'][0]['duration'],[1,240])
        self.assertTrue(any(p.get('percussion') for p in score['parts']))
        self.assertTrue(any('Unclosed' in w for w in score['warnings']))
        self.assertEqual(playback_plan(score,0,0)['error'],'uncertain')

    def test_corrupt_unsupported_and_limits(self):
        for data in (b'bad',smf([[]],fmt=2),smf([[]],ppqn=0x8028),smf([[]])[:-1],
                     smf([[(0,b'\x3c\x40')]],fmt=0),smf([[(0,b'\x90\x80\x40')]],fmt=0)):
            with self.subTest(data=data[:20]):
                with self.assertRaises(ValueError):self.read(data)


if __name__=='__main__':unittest.main()
