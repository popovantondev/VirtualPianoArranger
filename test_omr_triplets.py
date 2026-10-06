"""Synthetic printed tuplet evidence; no owner's score in fixtures."""
import unittest
from fractions import Fraction
from unittest.mock import patch
import cv2
import numpy as np
from homr.transformer.vocabulary import EncodedSymbol,SymbolDuration
from omr_duration import _triplet_beam,verify_triplet_durations


class TripletTests(unittest.TestCase):
    def setUp(self):
        self.gray=np.full((270,300),255,np.uint8)
        self.heads=[(70,115,63,77),(110,110,103,117),(150,115,143,157)]
        self.stems=[(77,70,115),(117,70,110),(157,70,115)]
        for x,y0,y1 in self.stems:cv2.line(self.gray,(x,y0),(x,y1),0,2)
        for x,y,a,b in self.heads:cv2.ellipse(self.gray,(x,y),(7,4),-15,0,360,0,-1)
        for y in (70,77):cv2.line(self.gray,(77,y),(157,y),0,3)
        cv2.putText(self.gray,'3',(111,61),cv2.FONT_HERSHEY_SIMPLEX,.45,0,1)
        self.reader=lambda crop:('3',.999)

    def bracket(self):
        cv2.line(self.gray,(77,50),(107,50),0,1)
        cv2.line(self.gray,(124,50),(157,50),0,1)
        for x in (77,157):cv2.line(self.gray,(x,50),(x,55),0,1)

    def test_number_beam_count_and_both_bracket_arms(self):
        evidence=_triplet_beam(self.gray,self.heads,self.stems,10,self.reader)
        self.assertEqual(evidence['beams'],2);self.assertFalse(evidence['bracket'])
        self.bracket()
        self.assertTrue(_triplet_beam(self.gray,self.heads,self.stems,10,self.reader)['bracket'])
        self.assertIsNone(_triplet_beam(self.gray,self.heads,self.stems,10,lambda crop:('3',.8)))
        self.assertIsNone(_triplet_beam(self.gray,self.heads,self.stems,10,lambda crop:('5',1)))
        self.gray[68:81,90:95]=255
        self.assertIsNone(_triplet_beam(self.gray,self.heads,self.stems,10,self.reader))

    def symbols(self):
        s=lambda rhythm,pitch='.',position='.':EncodedSymbol(rhythm=rhythm,pitch=pitch,position=position,lift='_',articulation='_',slur='_')
        return [s('clef_G2',position='upper'),s('clef_F4',position='lower'),
                s('note_16','G4','upper'),s('note_16','A4','upper'),s('note_16','G4','upper'),s('barline'),s('newline')]

    def check(self,symbols):
        systems=[(30,260,[85,95,105,115,125,175,185,195,205,215])]
        with patch('omr_duration._filled_heads',return_value=self.heads),patch('omr_duration._image_evidence',return_value=([],self.stems,[30,260])):
            return verify_triplet_durations(self.gray,systems,symbols,self.reader)

    def test_lone_fingering_is_not_a_tuplet_and_explicit_tuplets_survive(self):
        symbols=self.symbols();self.assertEqual(self.check(symbols)[1],[])
        self.bracket();result,audit=self.check(symbols)
        self.assertEqual(len(audit),1)
        self.assertEqual([s.get_duration().fraction for s in result[2:5]],[Fraction(1,24)]*3)
        self.assertEqual([s.get_duration().fraction for s in symbols[2:5]],[Fraction(1,16)]*3)
        self.assertEqual(self.check(result)[1],[])
        symbols[2]._duration=SymbolDuration(Fraction(1,16),0,5,4,16)
        self.assertEqual(self.check(symbols)[1],[])

    def test_xml_has_exact_divisions_and_three_to_two_metadata(self):
        from homr.music_xml_generator import generate_xml,XmlGeneratorArguments
        self.bracket();symbols,audit=self.check(self.symbols());self.assertTrue(audit)
        import tempfile
        from pathlib import Path
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory(prefix='vpa-triplet-test-') as folder:
            path=Path(folder)/'synthetic.musicxml'
            generate_xml(XmlGeneratorArguments(False,None,None),[symbols],'').write(str(path))
            root=ET.parse(path).getroot()
        notes=root.findall('./part/measure/note')
        divisions=int(root.findtext('./part/measure/attributes/divisions'))
        self.assertEqual([Fraction(int(n.findtext('duration')),divisions) for n in notes],[Fraction(1,6)]*3)
        self.assertEqual([n.findtext('time-modification/actual-notes') for n in notes],['3']*3)
        self.assertEqual([n.findtext('time-modification/normal-notes') for n in notes],['2']*3)

    def test_other_staff_chord_does_not_hide_melody_but_same_staff_chord_is_rejected(self):
        self.bracket();symbols=self.symbols()
        chord=EncodedSymbol(rhythm='chord')
        bass=EncodedSymbol(rhythm='note_1',pitch='C3',position='lower')
        symbols[3:3]=[chord,bass]
        self.assertEqual(len(self.check(symbols)[1]),1)
        symbols=self.symbols();symbols.insert(3,chord)
        self.assertEqual(self.check(symbols)[1],[])

    def test_already_encoded_tuplets_retime_both_staves_without_duration_edits(self):
        import tempfile
        from pathlib import Path
        import xml.etree.ElementTree as ET
        from homr.music_xml_generator import generate_xml,XmlGeneratorArguments
        from omr_timing import retime_independent_staves,_xml_notes
        for kern,count in ((12,12),(24,24)):
            s=lambda r,p='.',pos='.':EncodedSymbol(rhythm=r,pitch=p,position=pos,lift='_',articulation='_',slur='_')
            symbols=[s('clef_G2',pos='upper'),s('chord'),s('clef_F4',pos='lower'),
                     s(f'note_{kern}','C5','upper'),s('chord'),s('rest_1','_','lower')]
            symbols += [s(f'note_{kern}','C5','upper') for _ in range(count-1)]+[s('barline'),s('newline')]
            with tempfile.TemporaryDirectory(prefix='vpa-triplet-clock-test-') as folder:
                path=Path(folder)/'synthetic.musicxml'
                generate_xml(XmlGeneratorArguments(False,None,None),[symbols],'').write(str(path))
                root=ET.parse(path).getroot()
            m=root.find('./part/measure');division=Fraction(m.findtext('attributes/divisions'))
            # Recreate a sequential-staves serialization defect explicitly;
            # the vendor can already align this simple synthetic engraving.
            for child in list(m):
                if child.tag in ('backup','forward'):m.remove(child)
                if child.tag=='note':
                    for chord in child.findall('chord'):child.remove(chord)
            original=[(key,d) for _,key,_,d in _xml_notes(m,division)]
            audit=retime_independent_staves(root,symbols)
            self.assertTrue(audit);self.assertEqual(audit[0]['duration'],[4,1])
            after=_xml_notes(root.find('./part/measure'),division)
            self.assertCountEqual(original,[(key,d) for _,key,_,d in after])
            self.assertEqual(max(t+d for _,_,t,d in after),4)
            self.assertEqual(len(root.findall('./part/measure/note/rest')),1)
            self.assertEqual(retime_independent_staves(root,symbols),[])


if __name__=='__main__':unittest.main()
