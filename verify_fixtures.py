"""Deterministic smoke check for the checked-in MusicXML fixtures.

This does not launch the GUI, HOMR, or any file picker.  It verifies the
parser and the multi-page merge using the two already generated MusicXML files.
"""

import importlib.util
from music_time import read_musicxml, merge_scores, grouped_events, rational
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "main.py"


def load_module():
    spec = importlib.util.spec_from_file_location("vpa_main", MAIN)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {MAIN}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    app = load_module()
    pages = [app.parse_musicxml(ROOT / name) for name in ("page-1.musicxml", "page-2.musicxml")]
    assert [len(events) for events in pages] == [158, 141]

    scores = [read_musicxml(ROOT / name) for name in ("page-1.musicxml", "page-2.musicxml")]
    score = merge_scores(scores)
    merged = grouped_events(score)
    measure_offset = len(score["measures"])
    assert min(event["time"] for event in merged if event["measure"] == 25) >= float(rational(scores[0]["duration"]))

    assert len(merged) == 299
    assert measure_offset == 46
    text, warnings = app.render_events(merged, 5, "Русская", True, 100)
    assert not warnings
    assert text.splitlines()[0] == "я я д л д о"
    assert text.splitlines()[-1] == "(6з)"
    print("PASS: 2 MusicXML pages -> 299 events, 46 measures, 0 range warnings")


if __name__ == "__main__":
    main()
