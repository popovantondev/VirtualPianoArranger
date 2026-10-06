"""Shared arrangement and seconds plan without audio devices or user files."""
import copy
import json
import unittest
from arrangement import arrange, playback_plan, select_pitches, simplify_notes
from offline_piano import PianoBridge
from music_time import grouped_events


def score(notes, tempos=None):
    return {"format":1, "exact":True, "initial_tempo_explicit":True,
            "parts":[{"id":"P", "name":"Piano"}], "measures":[{"number":1,"onset":[0,1],"duration":[8,1]}],
            "duration":[8,1], "tempos":tempos or [{"onset":[0,1],"bpm":[120,1]}], "warnings":[],
            "notes":[{"id":str(i),"part_id":"P","voice":str(i),"staff":"1", "measure":1,
                      "pitch":p,"onset":[t,1],"duration":[d,1]} for i,(p,t,d) in enumerate(notes)]}


class ArrangementTests(unittest.TestCase):
    def test_boundaries_and_source_immutability(self):
        original=score([(35,0,1),(36,0,1),(96,0,1),(97,0,1)])
        before=copy.deepcopy(original)
        result=arrange(original,0,0)
        self.assertEqual([n["pitch"] for n in result["notes"]],[36,96])
        self.assertEqual(result["outside"],[(1,35),(1,97)])
        self.assertEqual(original,before)
        for shift in (-12,12):
            plan=playback_plan(original,shift,0)
            self.assertTrue(all(36<=n["midi"]<=96 for n in plan["notes"]))

    def test_duplicates_are_independent_sound_instances(self):
        result=arrange(score([(60,0,1),(60,0,3),(64,0,2)]),0,100)
        self.assertEqual(len(result["notes"]),3)
        self.assertEqual(result["attacks"][0]["notes"],[60,64])
        self.assertEqual(len(set(result["attacks"][0]["note_ids"])),3)
        plan=playback_plan(score([(60,0,1),(60,0,3)]),0,0)
        self.assertEqual([n["end"] for n in plan["notes"]],[0.5,1.5])

    def test_tempo_change_inside_note_and_initial_silence(self):
        plan=playback_plan(score([(60,1,4)], [{"onset":[0,1],"bpm":[120,1]},
                                               {"onset":[2,1],"bpm":[60,1]}]),0,0)
        self.assertEqual(plan["notes"][0]["start"],0.5)
        self.assertEqual(plan["notes"][0]["end"],4)
        self.assertEqual(plan["duration"],7)

    def test_simplification_steps_and_limits(self):
        pitches=list(range(48,60))
        previous=len(pitches)
        for v in range(101):
            selected=simplify_notes(pitches,v)
            self.assertLessEqual(len(selected),previous)
            self.assertEqual((selected[0],selected[-1]),(48,59))
            previous=len(selected)
        self.assertEqual(simplify_notes(pitches,10),pitches)
        self.assertEqual(simplify_notes(pitches,100),[48,59])

    def test_letter_render_plan_agree_in_all_layouts(self):
        import main
        original=score([(35,0,1),(60,0,2),(97,0,1),(64,3,1)])
        for layout in ("Русская","English","Deutsch"):
            text, warnings=main.render_events(grouped_events(original),0,layout,True,0)
            chosen=arrange(original,0,0)
            self.assertEqual(warnings,chosen["outside"])
            expected=main.render_events(chosen["attacks"],0,layout,True,0)[0]
            self.assertEqual(text,expected)
            self.assertEqual({n["midi"] for n in playback_plan(original,0,0)["notes"]},{60,64})

    def test_auto_transpose_honest_when_range_impossible(self):
        import main
        shift,outside,_=main.find_best_transposition(grouped_events(score([(25,0,1),(107,0,1)])),0,100)
        self.assertGreater(outside,0)
        self.assertTrue(-12<=shift<=12)

    def test_legacy_and_uncertain(self):
        self.assertEqual(playback_plan(None,0,0)["error"],"legacy")
        original=score([(60,0,1)]); original["exact"]=False
        self.assertEqual(playback_plan(original,0,0)["error"],"uncertain")

    def test_bridge_does_not_silently_accept_bad_plan(self):
        bridge=PianoBridge({},lambda:[])
        bridge.plan_provider=lambda:playback_plan(score([(60,0,1)]),0,0)
        valid=json.loads(bridge.plan()); self.assertEqual(valid["notes"][0]["midi"],60)
        for change in ({"midi":35},{"midi":True},{"start":float("nan")},{"end":-1}):
            bad=copy.deepcopy(valid); bad["notes"][0].update(change)
            bridge.plan_provider=lambda:bad
            self.assertEqual(json.loads(bridge.plan())["error"],"invalid")


if __name__=="__main__": unittest.main()
