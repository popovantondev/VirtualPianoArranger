"""Synthetic two-staff rhythm; no private musical reference fixture."""
from copy import deepcopy
from fractions import Fraction
import unittest
import xml.etree.ElementTree as ET

from omr_timing import retime_independent_staves,_xml_notes


class Token:
    def __init__(self,rhythm,pitch=".",position="."):
        self.rhythm=rhythm;self.pitch=pitch;self.position=position
    def get_duration(self):
        kern=self.rhythm.split("_")[1];base=int(kern.rstrip("."));duration=Fraction(1,base)
        for index in range(kern.count(".")):duration+=Fraction(1,base*2**(index+1))
        return type("Duration",(),{"fraction":duration})()


def fixture(ending="2",lower_rest=False):
    n=lambda rhythm,pitch,staff:Token(rhythm,pitch,"upper" if staff==1 else "lower")
    rest="rest_4." if lower_rest else "note_4."
    groups=[[n("note_4","C5",1),n(rest,"_" if lower_rest else "C3",2)], [n("note_4","D5",1)],
            [n("rest_8" if lower_rest else "note_8","_" if lower_rest else "C3",2)],
            [n("note_"+ending,"E5",1),n("note_"+ending,"D3",2)]]
    return fixture_groups(groups)


def fixture_groups(groups):
    tokens=[]
    for group in groups:
        for index,symbol in enumerate(group):
            if index:tokens.append(Token("chord"))
            tokens.append(symbol)
    tokens+=[Token("barline"),Token("newline")]
    root=ET.Element("score-partwise");part=ET.SubElement(root,"part",id="P1");measure=ET.SubElement(part,"measure",number="1")
    attributes=ET.SubElement(measure,"attributes");ET.SubElement(attributes,"divisions").text="2"
    cursor=Fraction(0);time=Fraction(0)
    for group in groups:
        durations=[symbol.get_duration().fraction*4 for symbol in group]
        for symbol,duration in zip(group,durations):
            delta=time-cursor
            if delta:
                motion=ET.SubElement(measure,"forward" if delta>0 else "backup")
                ET.SubElement(motion,"duration").text=str(int(abs(delta)*2))
            note=ET.SubElement(measure,"note")
            if symbol.rhythm.startswith("rest"):ET.SubElement(note,"rest")
            else:
                pitch=ET.SubElement(note,"pitch");ET.SubElement(pitch,"step").text=symbol.pitch[0];ET.SubElement(pitch,"octave").text=symbol.pitch[1]
            ET.SubElement(note,"duration").text=str(int(duration*2));ET.SubElement(note,"voice").text="1" if symbol.position=="upper" else "5"
            ET.SubElement(note,"staff").text="1" if symbol.position=="upper" else "2"
            cursor=time+duration
        time+=min(durations)
    return root,tokens


