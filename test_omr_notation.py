"""Synthetic notation, not an owner's score or a certified model output."""
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import test_omr_duration as engraving
from omr_notation import verify_notation, _sharp_header_end, _pitch
from omr_duration import _pitch_y
from omr_timing import _retime_measure


class NotationTests(unittest.TestCase):
    def setUp(self):
        self.d = engraving.DurationTests();self.d.setUp()
        self.root = ET.fromstring('''<score-partwise><part-list><score-part id="P"><part-name>Piano</part-name></score-part></part-list>
        <part id="P"><measure number="1"><attributes><divisions>4</divisions><key><fifths>4</fifths></key>
        <clef number="1"><sign>G</sign><line>2</line></clef><clef number="2"><sign>F</sign><line>4</line></clef>
        </attributes><note><pitch><step>E</step><octave>4</octave></pitch><duration>16</duration><type>whole</type><voice>1</voice><staff>1</staff></note>
        </measure><measure number="2"><note><rest/><duration>16</duration></note></measure></part></score-partwise>''')

    def note(self, name, duration, staff='1', voice='1', alter=0, slur=None):
        n = ET.Element('note');p = ET.SubElement(n, 'pitch')
        ET.SubElement(p, 'step').text = name[0];ET.SubElement(p, 'alter').text = str(alter);ET.SubElement(p, 'octave').text = name[1]
        ET.SubElement(n, 'duration').text = str(duration*4);ET.SubElement(n, 'type').text = {1:'quarter', 2:'half', 4:'whole'}[duration]
        ET.SubElement(n, 'voice').text = voice;ET.SubElement(n, 'staff').text = staff
        if slur:ET.SubElement(ET.SubElement(n, 'notations'), 'slur', type=slur, number='2')
        return n

    def render(self, events):
        old = self.root.find('./part/measure[@number="2"]')
        new = _retime_measure(old, [(n, Fraction(start), Fraction(duration), i) for i, (n, start, duration) in enumerate(events)], Fraction(4))
        self.assertIsNotNone(new)
        part = self.root.find('part');part.remove(old);part.append(new)

    def run_check(self, limit=200):
        return verify_notation(self.root, self.d.image, self.d.systems, limit)

    def curve(self, y=120):
        import numpy as np
        points = np.array([(146, y-3), (150, y-6), (160, y-9), (170, y-6), (174, y-3)])
        self.d.cv2.polylines(self.d.image, [points], False, 0, 1)

    def tie_case(self, missing=False, curve=True, wrong_second=False):
        self.d.head(140, 120);self.d.head(180, 120, filled=True);self.d.head(210, 120, filled=True)
        self.d.head(140, 72, stem=None);self.d.head(140, 140, stem=None)
        if curve:self.curve()
        events = [(self.note('G4', 4), 0, 4), (self.note('C3', 4, '2', '6'), 0, 4),
                  (self.note('A3', 2, '2', '5', slur='start'), 0, 2)]
        if not missing:events.append((self.note('B3' if wrong_second else 'A3', 1, '2', '5', slur='stop'), 2, 1))
        events.append((self.note('A3', 1, '2', '5'), 3, 1));self.render(events)

    def score(self):
        from music_time import read_musicxml
        with tempfile.TemporaryDirectory(prefix='vpa-notation-test-') as folder:
            path = Path(folder)/'result.musicxml';ET.ElementTree(self.root).write(path)
            return read_musicxml(path)

    def test_complete_solid_sequence_repairs_single_wrong_step_and_alter(self):
        self.d.head(140,140,filled=True);self.d.head(180,140,filled=True)
        self.render([(self.note('C3',1,'2','5'),0,1),(self.note('B2',1,'2','5'),1,1)])
        audit=self.run_check()
        self.assertEqual(len(audit['headPitchCorrections']),1)
        self.assertEqual(len(audit['alterationCorrections']),1)
        self.assertEqual([(n.findtext('pitch/step'),n.findtext('pitch/alter'))
                          for n in self.root.findall('./part/measure[@number="2"]/note')],[('C','1'),('C','1')])

    def test_complete_sharp_header_requires_both_staves_and_order(self):
        original=self.d.image.copy()
        for staff,clef,names in ((1,'G2','F5 C5 G5 D5'.split()),(2,'F4','F3 C3 G3 D3'.split())):
            lines=self.d.systems[0][2][:5] if staff==1 else self.d.systems[0][2][5:]
            for index,name in enumerate(names):
                x=60+12*index;y=round(_pitch_y(name,clef,lines))
                for dx in (0,4):self.d.cv2.line(self.d.image,(x+dx,y-12),(x+dx,y+12),0,1)
                for dy in (-3,3):self.d.cv2.line(self.d.image,(x-2,y+dy),(x+6,y+dy),0,2)
        lines=self.d.systems[0][2];clefs={'1':'G2','2':'F4'}
        self.assertIsNotNone(_sharp_header_end(self.d.image,lines,20,140,4,clefs))
        self.assertIsNone(_sharp_header_end(self.d.image,lines,20,140,4,{'1':'G2','2':'G2'}))
        self.assertIsNone(_sharp_header_end(self.d.image,lines,20,140,-4,clefs))
        self.d.image[108:170]=original[108:170]
        self.assertIsNone(_sharp_header_end(self.d.image,lines,20,140,4,clefs))

    def test_natural_cancellation_header_cannot_unlock_sharp_default(self):
        for staff,clef,names in ((1,'G2','F5 C5 G5 D5'.split()),(2,'F4','F3 C3 G3 D3'.split())):
            lines=self.d.systems[0][2][:5] if staff==1 else self.d.systems[0][2][5:]
            for index,name in enumerate(names):
                x=60+12*index;y=round(_pitch_y(name,clef,lines))
                self.d.cv2.line(self.d.image,(x,y-12),(x,y+3),0,1)
                self.d.cv2.line(self.d.image,(x+4,y-3),(x+4,y+12),0,1)
                for dy in (-3,3):self.d.cv2.line(self.d.image,(x,y+dy),(x+4,y+dy),0,1)
        self.assertIsNone(_sharp_header_end(self.d.image,self.d.systems[0][2],20,140,4,{'1':'G2','2':'F4'}))

    def test_sharp_header_wrong_pitch_order_is_ambiguous(self):
        for staff,clef,names in ((1,'G2','C5 F5 G5 D5'.split()),(2,'F4','C3 F3 G3 D3'.split())):
            lines=self.d.systems[0][2][:5] if staff==1 else self.d.systems[0][2][5:]
            for index,name in enumerate(names):
                x=60+12*index;y=round(_pitch_y(name,clef,lines))
                for dx in (0,4):self.d.cv2.line(self.d.image,(x+dx,y-12),(x+dx,y+12),0,1)
                for dy in (-3,3):self.d.cv2.line(self.d.image,(x-2,y+dy),(x+6,y+dy),0,2)
        self.assertIsNone(_sharp_header_end(self.d.image,self.d.systems[0][2],20,140,4,{'1':'G2','2':'F4'}))

    def dotted_gap_case(self, kind='plain'):
        self.d.head(140,80,filled=True);self.d.head(180,80,filled=True)
        self.d.head(140,140,stem=None,filled=True);self.d.head(180,140,filled=True)
        if kind!='no-dot':self.d.cv2.circle(self.d.image,(149,140),1,0,-1)
        if kind=='double-dot':self.d.cv2.circle(self.d.image,(155,140),1,0,-1)
        if kind=='rest':self.d.cv2.line(self.d.image,(162,130),(158,146),0,2)
        if kind=='flag':self.d.cv2.line(self.d.image,(145,118),(151,124),0,2)
        if kind=='down-flag':self.d.cv2.line(self.d.image,(135,156),(129,150),0,2)
        first=self.note('E4',1);first.find('duration').text='6';ET.SubElement(first,'dot')
        second=self.note('E4',1);second.find('duration').text='2';second.find('type').text='eighth'
        bass=self.note('C3',1,'2','5');bass.find('duration').text='2';bass.find('type').text='eighth'
        events=[(first,0,Fraction(3,2)),(second,Fraction(3,2),Fraction(1,2)),(bass,Fraction(3,2),Fraction(1,2))]
        if kind=='xml-rest':
            rest=ET.Element('note');ET.SubElement(rest,'rest');ET.SubElement(rest,'duration').text='4'
            ET.SubElement(rest,'voice').text='5';ET.SubElement(rest,'staff').text='2'
            events.append((rest,0,1))
        self.render(events)

    def test_dot_and_independent_anchors_recover_gap_without_extending_bar(self):
        self.dotted_gap_case();before=self.score()
        audit=self.run_check();after=self.score()
        self.assertEqual(len(audit['omittedAttackRecoveries']),1)
        self.assertEqual(audit['unmatchedSolidHeads'],[])
        self.assertEqual(after['measures'],before['measures'])
        bass=[n for n in self.root.findall('./part/measure[@number="2"]/note') if n.findtext('staff')=='2']
        self.assertEqual(len(bass),2)
        self.assertEqual(bass[0].findtext('duration'),'6')
        self.assertEqual(bass[0].findtext('type'),'quarter')
        self.assertIsNotNone(bass[0].find('dot'))
        self.assertEqual(bass[0].findtext('pitch/alter'),'1')
        self.assertEqual(bass[1].findtext('duration'),'2')
        self.assertFalse(any(n.find('tie') is not None for n in bass))
        from arrangement import playback_plan, score_clock
        plan=playback_plan(after,0,0);at=score_clock(after)
        sounding=[n for n in plan['notes'] if n['midi']==49]
        self.assertEqual(len(sounding),2)
        self.assertAlmostEqual(sounding[0]['start'],at(Fraction(4)))
        self.assertAlmostEqual(sounding[0]['end'],at(Fraction(11,2)))
        self.assertAlmostEqual(sounding[1]['start'],sounding[0]['end'])
        self.assertAlmostEqual(sounding[1]['end'],at(Fraction(6)))

    def test_dotted_gap_recovery_vetoes_rest_flags_extra_dot_and_budget(self):
        for kind in ('no-dot','double-dot','rest','flag','down-flag','xml-rest','budget'):
            with self.subTest(kind=kind):
                self.setUp();self.dotted_gap_case(kind)
                before=ET.tostring(self.root)
                audit=self.run_check(1 if kind=='budget' else 200)
                self.assertEqual(audit['omittedAttackRecoveries'],[])
                if kind=='budget':self.assertEqual(ET.tostring(self.root),before)

    def test_other_staff_anchors_singleton_without_inventing_missing_note(self):
        self.d.head(140,80,filled=True);self.d.head(180,80,filled=True)
        self.d.head(140,140,stem=None,filled=True);self.d.head(180,140,filled=True)
        self.render([(self.note('E4',1),0,1),(self.note('E4',1),1,1),(self.note('C3',1,'2','5'),1,1)])
        audit=self.run_check()
        self.assertEqual(len(self.root.findall('./part/measure[@number="2"]/note')),3)
        self.assertEqual(len(audit['unmatchedSolidHeads']),1)
        self.assertEqual(audit['alterationCorrections'][0]['reason'],'opposite-staff-attack-anchor-no-local-sign')
        self.assertEqual(self.root.findall('./part/measure[@number="2"]/note')[-1].findtext('pitch/alter'),'1')

    def test_singleton_anchor_does_not_override_earlier_natural(self):
        self.d.head(140,80,filled=True);self.d.head(180,80,filled=True)
        self.d.head(140,140,stem=None,filled=True);self.d.head(180,140,filled=True)
        for x in (123,127):self.d.cv2.line(self.d.image,(x,130),(x,149),0,1)
        for y in (135,143):self.d.cv2.line(self.d.image,(123,y),(127,y),0,1)
        self.render([(self.note('E4',1),0,1),(self.note('E4',1),1,1),(self.note('C3',1,'2','5'),1,1)])
        before=ET.tostring(self.root);self.run_check();self.assertEqual(ET.tostring(self.root),before)

    def test_unique_hollow_chord_restores_isolated_wrong_accidental(self):
        self.d.head(160,116,stem='down');self.d.head(160,128,stem='down')
        self.render([(self.note('F3',2,'2','5',1),0,2),(self.note('B3',2,'2','5',1),0,2)])
        audit=self.run_check()
        self.assertEqual([(a['pitch'],a['from'],a['to']) for a in audit['alterationCorrections']],[('B3','1',0)])

    def whole_composition_case(self, smaller=False):
        physical=(80,88) if smaller else (64,72,80,88)
        for y in physical:
            self.d.cv2.line(self.d.image,(151,y),(169,y),190,1)
            self.d.head(160,y,stem=None)
        for y in (128,140):self.d.head(160,y,stem=None)
        upper=('B4','G4','E4') if smaller else ('B4','G4','F4')
        notes=[self.note(p,4,alter=1 if p=='F4' else 0) for p in upper]
        ET.SubElement(ET.SubElement(notes[0],'notations'),'fermata')
        self.render([(n,0,4) for n in notes]+[(self.note('F3',4,'2','5',1),0,4),(self.note('C3',4,'2','5',1),0,4)])

    def test_whole_composition_restores_missing_member_and_near_wrong_step(self):
        self.whole_composition_case();before=self.score();audit=self.run_check();after=self.score()
        self.assertEqual(len(audit['chordCompositionCorrections']),1)
        upper=[n for n in self.root.findall('./part/measure[@number="2"]/note') if n.findtext('staff')=='1']
        self.assertEqual({_pitch(n) for n in upper},{'B4','G4','E4','C4'})
        self.assertEqual(after['measures'],before['measures'])
        self.assertEqual(sum(n.find('notations/fermata') is not None for n in upper),1)
        self.assertTrue(all(n.findtext('duration')=='16' for n in upper))

    def test_whole_composition_removes_blank_phantoms_and_their_fermata(self):
        self.whole_composition_case(smaller=True);before=self.score();audit=self.run_check();after=self.score()
        self.assertEqual(len(audit['chordCompositionCorrections']),1)
        upper=[n for n in self.root.findall('./part/measure[@number="2"]/note') if n.findtext('staff')=='1']
        self.assertEqual({_pitch(n) for n in upper},{'E4','C4'})
        self.assertTrue(all(n.find('notations/fermata') is None for n in upper))
        self.assertEqual(after['measures'],before['measures'])
        from arrangement import playback_plan
        plan=[n for n in playback_plan(after,0,0)['notes'] if n['start']>=4*60/110]
        self.assertEqual(sorted(n['midi'] for n in plan),[49,54,61,64])
        self.assertTrue(all(abs(n['end']-n['start']-4*60/110)<1e-9 for n in plan))

    def test_whole_composition_vetoes_signs_ties_ambiguous_columns_and_missing_anchor(self):
        for kind in ('printed','explicit','tie','missing','duplicate','not-blank','stem'):
            with self.subTest(kind=kind):
                self.setUp();self.whole_composition_case(smaller=True)
                first=self.root.find('./part/measure[@number="2"]/note')
                if kind=='printed':
                    for x in (143,146):self.d.cv2.line(self.d.image,(x,66),(x,90),0,1)
                elif kind=='explicit':ET.SubElement(first,'accidental').text='natural'
                elif kind=='tie':ET.SubElement(first,'tie',type='stop')
                elif kind=='missing':self.d.image[123:133,150:171]=255
                elif kind=='not-blank':self.d.cv2.circle(self.d.image,(160,64),2,0,-1)
                elif kind=='stem':self.d.cv2.line(self.d.image,(165,80),(165,53),0,1)
                else:
                    for y in (80,88,128,140):self.d.head(195,y,stem=None)
                before=ET.tostring(self.root);audit=self.run_check()
                self.assertEqual(audit['chordCompositionCorrections'],[])
                self.assertEqual(ET.tostring(self.root),before)

    def test_whole_composition_connected_dynamic_is_not_an_isolated_stem(self):
        self.whole_composition_case(smaller=True)
        # Own branched text-like mark, connected below the head: the long
        # vertical part alone looks like a stem, but its side strokes do not.
        self.d.cv2.line(self.d.image,(165,88),(165,109),0,1)
        for y in (97,100,103,106):
            self.d.cv2.line(self.d.image,(160,y),(170,y),0,1)
        self.assertEqual(len(self.run_check()['chordCompositionCorrections']),1)

    def test_whole_composition_scaled_images_and_atomic_guards(self):
        for scale in (1,2,3):
            with self.subTest(scale=scale):
                self.setUp();self.whole_composition_case(smaller=True)
                self.d.image=self.d.cv2.resize(self.d.image,None,fx=scale,fy=scale,interpolation=self.d.cv2.INTER_NEAREST)
                self.d.systems=[(a*scale,b*scale,[y*scale+(scale-1)/2 for y in lines]) for a,b,lines in self.d.systems]
                self.assertEqual(len(self.run_check()['chordCompositionCorrections']),1)
        for kind in ('budget','direction','dot','unknown-key','articulation','invalid-pitch'):
            with self.subTest(kind=kind):
                self.setUp();self.whole_composition_case(smaller=True)
                bar=self.root.find('./part/measure[@number="2"]');first=bar.find('note')
                if kind=='direction':bar.insert(list(bar).index(first)+1,ET.Element('direction'))
                elif kind=='dot':ET.SubElement(first,'dot')
                elif kind=='unknown-key':ET.SubElement(self.root.find('./part/measure/attributes/key'),'key-step').text='F'
                elif kind=='articulation':ET.SubElement(first.find('notations'),'articulations')
                elif kind=='invalid-pitch':first.find('pitch/step').text='H'
                before=ET.tostring(self.root)
                audit=self.run_check(limit=0 if kind=='budget' else 200)
                self.assertEqual(audit['chordCompositionCorrections'],[])
                self.assertEqual(ET.tostring(self.root),before)

    def test_whole_chord_disagreement_warns_without_guessing_composition(self):
        for y in (64,72,80):self.d.head(160,y,stem=None)
        self.render([(self.note('B4',4),0,4),(self.note('G4',4),0,4),(self.note('C4',4),0,4)])
        before=ET.tostring(self.root);audit=self.run_check()
        self.assertEqual(ET.tostring(self.root),before)
        self.assertEqual(len(audit['unresolvedHollowChords']),1)
        self.assertEqual(audit['unresolvedHollowChords'][0]['recognizedCount'],3)

    def test_staff_split_whole_bass_head_is_not_a_conflicting_pitch(self):
        # Own tall oval: the staff stroke separates its white interior into
        # two contours. A fragment centre lies near the next diatonic step.
        self.d.cv2.ellipse(self.d.image,(160,128),(6,5),0,0,360,0,1)
        self.d.cv2.line(self.d.image,(151,128),(169,128),0,1)
        for y in (140,156):self.d.head(160,y,stem=None)
        self.render([(self.note(p,4,'2','5',1),0,4) for p in ('F3','C3','F2')])
        before=ET.tostring(self.root)
        audit=self.run_check()
        self.assertEqual(audit['unresolvedHollowChords'],[])
        self.assertEqual(audit['chordCompositionCorrections'],[])
        self.assertEqual(ET.tostring(self.root),before)

    def test_whole_probe_alone_cannot_invent_a_conflicting_head(self):
        from unittest.mock import patch
        for y in (64,72,80):self.d.head(160,y,stem=None)
        self.render([(self.note(p,4),0,4) for p in ('B4','G4','E4')])
        before=ET.tostring(self.root)
        # A second probe may merge close outlines at their midpoint; it is
        # corroboration, not a replacement for the original complete grid.
        merged=[(160,y,155,165) for y in (64,72,76)]
        with patch('omr_notation._whole_hollow_heads',return_value=merged):
            self.assertEqual(self.run_check()['unresolvedHollowChords'],[])
        self.assertEqual(ET.tostring(self.root),before)

    def test_matching_and_multiple_attack_whole_chords_do_not_warn(self):
        self.d.head(160,64,stem=None);self.d.head(160,80,stem=None)
        self.render([(self.note('B4',4),0,4),(self.note('E4',4),0,4)])
        # Two physical attack columns cannot identify a unique chord.
        self.d.head(195,64,stem=None)
        self.assertEqual(self.run_check()['unresolvedHollowChords'],[])
        self.setUp();self.d.head(160,64,stem=None);self.d.head(160,80,stem=None)
        self.render([(self.note('B4',4),0,4),(self.note('E4',4),0,4),(self.note('E4',1,voice='2'),3,1)])
        self.assertEqual(self.run_check()['unresolvedHollowChords'],[])
        self.setUp();self.d.head(160,64,stem=None);self.d.head(160,80,stem=None)
        self.render([(self.note('B4',4),0,4),(self.note('E4',4),0,4)])
        self.assertEqual(self.run_check()['unresolvedHollowChords'],[])

    def test_ledger_hole_centres_do_not_prove_a_conflicting_whole_pitch(self):
        for y in (72,80,88):self.d.head(160,y,stem=None)
        self.render([(self.note('G4',4),0,4),(self.note('E4',4),0,4),(self.note('D4',4),0,4)])
        self.assertEqual(self.run_check()['unresolvedHollowChords'],[])

    def test_unsupported_clef_does_not_invent_whole_chord_evidence(self):
        for y in (64,72,80):self.d.head(160,y,stem=None)
        self.render([(self.note('B4',4),0,4),(self.note('G4',4),0,4),(self.note('C4',4),0,4)])
        self.root.find('./part/measure/attributes/clef/sign').text='C'
        before=ET.tostring(self.root)
        self.assertEqual(self.run_check()['unresolvedHollowChords'],[])
        self.assertEqual(ET.tostring(self.root),before)

    def test_hollow_chord_local_sign_and_duplicate_visual_chord_veto(self):
        for kind in ('local','duplicate','earlier','explicit'):
            with self.subTest(kind=kind):
                self.setUp()
                self.d.head(160,116,stem='down');self.d.head(160,128,stem='down')
                second=self.note('B3',2,'2','5',1)
                if kind=='local':
                    for x in (144,147):self.d.cv2.line(self.d.image,(x,105),(x,126),0,1)
                    for y in (112,120):self.d.cv2.line(self.d.image,(142,y),(150,y),0,1)
                elif kind=='duplicate':
                    self.d.head(190,116,stem='down');self.d.head(190,128,stem='down')
                elif kind=='earlier':self.d.head(135,116,stem='down')
                else:ET.SubElement(second,'accidental').text='sharp'
                self.render([(self.note('F3',2,'2','5',1),0,2),(second,0,2)])
                before=ET.tostring(self.root)
                self.run_check();self.assertEqual(ET.tostring(self.root),before)

    def test_round_clef_dot_does_not_break_note_sequence(self):
        self.d.head(140,140,filled=True);self.d.head(180,140,filled=True)
        self.d.cv2.circle(self.d.image,(121,126),4,0,-1)
        self.render([(self.note('C3',1,'2','5'),0,1),(self.note('B2',1,'2','5'),1,1)])
        audit=self.run_check()
        self.assertEqual(len(audit['headPitchCorrections']),1)

    def test_unreadable_prior_stem_preserves_alter_but_allows_visible_step(self):
        self.d.head(140,140,stem=None,filled=True);self.d.head(180,140,filled=True)
        self.render([(self.note('C3',1,'2','5'),0,1),(self.note('B2',1,'2','5'),1,1)])
        audit=self.run_check()
        self.assertEqual(len(audit['headPitchCorrections']),1)
        self.assertEqual(audit['alterationCorrections'],[])
        self.assertEqual([(n.findtext('pitch/step'),n.findtext('pitch/alter'))
                          for n in self.root.findall('./part/measure[@number="2"]/note')],[('C','0'),('C','0')])

    def test_solid_sequence_vetoes_explicit_natural_and_missing_head(self):
        self.d.head(140,140,filled=True);self.d.head(180,140,filled=True)
        first=self.note('C3',1,'2','5');ET.SubElement(first,'accidental').text='natural'
        self.render([(first,0,1),(self.note('B2',1,'2','5'),1,1)])
        before=ET.tostring(self.root);self.run_check();self.assertEqual(ET.tostring(self.root),before)
        first=self.note('C3',1,'2','5')
        self.render([(first,0,1),(self.note('B2',1,'2','5'),1,1),(self.note('D3',1,'2','5'),2,1)])
        before=ET.tostring(self.root);self.run_check();self.assertEqual(ET.tostring(self.root),before)

    def test_image_tie_merges_sound_without_changing_bar_or_other_voice(self):
        self.tie_case();audit = self.run_check()
        self.assertEqual(len(audit['tieCorrections']), 1)
        s = self.score();bass = [n for n in s['notes'] if n['measure'] == 2 and n['pitch'] == 57]
        self.assertEqual([(n['onset'], n['duration']) for n in bass], [([4, 1], [3, 1]), ([7, 1], [1, 1])])
        self.assertEqual(s['measures'][1]['duration'], [4, 1])
        from arrangement import playback_plan
        plan = [n for n in playback_plan(s, 0, 0)['notes'] if n['midi'] == 57]
        self.assertEqual(len(plan), 2)
        self.assertAlmostEqual(plan[0]['end']-plan[0]['start'], 3*60/110)
        self.assertAlmostEqual(plan[1]['start']-plan[0]['start'], 3*60/110)
        self.assertTrue(s['exact']);self.assertFalse(any('tie' in w.lower() for w in s['warnings']))
        self.assertEqual(len(self.root.findall('./part/measure/note/notations/slur')), 0)
        self.assertEqual(self.run_check()['tieCorrections'], [])

    def test_visible_missing_continuation_recovers_only_tied_quarter(self):
        self.tie_case(missing=True);before = len(self.root.findall('./part/measure/note'))
        audit = self.run_check()
        self.assertEqual(len(audit['heldNoteRecoveries']), 1)
        self.assertEqual(audit['heldNoteRecoveries'][0]['onset'], '2')
        self.assertEqual(len(self.root.findall('./part/measure/note')), before+1)
        s = self.score();bass = [n for n in s['notes'] if n['measure'] == 2 and n['pitch'] == 57]
        self.assertEqual([(n['onset'], n['duration']) for n in bass], [([4, 1], [3, 1]), ([7, 1], [1, 1])])
        self.assertEqual(s['measures'][1]['duration'], [4, 1])

    def test_no_tie_or_recovery_from_missing_arc_different_pitch_or_budget(self):
        for kind in ('arc', 'pitch', 'budget', 'extra', 'articulation'):
            with self.subTest(kind=kind):
                self.setUp();self.tie_case(missing=kind == 'extra', curve=kind != 'arc', wrong_second=kind == 'pitch')
                if kind == 'extra':self.d.head(194, 120, filled=True)
                if kind == 'articulation':
                    n = self.root.findall('./part/measure')[1].find("note[staff='2'][voice='5']")
                    ET.SubElement(ET.SubElement(n.find('notations'), 'articulations'), 'staccato')
                audit = self.run_check(limit=0 if kind == 'budget' else 200)
                self.assertEqual(audit['tieCorrections'], [])
                self.assertEqual(audit['heldNoteRecoveries'], [])

    def test_visible_beam_does_not_become_missing_plain_quarter(self):
        self.tie_case(missing=True)
        self.d.cv2.line(self.d.image, (185, 93), (208, 93), 0, 3)
        self.assertEqual(self.run_check()['heldNoteRecoveries'], [])

    def test_faint_flag_is_not_silently_treated_as_quarter(self):
        self.tie_case(missing=True)
        self.d.cv2.line(self.d.image, (185, 93), (197, 98), 220, 2)
        self.assertEqual(self.run_check()['heldNoteRecoveries'], [])

    def test_double_bar_strokes_and_multiple_initial_attribute_blocks_are_supported(self):
        self.tie_case()
        self.d.cv2.line(self.d.image, (113, 48), (113, 152), 0, 1)
        first = self.root.find('./part/measure');attr = first.find('attributes')
        extra = ET.Element('attributes');extra.append(attr.find('key'));attr.remove(attr.find('key'));first.insert(1, extra)
        self.assertEqual(len(self.run_check()['tieCorrections']), 1)

    def test_other_slur_numbers_and_existing_cross_bar_naturals_are_preserved(self):
        self.tie_case()
        first = self.root.findall('./part/measure')[1].find("note[staff='2'][voice='5']")
        ET.SubElement(first.find('notations'), 'slur', type='start', number='9')
        self.assertEqual(len(self.run_check()['tieCorrections']), 1)
        self.assertEqual([s.get('number') for s in self.root.findall('./part/measure/note/notations/slur')], ['9'])
        self.setUp();self.pitch_case()
        n = self.root.findall('./part/measure')[1].find('note')
        ET.SubElement(n, 'tie', type='stop')
        self.assertEqual(self.run_check()['alterationCorrections'], [])

    def test_short_horizontal_line_is_not_a_tie(self):
        self.tie_case(curve=False)
        self.d.cv2.line(self.d.image, (146, 111), (174, 111), 0, 1)
        self.assertEqual(self.run_check()['tieCorrections'], [])

    def pitch_case(self, wrong_height=False):
        y = 84 if wrong_height else 56
        self.d.head(140, y, stem='down');self.d.head(185, y, stem='down')
        name = 'E4' if wrong_height else 'D5';alter = 1 if wrong_height else 0
        self.render([(self.note(name, 2, alter=alter), 0, 2), (self.note(name, 2, alter=alter), 2, 2)])

    def natural(self, x=127, y=56, color=0):
        cv2 = self.d.cv2
        cv2.line(self.d.image, (x-2, y-7), (x-2, y+4), color, 1)
        cv2.line(self.d.image, (x+2, y-4), (x+2, y+7), color, 1)
        cv2.line(self.d.image, (x-2, y-2), (x+2, y-4), color, 1)
        cv2.line(self.d.image, (x-2, y+4), (x+2, y+2), color, 1)

    def test_repeated_hollow_heads_correct_height_and_key_not_just_remove_sharp(self):
        self.pitch_case(wrong_height=True);audit = self.run_check()
        self.assertEqual(len(audit['headPitchCorrections']), 2)
        self.assertEqual({item['to'] for item in audit['headPitchCorrections']}, {'D4'})
        self.assertEqual({n['pitch'] for n in self.score()['notes'] if n['measure'] == 2}, {63})

    def test_complete_repeated_heads_and_key_restore_missing_accidental(self):
        self.pitch_case();audit = self.run_check()
        self.assertEqual(len(audit['alterationCorrections']), 2)
        self.assertEqual({n['pitch'] for n in self.score()['notes'] if n['measure'] == 2}, {75})

    def test_local_natural_even_faint_vetoes_key_repair(self):
        for color in (0, 220):
            with self.subTest(color=color):
                self.setUp();self.pitch_case();self.natural(color=color)
                self.assertEqual(self.run_check()['alterationCorrections'], [])

    def test_no_guess_with_extra_head_unknown_clef_or_key_change(self):
        for kind in ('extra', 'clef', 'nontraditional', 'tuplet', 'bars', 'limit'):
            with self.subTest(kind=kind):
                self.setUp();self.pitch_case(wrong_height=True)
                if kind == 'extra':self.d.head(160, 84, stem='down')
                if kind == 'clef':self.root.find('./part/measure/attributes/clef/sign').text = 'C'
                if kind == 'nontraditional':ET.SubElement(self.root.find('./part/measure/attributes/key'), 'key-step').text = 'F'
                if kind == 'tuplet':ET.SubElement(self.root.findall('./part/measure')[1].find('note'), 'time-modification')
                if kind == 'bars':self.root.find('part').remove(self.root.findall('./part/measure')[0])
                audit = self.run_check(limit=1 if kind == 'limit' else 200)
                self.assertEqual(audit['headPitchCorrections'], [])


if __name__ == '__main__':unittest.main()
