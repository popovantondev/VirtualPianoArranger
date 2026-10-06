"""Generic rhythm/tie fixtures, not a transcription of an owner's music."""
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from music_time import read_musicxml
from omr_quality import prepare_result, promote_notated_ties, rhythm_report, result_warnings


def score_xml(lengths,meter=None):
    root=ET.Element("score-partwise");part=ET.SubElement(root,"part",id="P1")
    for index,length in enumerate(lengths,1):
        measure=ET.SubElement(part,"measure",number=str(index))
        if index==1:
            attributes=ET.SubElement(measure,"attributes")
            ET.SubElement(attributes,"divisions").text="3"
            if meter:
                time=ET.SubElement(attributes,"time")
                ET.SubElement(time,"beats").text=str(meter[0]);ET.SubElement(time,"beat-type").text=str(meter[1])
        note=ET.SubElement(measure,"note");pitch=ET.SubElement(note,"pitch")
        ET.SubElement(pitch,"step").text="C";ET.SubElement(pitch,"octave").text="4"
        ET.SubElement(note,"duration").text=str(length)
        ET.SubElement(note,"voice").text="1";ET.SubElement(note,"staff").text="1"
    return root


class QualityTests(unittest.TestCase):
    def test_verified_sixteenth_correction_is_not_reported_as_unavailable(self):
        with tempfile.TemporaryDirectory(prefix='vpa-quality-test-') as folder:
            path=Path(folder)/'result.musicxml';report=rhythm_report(score_xml([12],(4,4)))
            report['durationCorrections']=[{'measure':1,'from':'note_16','to':'note_4'}]
            path.with_suffix('.recognition.json').write_text(json.dumps({'quality':report}))
            for language,needle in [('Русский','шестнадцатая'),('English','sixteenth'),('Deutsch','Sechzehntel')]:
                self.assertIn(needle,result_warnings(path,1,language)[0])

    def test_explicit_meter_flags_without_changing_notes_or_time(self):
        root=score_xml([12,18],(4,4));before=ET.tostring(root)
        report=rhythm_report(root)
        self.assertEqual(report["suspectMeasures"],[{"part":1,"measure":2,"actual":[6,1],"expected":[4,1],"basis":"meter"}])
        self.assertEqual(ET.tostring(root),before)

    def test_common_length_is_only_a_warning_not_an_invented_meter(self):
        root=score_xml([12,12,18,12,12]);before=ET.tostring(root)
        report=rhythm_report(root)
        self.assertEqual(report["suspectMeasures"][0]["measure"],3)
        self.assertEqual(report["suspectMeasures"][0]["basis"],"common-duration")
        self.assertEqual(ET.tostring(root),before)
        self.assertEqual(rhythm_report(score_xml([12,18,12,18]))["suspectCount"],0)
        no_reference=rhythm_report(score_xml([12,18,12,18]))
        self.assertEqual(no_reference["unreferencedMeasures"],4);self.assertEqual(no_reference["checkedMeasures"],0)

    def test_compound_meter_pickup_and_changing_meter(self):
        root=score_xml([9,3,12],(6,8))
        root.find("part")[1].set("implicit","yes")
        attributes=ET.Element("attributes");time=ET.SubElement(attributes,"time")
        ET.SubElement(time,"beats").text="4";ET.SubElement(time,"beat-type").text="4"
        root.find("part")[2].insert(0,attributes)
        self.assertEqual(rhythm_report(root)["suspectCount"],0)

    def test_chords_backups_rests_and_fractional_durations(self):
        root=ET.fromstring('''<score-partwise><part id="P1"><measure number="1">
          <attributes><divisions>3</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
          <note><duration>12</duration></note><note><chord/><duration>12</duration></note>
          <backup><duration>12</duration></backup>
          <note><rest/><duration>2</duration></note><forward><duration>10</duration></forward>
        </measure></part></score-partwise>''')
        self.assertEqual(rhythm_report(root)["suspectCount"],0)

    def test_free_meter_is_not_mistaken_for_a_missing_time_signature(self):
        root=score_xml([12,12,12,12,18])
        attributes=root.find("./part/measure/attributes")
        ET.SubElement(ET.SubElement(attributes,"time"),"senza-misura")
        self.assertEqual(rhythm_report(root)["suspectCount"],0)

    def test_notated_ties_become_one_held_note_and_are_idempotent(self):
        root=score_xml([12,12],(4,4))
        for note,kind in zip(root.findall("./part/measure/note"),("start","stop")):
            ET.SubElement(ET.SubElement(note,"notations"),"tied",type=kind)
        with tempfile.TemporaryDirectory(prefix="vpa-quality-test-") as folder:
            path=Path(folder)/"result.musicxml";ET.ElementTree(root).write(path)
            self.assertEqual(prepare_result(path)["promotedTies"],2)
            self.assertEqual(prepare_result(path)["promotedTies"],0)
            result=read_musicxml(path)
            self.assertEqual(len(result["notes"]),1)
            self.assertEqual(result["notes"][0]["duration"],[8,1])
            tree=ET.parse(path)
            for note in tree.findall("./part/measure/note"):
                tags=[child.tag for child in note]
                self.assertLess(tags.index("duration"),tags.index("tie"));self.assertLess(tags.index("tie"),tags.index("voice"))

    def test_slurs_and_unsupported_marks_are_not_guessed_as_ties(self):
        root=score_xml([12,12],(4,4))
        for note,kind in zip(root.findall("./part/measure/note"),("start","stop")):
            ET.SubElement(ET.SubElement(note,"notations"),"slur",type=kind)
        self.assertEqual(promote_notated_ties(root),0)
        note=root.find("./part/measure/note")
        ET.SubElement(note.find("notations"),"tied",type="let-ring")
        self.assertEqual(promote_notated_ties(root),0)

    def test_rest_and_grace_marks_are_not_promoted(self):
        root=score_xml([12,12],(4,4));notes=root.findall("./part/measure/note")
        notes[0].remove(notes[0].find("pitch"));ET.SubElement(notes[0],"rest")
        ET.SubElement(notes[1],"grace")
        for note in notes:ET.SubElement(ET.SubElement(note,"notations"),"tied",type="start")
        self.assertEqual(promote_notated_ties(root),0)

    def test_result_does_not_rewrite_untied_xml_and_rejects_entities(self):
        with tempfile.TemporaryDirectory(prefix="vpa-quality-test-") as folder:
            path=Path(folder)/"result.musicxml";ET.ElementTree(score_xml([12,18],(4,4))).write(path)
            before=path.read_bytes();report=prepare_result(path)
            self.assertEqual(report["suspectCount"],1);self.assertEqual(path.read_bytes(),before)
            path.write_text('<!DOCTYPE score-partwise [<!ENTITY x "bad">]><score-partwise/>')
            with self.assertRaisesRegex(ValueError,"Unsafe"):prepare_result(path)

    def test_reports_are_bounded_localised_and_optional(self):
        with tempfile.TemporaryDirectory(prefix="vpa-quality-test-") as folder:
            path=Path(folder)/"result.musicxml";sidecar=path.with_suffix(".recognition.json")
            self.assertEqual(result_warnings(path,2,"Русский"),[])
            report=rhythm_report(score_xml([12,18],(4,4)));sidecar.write_text(json.dumps({"quality":report}))
            for language,needle in [("Русский","страница 2"),("English","page 2"),("Deutsch","Seite 2")]:
                warnings=result_warnings(path,2,language)
                self.assertEqual(len(warnings),1);self.assertIn(needle,warnings[0]);self.assertLess(len(warnings[0]),1000)
            for invalid in ({"quality":[]},{"quality":{"version":1,"suspectCount":True,"suspectMeasures":[]}}):
                sidecar.write_text(json.dumps(invalid));self.assertIn("недоступна",result_warnings(path,1,"Русский")[0])
            sidecar.write_text("x"*65537);self.assertIn("unavailable",result_warnings(path,1,"English")[0])

    def test_image_verified_duration_audit_is_localised_and_saved_with_warnings(self):
        with tempfile.TemporaryDirectory(prefix="vpa-quality-test-") as folder:
            path=Path(folder)/"result.musicxml";sidecar=path.with_suffix(".recognition.json")
            report=rhythm_report(score_xml([12,12],(4,4)))
            report["durationCorrections"]=[{"measure":2,"from":"note_1","to":"note_2","reason":"hollow-head-attached-stem"}]
            sidecar.write_text(json.dumps({"quality":report}))
            for language,needle in [("Русский","половинная"),("English","half"),("Deutsch","halbe")]:
                notice=result_warnings(path,1,language)
                self.assertEqual(len(notice),1);self.assertIn(needle,notice[0])
            report["durationCorrections"]=[{"measure":True}];sidecar.write_text(json.dumps({"quality":report}))
            self.assertIn("недоступна",result_warnings(path,1,"Русский")[0])

    def test_filled_head_and_independent_timing_notices_are_distinct_and_bounded(self):
        with tempfile.TemporaryDirectory(prefix="vpa-quality-test-") as folder:
            path=Path(folder)/"result.musicxml";sidecar=path.with_suffix(".recognition.json")
            report=rhythm_report(score_xml([12,12],(4,4)))
            report["durationCorrections"]=[{"measure":2,"from":"note_2","to":"note_4"}]
            report["timingCorrections"]=[{"measure":2,"movedNotes":3}]
            sidecar.write_text(json.dumps({"quality":report}))
            for language,quarter,timing in (("Русский","четверть","синхронизация"),("English","quarter","synchronization"),("Deutsch","Viertelnote","Synchronisation")):
                notices=result_warnings(path,1,language);self.assertEqual(len(notices),2)
                self.assertIn(quarter,notices[0]);self.assertIn(timing,notices[1])
            for invalid in ([{"measure":True,"movedNotes":3}],[{"measure":2,"movedNotes":True}],[{"measure":2,"movedNotes":1}]*201):
                report["timingCorrections"]=invalid;sidecar.write_text(json.dumps({"quality":report}))
                self.assertIn("unavailable",result_warnings(path,1,"English")[0])

    def test_missing_rhythm_reference_is_not_silently_reported_as_zero_errors(self):
        with tempfile.TemporaryDirectory(prefix="vpa-quality-test-") as folder:
            path=Path(folder)/"result.musicxml";report=rhythm_report(score_xml([12,18,12,18]))
            path.with_suffix(".recognition.json").write_text(json.dumps({"quality":report}))
            self.assertIn("Zero findings",result_warnings(path,1,"English")[0])

    def test_pitch_recovery_and_eighth_audits_are_localised_and_bounded(self):
        with tempfile.TemporaryDirectory(prefix="vpa-quality-test-") as folder:
            path=Path(folder)/"result.musicxml";sidecar=path.with_suffix(".recognition.json")
            report=rhythm_report(score_xml([12,12],(4,4)))
            report["durationCorrections"]=[{"measure":2,"from":"note_8","to":"note_4"}]
            report["pitchCorrections"]=[{"measure":2,"from":"A4","to":"F4"}]
            report["recoveredNotes"]=[{"measure":2,"pitch":"C3","rhythm":"note_8"}]
            sidecar.write_text(json.dumps({"quality":report}))
            for language,word in (("Русский","восстановлено"),("English","recovered"),("Deutsch","ergänzt")):
                notices=result_warnings(path,3,language);self.assertEqual(len(notices),3);self.assertIn(word,notices[2])
            for field in ("pitchCorrections","recoveredNotes"):
                previous=report[field]
                for bad in ([{"measure":True}],[{"measure":2}]*201):
                    report[field]=bad;sidecar.write_text(json.dumps({"quality":report}))
                    self.assertIn("unavailable",result_warnings(path,1,"English")[0])
                report[field]=previous

    def test_notation_evidence_is_localised_bounded_and_optional(self):
        fields=("headPitchCorrections","alterationCorrections","tieCorrections","heldNoteRecoveries","omittedAttackRecoveries")
        with tempfile.TemporaryDirectory(prefix="vpa-quality-test-") as folder:
            path=Path(folder)/"result.musicxml";sidecar=path.with_suffix(".recognition.json")
            report=rhythm_report(score_xml([12,12],(4,4)))
            for field in fields:report[field]=[{"measure":2}]
            sidecar.write_text(json.dumps({"quality":report}))
            for language,needle in (("Русский","удержания"),("English","held-note"),("Deutsch","Haltebögen")):
                notices=result_warnings(path,1,language)
                self.assertEqual(len(notices),len(fields));self.assertIn(needle,notices[2])
            for field in fields:
                for bad in ([{"measure":True}],[{"measure":2}]*201):
                    report[field]=bad;sidecar.write_text(json.dumps({"quality":report}))
                    self.assertIn("unavailable",result_warnings(path,1,"English")[0])
                report[field]=[{"measure":2}]

    def test_unresolved_accidentals_warn_without_claiming_correction(self):
        with tempfile.TemporaryDirectory(prefix="vpa-quality-test-") as folder:
            path=Path(folder)/"result.musicxml";sidecar=path.with_suffix(".recognition.json")
            report=rhythm_report(score_xml([12,12],(4,4)))
            report['unresolvedAlterations']=[{'measure':2}]
            sidecar.write_text(json.dumps({'quality':report}))
            for language,needle in (("Русский","догадкой"),("English","guess"),("Deutsch","Vermutung")):
                notices=result_warnings(path,1,language)
                self.assertEqual(len(notices),1);self.assertIn(needle,notices[0])
            report['unresolvedAlterations']=[{'measure':True}]
            sidecar.write_text(json.dumps({'quality':report}))
            self.assertIn('unavailable',result_warnings(path,1,'English')[0])

    def test_geometry_audit_is_explicit_and_rejected_candidates_are_not_success(self):
        with tempfile.TemporaryDirectory(prefix="vpa-quality-test-") as folder:
            path=Path(folder)/"result.musicxml";sidecar=path.with_suffix(".recognition.json")
            report=rhythm_report(score_xml([12,12],(4,4)))
            report["geometryAlternatives"]=[{"system":1,"accepted":False}]
            sidecar.write_text(json.dumps({"quality":report}));self.assertEqual(result_warnings(path,1,"English"),[])
            report["geometryAlternatives"]=[{"system":1,"accepted":True}]
            sidecar.write_text(json.dumps({"quality":report}));self.assertIn("still required",result_warnings(path,1,"English")[0])
            for bad in ([{"system":True,"accepted":True}],[{"system":1,"accepted":1}],[{"system":1,"accepted":False}]*3):
                report["geometryAlternatives"]=bad;sidecar.write_text(json.dumps({"quality":report}))
                self.assertIn("unavailable",result_warnings(path,1,"English")[0])

    def test_unmatched_heads_and_hollow_chords_warn_bounded_and_localised(self):
        with tempfile.TemporaryDirectory(prefix="vpa-quality-test-") as folder:
            path=Path(folder)/"result.musicxml";sidecar=path.with_suffix(".recognition.json")
            report=rhythm_report(score_xml([12,12],(4,4)))
            for field,valid in (("unmatchedSolidHeads",{"measure":2,"count":1}),
                                ("unresolvedHollowChords",{"measure":2,"recognizedCount":3,"detectedCount":2})):
                report[field]=[valid];sidecar.write_text(json.dumps({"quality":report}))
                for language,needle in (("Русский","догадкой"),("English","guess"),("Deutsch","geraten")):
                    notices=result_warnings(path,1,language)
                    self.assertEqual(len(notices),1);self.assertIn(needle,notices[0])
                for key in valid:
                    report[field]=[{**valid,key:True}];sidecar.write_text(json.dumps({"quality":report}))
                    self.assertIn("unavailable",result_warnings(path,1,"English")[0])
                report[field]=[valid]*201;sidecar.write_text(json.dumps({"quality":report}))
                self.assertIn("unavailable",result_warnings(path,1,"English")[0])
                del report[field]

    def test_whole_chord_correction_is_localised_and_rejects_invalid_members(self):
        with tempfile.TemporaryDirectory(prefix="vpa-quality-test-") as folder:
            path=Path(folder)/"result.musicxml";sidecar=path.with_suffix(".recognition.json")
            report=rhythm_report(score_xml([12,12],(4,4)))
            entry={"measure":2,"notesBefore":3,"notesAfter":2,"removedPitches":["B4","G4"],"addedPitches":["C4"]}
            report["chordCompositionCorrections"]=[entry];sidecar.write_text(json.dumps({"quality":report}))
            for language,needle in (("Русский","составы целых аккордов"),("English","whole-note chord"),("Deutsch","Zusammensetzungen")):
                notices=result_warnings(path,1,language)
                self.assertEqual(len(notices),1);self.assertIn(needle,notices[0])
            for bad in ({"measure":True},{"notesBefore":True},{"notesAfter":5},
                        {"removedPitches":["B4"]*3},{"addedPitches":["H4"]},{"addedPitches":"C4"}):
                report["chordCompositionCorrections"]=[{**entry,**bad}]
                sidecar.write_text(json.dumps({"quality":report}))
                self.assertIn("unavailable",result_warnings(path,1,"English")[0])


if __name__=="__main__":unittest.main()
