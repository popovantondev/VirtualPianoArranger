"""Shared note selection and tempo conversion; no UI or audio dependencies."""
from bisect import bisect_right
from fractions import Fraction
from music_time import rational, validate_score

LOW, HIGH = 36, 96


def playback_time_available(score):
    """Exact clock, or explicit MIDI-only consent for closed-event replay."""
    return bool(score and (score['exact'] or score.get('midi_approximate_playback') is True))


def simplify_notes(notes, chord_value):
    """Select distinct pitches by rank, not a inferred melody voice."""
    notes = sorted(set(notes))
    if len(notes) <= 2 or chord_value <= 10:
        return notes
    limit = max(2, round(6 - (chord_value - 10) * 4 / 90))
    if len(notes) <= limit:
        return notes
    selected = [notes[0], notes[-1]]
    interior, slots = notes[1:-1], limit - 2
    if slots:
        indexes = [len(interior) // 2] if slots == 1 else [round(i * (len(interior) - 1) / (slots - 1)) for i in range(slots)]
        selected.extend(interior[i] for i in indexes)
    return sorted(set(selected))


def select_pitches(notes, shift, simplification):
    selected = simplify_notes([p + shift for p in notes], simplification)
    return [p for p in selected if LOW <= p <= HIGH], [p for p in selected if not LOW <= p <= HIGH]


def arrange(score, shift, simplification):
    validate_score(score)
    groups = {}
    for note in score["notes"]:
        groups.setdefault((note["measure"], rational(note["onset"])), []).append(note)
    selected, attacks, outside = [], [], []
    for (measure, onset), notes in sorted(groups.items()):
        pitches, rejected = select_pitches([n["pitch"] for n in notes], shift, simplification)
        outside.extend((measure, p) for p in rejected)
        chosen = [{**n, "pitch": n["pitch"] + shift} for n in notes if n["pitch"] + shift in pitches]
        selected.extend(chosen)
        attacks.append({"measure": measure, "time": float(onset), "notes": pitches,
                        "note_ids": [n["id"] for n in chosen]})
    return {"notes": selected, "attacks": attacks, "outside": outside}


def score_clock(score):
    """Clock for validated score events, shared by audio and UI.

    Approximate MIDI consent preserves the recorded ticks/tempo but does not
    make ambiguous note matching or unsupported pitch bends exact.
    """
    if not playback_time_available(score):
        raise ValueError("Exact musical time is unavailable")
    times = [rational(t["onset"]) for t in score["tempos"]]
    rates = [Fraction(60) / rational(t["bpm"]) for t in score["tempos"]]
    seconds = [Fraction(0)]
    for i in range(1, len(times)):
        seconds.append(seconds[-1] + (times[i] - times[i-1]) * rates[i-1])
    def at(position):
        i = bisect_right(times, position) - 1
        return float(seconds[i] + (position - times[i]) * rates[i])
    return at


def playback_plan(score, shift, simplification):
    if score is None:
        return {"version": 1, "error": "legacy", "notes": [], "duration": 0}
    selected = arrange(score, shift, simplification)
    if not playback_time_available(score):
        return {"version": 1, "error": "uncertain", "notes": [], "duration": 0}
    at = score_clock(score)
    notes = [{"id": n["id"], "midi": n["pitch"], "start": at(rational(n["onset"])),
              "end": at(rational(n["onset"]) + rational(n["duration"])),
              **({'velocity':n['velocity']} if 'velocity' in n else {})} for n in selected["notes"]]
    return {"version": 1, "approximate":not score['exact'], "notes": sorted(notes, key=lambda n: (n["start"], n["id"])),
            "duration": at(rational(score["duration"])), "outside": len(selected["outside"])}