class TimingTests(unittest.TestCase):
    def test_separate_eighth_enters_at_one_and_a_half_not_two(self):
        root,tokens=fixture();before=deepcopy(root)
        audit=retime_independent_staves(root,tokens);self.assertEqual(audit[0]["duration"],[4,1])
        notes=_xml_notes(root.find("./part/measure"),Fraction(2))
        bass=[(onset,duration) for note,key,onset,duration in notes if key[0]=="2"]
        self.assertEqual(bass,[(Fraction(0),Fraction(3,2)),(Fraction(3,2),Fraction(1,2)),(Fraction(2),Fraction(2))])
        original=_xml_notes(before.find("./part/measure"),Fraction(2))
        payload=lambda note:ET.tostring(next((child for child in note if child.tag in ("pitch","rest")),ET.Element("missing")))
        self.assertCountEqual([(payload(n),k,d) for n,k,_,d in notes],[(payload(n),k,d) for n,k,_,d in original])
        after=ET.tostring(root);self.assertEqual(retime_independent_staves(root,tokens),[]);self.assertEqual(ET.tostring(root),after)

    def test_six_quarters_is_not_forced_into_four(self):
        root,tokens=fixture(ending="1")
        audit=retime_independent_staves(root,tokens);self.assertEqual(audit[0]["duration"],[6,1])
        self.assertEqual(max(t+d for _,_,t,d in _xml_notes(root.find("./part/measure"),Fraction(2))),6)

    def test_explicit_rests_are_retained_and_not_invented(self):
        root,tokens=fixture(lower_rest=True);before=len(root.findall("./part/measure/note/rest"))
        self.assertEqual(len(retime_independent_staves(root,tokens)),1)
        self.assertEqual(len(root.findall("./part/measure/note/rest")),before)

    def test_pitched_rest_token_matches_existing_xml_note_not_a_new_rest(self):
        root,tokens=fixture();bass=next(t for t in tokens if t.rhythm=="note_8")
        bass.rhythm="rest_8"
        self.assertEqual(len(retime_independent_staves(root,tokens)),1)
        self.assertEqual(len(root.findall("./part/measure/note/rest")),0)

    def test_image_verified_held_voice_advances_separately_from_melody(self):
        n=lambda r,p,s="upper":Token(r,p,s)
        groups=[[n("note_4","G5"),n("note_2","C5"),n("note_1","C3","lower")],
                [n("note_4","A5")],[n("note_2","C5")],[n("note_4","B5")],[n("note_4","D6")]]
        root,tokens=fixture_groups(groups);before=ET.tostring(root)
        self.assertEqual(retime_independent_staves(root,tokens),[]);self.assertEqual(ET.tostring(root),before)
        for t in tokens:
            if t.position=="upper":t._vpa_polyphonic=True
        audit=retime_independent_staves(root,tokens);self.assertEqual(audit[0]["duration"],[4,1])
        events=_xml_notes(root.find("./part/measure"),Fraction(2))
        self.assertEqual([(onset,d) for n,k,onset,d in events if k[1]=="C5"],[(0,2),(2,2)])
        self.assertTrue(all(n.findtext("voice")=="2" for n,k,_,_ in events if k[1]=="C5"))
        self.assertEqual([onset for n,k,onset,d in events if k[0]=="1" and k[1]!="C5"],[0,1,2,3])
        self.assertCountEqual([k for _,k,_,_ in events],[k for _,k,_,_ in _xml_notes(ET.fromstring(before).find("./part/measure"),Fraction(2))])

    def test_crossing_registers_do_not_enable_duration_only_voice_split(self):
        n=lambda r,p,s="upper":Token(r,p,s)
        root,tokens=fixture_groups([[n("note_4","C5"),n("note_2","G5"),n("note_1","C3","lower")],
            [n("note_4","A5")],[n("note_2","G5")],[n("note_4","B5")],[n("note_4","D6")]])
        for t in tokens:
            if t.position=="upper":t._vpa_polyphonic=True
        before=ET.tostring(root);self.assertEqual(retime_independent_staves(root,tokens),[]);self.assertEqual(ET.tostring(root),before)

    def test_partial_held_voice_keeps_valid_staff_clocks(self):
        root,tokens=fixture();measure=root.find("./part/measure")
        first=measure.find("note");held=deepcopy(first)
        held.find("pitch/step").text="A";held.find("pitch/octave").text="4"
        held.find("duration").text="4";held.find("voice").text="2";held.insert(0,ET.Element("chord"))
        measure.insert(list(measure).index(first)+1,held)
        tokens[1:1]=[Token("chord"),Token("note_2","A4","upper")]
        for t in tokens:
            if t.position=="upper":t._vpa_polyphonic=True
        audit=retime_independent_staves(root,tokens)
        self.assertEqual(audit[0]["duration"],[4,1]);self.assertEqual(audit[0]["reason"],"independent-staff-clocks")
        self.assertEqual(len(root.findall("./part/measure/note")),7)

    def test_same_duration_chords_preserve_stream_and_notation(self):
        root,tokens=fixture();measure=root.find("./part/measure");first=measure.find("note")
        first.set("color","#000000");ET.SubElement(ET.SubElement(first,"notations"),"slur",type="start",number="1")
        clone=deepcopy(first);clone.find("pitch/step").text="G";clone.insert(0,ET.Element("chord"));measure.insert(list(measure).index(first)+1,clone)
        tokens[1:1]=[Token("chord"),Token("note_4","G5","upper")]
        self.assertEqual(len(retime_independent_staves(root,tokens)),1)
        chord=next(n for n in root.findall("./part/measure/note") if n.find("chord") is not None)
        self.assertEqual(chord.findtext("voice"),"1");self.assertEqual(chord.get("color"),"#000000")
        self.assertIsNotNone(chord.find("notations/slur"))

    def test_missing_tokens_cross_staff_conflict_tuplets_and_grace_are_not_guessed(self):
        for kind in ("missing","conflict","tuplet","grace","single"):
            with self.subTest(kind=kind):
                root,tokens=fixture()
                if kind=="missing":tokens.pop(3)
                if kind=="conflict":tokens[2].rhythm="note_2"
                if kind=="tuplet":tokens[0].rhythm="note_6"
                if kind=="grace":root.find("./part/measure/note").insert(0,ET.Element("grace"))
                if kind=="single":tokens=[t for t in tokens if t.position!="lower"]
                before=ET.tostring(root);self.assertEqual(retime_independent_staves(root,tokens),[]);self.assertEqual(ET.tostring(root),before)

    def test_positioned_direction_and_nonintegral_division_are_preserved_by_skipping(self):
        root,tokens=fixture();measure=root.find("./part/measure")
        measure.insert(2,ET.Element("direction"));before=ET.tostring(root)
        self.assertEqual(retime_independent_staves(root,tokens),[]);self.assertEqual(ET.tostring(root),before)
        root,tokens=fixture();root.find("./part/measure/attributes/divisions").text="3"
        before=ET.tostring(root);self.assertEqual(retime_independent_staves(root,tokens),[]);self.assertEqual(ET.tostring(root),before)


if __name__=="__main__":unittest.main()
