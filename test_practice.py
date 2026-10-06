import copy
import json
import unittest
from practice import practice_score
from docs.design.preview_dark import demo_score
from music_time import grouped_events, validate_score, merge_scores
from project_io import validate_project
from offline_piano import PianoBridge


class PracticeTests(unittest.TestCase):
    def test_accompaniment_fullness_is_monotonic_preserves_melody_and_source(self):
        from test_arrangement import score
        from music_time import rational
        source=score([(48,0,2),(60,0,1),(64,0,1),(67,0,1),(52,2,2),(64,2,1),(67,2,1)])
        before=copy.deepcopy(source)
        for mode in ('keyboard','balanced','musical'):
            full=practice_score(source,mode,0,100)
            previous=set()
            for fullness in (0,25,50,75,100):
                result=practice_score(source,mode,0,fullness);validate_score(result)
                ids={n['id'] for n in result['notes']}
                self.assertTrue(previous<=ids);previous=ids
                events=grouped_events(result)
                self.assertTrue(all(max(e['notes'])==67 for e in events))
                self.assertTrue(all(len({p%12 in (1,3,6,8,10) for p in e['notes']})==1 for e in events))
                self.assertEqual(result['tempos'],source['tempos']);self.assertEqual(result['duration'],source['duration'])
                originals={n['id']:n for n in source['notes']}
                for note in result['notes']:
                    self.assertEqual(note['pitch'],originals[note['id']]['pitch'])
                    self.assertEqual(rational(note['duration']),rational(originals[note['id']]['duration']))
            self.assertLess(len(practice_score(source,mode,0,0)['notes']),len(full['notes']))
            self.assertEqual([e['notes'] for e in grouped_events(practice_score(source,mode,0,0))],[[67],[67]])
        self.assertEqual(source,before)

    def test_balanced_retains_some_bass_without_fast_double_attacks(self):
        from test_arrangement import score
        source=score([(48,0,2),(60,0,1),(64,0,1),(50,1,1),(62,1,1),(52,2,2),(64,2,1),(53,3,1),(65,3,1)])
        before=copy.deepcopy(source)
        result=practice_score(source,'balanced',0);validate_score(result)
        events=grouped_events(result)
        self.assertEqual([e['notes'] for e in events],[[48,64],[62],[52,64],[65]])
        self.assertEqual(source,before)
        for shift in range(-12,13):
            events=grouped_events(practice_score(source,'balanced',shift))
            self.assertTrue(all(len(e['notes'])<=2 for e in events))
            self.assertTrue(all(len({(p+shift)%12 in (1,3,6,8,10) for p in e['notes']})==1 for e in events))

    def test_keyboard_mode_keeps_one_modifier_group_at_requested_shift(self):
        from test_arrangement import score
        source=score([(60,0,1),(61,0,1),(64,0,2),(65,3,1),(66,3,1)])
        before=copy.deepcopy(source)
        for shift in range(-12,13):
            result=practice_score(source,'keyboard',shift);validate_score(result)
            for event in grouped_events(result):
                self.assertEqual(len({(p+shift)%12 in (1,3,6,8,10) for p in event['notes']}),1)
            self.assertEqual(result['duration'],source['duration'])
            self.assertEqual(result['tempos'],source['tempos'])
        self.assertEqual(source,before)
        self.assertIs(practice_score(source,'off'),source)

    def test_single_and_upper_preserve_source_and_time(self):
        source=demo_score();old=copy.deepcopy(source)
        for mode in("single","upper"):
            result=practice_score(source,mode);validate_score(result)
            self.assertTrue(all(len(e["notes"])==1 for e in grouped_events(result)))
            self.assertEqual(result["tempos"],source["tempos"])
            self.assertLess(len(result["notes"]),len(source["notes"]))
        self.assertEqual({n["staff"] for n in practice_score(source,"upper")["notes"]},{"1"})
        self.assertEqual(source,old)

    def test_upper_keeps_every_continuation_page_and_normal_restores_source(self):
        source=merge_scores([demo_score(),demo_score(),demo_score()]);old=copy.deepcopy(source)
        result=practice_score(source,"upper");validate_score(result)
        self.assertEqual({n["part_id"].split(":")[0] for n in result["notes"]},{"page1","page2","page3"})
        self.assertEqual(result["duration"],source["duration"])
        self.assertEqual(result["tempos"],source["tempos"])
        self.assertIs(practice_score(source,"normal"),source)
        self.assertEqual(source,old)

    def test_invalid_optional_project_fields(self):
        base={"version":8,"events":[]}
        for key,value in(("piano_shift",99),("link_piano_shift",1),("practice_mode","invented")):
            with self.assertRaises(ValueError):validate_project({**base,key:value})

    def test_sounding_and_display_ranges_are_validated_separately(self):
        bridge=PianoBridge({},lambda:[])
        base={"version":1,"duration":1,"notes":[{"id":"n","midi":24,"displayMidi":36,"start":0,"end":1}]}
        bridge.plan_provider=lambda:base
        self.assertEqual(json.loads(bridge.plan())["notes"][0]["midi"],24)
        for patch in ({"midi":108,"displayMidi":96},{"midi":109},{"midi":20},{"displayMidi":35},{"displayMidi":True}):
            trial=copy.deepcopy(base);trial["notes"][0].update(patch);bridge.plan_provider=lambda:trial
            result=json.loads(bridge.plan())
            if patch.get("midi")==108:self.assertEqual(result["notes"][0]["midi"],108)
            else:self.assertEqual(result["error"],"invalid")


if __name__=="__main__":unittest.main()
