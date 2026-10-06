"""Synthetic MusicXML, persistence and isolated Qt integration checks."""
import copy
import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from music_time import read_musicxml, merge_scores, grouped_events, rational, validate_score
import project_io


def note(step="C", duration=1, voice="1", extra="", staff="1"):
    return (f"<note>{extra}<pitch><step>{step}</step><octave>4</octave></pitch>"
            f"<duration>{duration}</duration><voice>{voice}</voice><staff>{staff}</staff></note>")


ATTR = "<attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>"


class MusicTimeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "score.xml"

    def parse(self, body, parts=None):
        # Test fixtures only; no user documents.
        if parts is None:
            parts = f'<part id="P1">{body}</part>'
        self.path.write_text(f'<score-partwise><part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>{parts}</score-partwise>', encoding="utf-8")
        return read_musicxml(self.path)

    def test_chords_voices_and_forward(self):
        score = self.parse('<measure number="1">' + ATTR + note(duration=2) + note("E", 1, extra="<chord/>") +
                           '<backup><duration>2</duration></backup>' + note("G", 1, "2", staff="2") +
                           '<forward><duration>2</duration></forward>' + note("D", 1, "2", staff="2") + '</measure>')
        self.assertEqual([(n["pitch"], n["onset"], n["duration"]) for n in score["notes"]],
                         [(60, [0, 1], [2, 1]), (64, [0, 1], [1, 1]), (67, [0, 1], [1, 1]), (62, [3, 1], [1, 1])])
        self.assertEqual(grouped_events(score)[0]["notes"], [60, 64, 67])
        self.assertTrue(score["exact"])

    def test_divisions_pickup_and_part_alignment(self):
        p1 = '<measure implicit="yes">' + ATTR + note(duration=1) + '</measure><measure>' + note("D", 1) + '</measure>'
        p2 = '<measure implicit="yes">' + ATTR + note("G", 2) + '</measure><measure><attributes><divisions>3</divisions></attributes>' + note("E", 1) + note("F", 2) + '</measure>'
        score = self.parse("", f'<part id="P1">{p1}</part><part id="P2">{p2}</part>')
        self.assertEqual(score["measures"][0]["duration"], [2, 1])
        self.assertEqual(score["duration"], [6, 1])
        notes = {n["pitch"]: n for n in score["notes"]}
        self.assertEqual(notes[62]["onset"], [2, 1])
        self.assertEqual(notes[65]["onset"], [7, 3])
        self.assertEqual(notes[64]["duration"], [1, 3])

    def test_ties_independent_streams(self):
        score = self.parse('<measure>' + ATTR + note(duration=4, extra='<tie type="start"/>') +
                           '<backup><duration>4</duration></backup>' + note(duration=4, voice="2") + '</measure>' +
                           '<measure>' + note(duration=4, extra='<tie type="stop"/>') + '</measure>')
        self.assertEqual(len(score["notes"]), 2)
        self.assertEqual(score["notes"][0]["duration"], [8, 1])
        self.assertEqual(score["notes"][1]["duration"], [4, 1])
        self.assertEqual(len(grouped_events(score)), 1)
        self.assertTrue(score["exact"])

    def test_tempos_offsets_and_dots(self):
        score = self.parse('<measure>' + ATTR + '<direction><sound tempo="120"/></direction>' + note(duration=1) +
                           '<direction><offset>1</offset><direction-type><metronome><beat-unit>eighth</beat-unit><beat-unit-dot/><per-minute>80</per-minute></metronome></direction-type></direction>' + note("D", 3) + '</measure>')
        self.assertEqual(score["tempos"], [{"onset": [0, 1], "bpm": [120, 1]}, {"onset": [2, 1], "bpm": [60, 1]}])

    def test_page_end_rest_and_merge_is_immutable(self):
        a = self.parse('<measure>' + ATTR + note() + '<note><rest/><duration>3</duration></note></measure><measure><note><rest/><duration>4</duration></note></measure>')
        b = self.parse('<measure implicit="yes">' + ATTR + note("D") + '</measure>')
        before = copy.deepcopy(a)
        merged = merge_scores([a, b])
        self.assertEqual(merged["duration"], [9, 1])
        self.assertEqual(merged["notes"][-1]["onset"], [8, 1])
        self.assertEqual(merged["notes"][-1]["measure"], 3)
        self.assertEqual(a, before)
        validate_score(merged)

    def test_continuation_inherits_tempo_and_explicit_mark_replaces_it(self):
        a = self.parse('<measure>' + ATTR + '<direction><sound tempo="140"/></direction>' + note(duration=4) + '</measure>')
        b = self.parse('<measure>' + ATTR + note(duration=4) + '</measure>')
        self.assertEqual(merge_scores([a,b])["tempos"], [{"onset":[0,1], "bpm":[140,1]}])
        b = self.parse('<measure>' + ATTR + '<direction><sound tempo="90"/></direction>' + note(duration=4) + '</measure>')
        self.assertEqual(merge_scores([a,b])["tempos"][-1], {"onset":[4,1], "bpm":[90,1]})

    def test_unsupported_and_invalid_are_explicit(self):
        score = self.parse('<measure>' + ATTR + note(duration=4) + '<barline><repeat direction="backward"/></barline></measure>')
        self.assertFalse(score["exact"])
        self.assertTrue(score["warnings"])
        for contents in ('<backup><duration>1</duration></backup>' + note(), note(extra='<chord/>'), note(duration=0), '<attributes><divisions>0</divisions></attributes>' + note()):
            with self.subTest(contents=contents), self.assertRaises(ValueError):
                self.parse('<measure>' + contents + '</measure>')

    def test_v9_round_trip_validation_and_legacy(self):
        score = self.parse('<measure>' + ATTR + note(duration=4) + '</measure>')
        data = {"version": 9, "schema_version": 9, "musical_score": score, "events": grouped_events(score), "transcription": ""}
        target = self.path.with_suffix(".json")
        project_io.write_project(target, data)
        self.assertEqual(project_io.read_project(target), data)
        for change in (lambda s: s["notes"][0].update(duration=[1, 0]),
                       lambda s: s["notes"][0].update(pitch=True),
                       lambda s: s["measures"][0].update(onset=[1, 1]),
                       lambda s: s.update(tempos=[])):
            bad = copy.deepcopy(data); change(bad["musical_score"])
            with self.assertRaises(ValueError): project_io.validate_project(bad)
        bad = copy.deepcopy(data); bad["events"][0]["notes"] = [62]
        with self.assertRaises(ValueError): project_io.validate_project(bad)
        legacy = {"version":8, "events": data["events"], "transcription":"old edit"}
        project_io.write_project(target, legacy)
        before = target.read_bytes()
        self.assertEqual(project_io.read_project(target), legacy)
        self.assertEqual(target.read_bytes(), before)

    def test_missing_divisions_and_navigation_are_not_silent(self):
        missing = self.parse('<measure>' + note(duration=4) + '</measure>')
        self.assertFalse(missing["exact"])
        navigation = self.parse('<measure>' + ATTR + note(duration=4) + '<direction><sound dacapo="yes"/></direction></measure>')
        self.assertFalse(navigation["exact"])
        self.assertTrue(any("Navigation" in w for w in navigation["warnings"]))

    def test_existing_fixtures_and_layouts(self):
        import main
        root = Path(__file__).parent
        pages = [read_musicxml(root / p) for p in ("page-1.musicxml", "page-2.musicxml")]
        self.assertEqual([len(grouped_events(p)) for p in pages], [158, 141])
        merged = merge_scores(pages)
        self.assertEqual(len(merged["measures"]), 46)
        self.assertEqual(len(grouped_events(merged)), 299)
        second = [n for n in merged["notes"] if n["measure"] == 25]
        self.assertGreaterEqual(min(rational(n["onset"]) for n in second), rational(pages[0]["duration"]))
        for layout in ("Русская", "English", "Deutsch"):
            text, warnings = main.render_events(grouped_events(merged), 5, layout, True, 100)
            self.assertTrue(text); self.assertFalse(warnings)

    def test_gui_score_roundtrip_and_legacy_playback(self):
        from test_project_safety import piano, MemorySettings, DummyPiano, QApplication
        app = QApplication.instance() or QApplication([])
        with patch.object(piano, "QSettings", MemorySettings), patch.object(piano, "OfflinePianoPanel", DummyPiano), patch.object(piano, "VirtualPianoPanel", DummyPiano):
            window = piano.MainWindow()
        self.addCleanup(window.deleteLater)
        self.parse('<measure>' + ATTR + note(duration=2) + note("E", 1, extra='<chord/>') + '<note><rest/><duration>2</duration></note></measure>')
        with patch.object(window, "confirm_discard", return_value=True):
            self.assertTrue(window.load_musicxml(str(self.path)))
        self.assertEqual(sorted(e["duration"] for e in window.offline_score()), [1, 2])
        window.output.setPlainText("manual")
        window.transpose_spin.setValue(3)
        self.assertEqual(window.output.toPlainText(), "manual")
        target = self.path.with_suffix(".vpa.json")
        with patch.object(piano.QFileDialog, "getSaveFileName", return_value=(str(target), "")):
            self.assertTrue(window.save_project())
        expected = copy.deepcopy(window.musical_score)
        with patch.object(piano.QFileDialog, "getOpenFileName", return_value=(str(target), "")), patch.object(window, "confirm_discard", return_value=True):
            self.assertTrue(window.open_project())
        self.assertEqual(window.musical_score, expected)
        self.assertEqual(window.output.toPlainText(), "manual")
        legacy = {"version":8, "events": window.events, "transcription":"legacy"}
        project_io.write_project(target, legacy)
        with patch.object(piano.QFileDialog, "getOpenFileName", return_value=(str(target), "")), patch.object(window, "confirm_discard", return_value=True):
            self.assertTrue(window.open_project())
        self.assertIsNone(window.musical_score)
        self.assertEqual(window.offline_score(), [])
        self.assertEqual(window.output.toPlainText(), "legacy")
        self.assertIn("MusicXML", window.status.text())


if __name__ == "__main__":
    unittest.main()
