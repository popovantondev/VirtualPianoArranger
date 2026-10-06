"""Qt-free MusicXML timeline. Project time is exact quarter-note fractions."""
import copy
from fractions import Fraction
import xml.etree.ElementTree as ET


def rational(value):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(v) is not int or abs(v) > 10**12 for v in value) or value[1] <= 0):
        raise ValueError("Invalid rational time")
    return Fraction(*value)


def pair(value):
    value = Fraction(value)
    return [value.numerator, value.denominator]


def number(text, positive=False):
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError, TypeError) as error:
        raise ValueError("Invalid MusicXML number") from error
    if abs(value) > 10**9 or (positive and value <= 0):
        raise ValueError("MusicXML number out of range")
    return value


def validate_score(score):
    if not isinstance(score, dict) or type(score.get("format")) is not int or score["format"] != 1:
        raise ValueError("Unsupported musical model")
    if type(score.get("exact")) is not bool:
        raise ValueError("Missing musical precision status")
    if type(score.get("initial_tempo_explicit")) is not bool:
        raise ValueError("Missing initial tempo provenance")
    parts = score.get("parts")
    if not isinstance(parts, list) or len(parts) > 1000:
        raise ValueError("Invalid parts")
    ids = set()
    for part in parts:
        if not isinstance(part, dict) or not isinstance(part.get("id"), str) or not 0 < len(part["id"]) <= 1000 or part["id"] in ids:
            raise ValueError("Invalid part id")
        if not isinstance(part.get("name"), str) or len(part["name"]) > 1000:
            raise ValueError("Invalid part name")
        ids.add(part["id"])
        for name,limit in (("midi_track",999),("midi_port",127),("midi_channel",15),("midi_program",127)):
            if name in part and (type(part[name]) is not int or not 0<=part[name]<=limit):raise ValueError("Invalid MIDI part metadata")
        if "percussion" in part and type(part['percussion']) is not bool:raise ValueError("Invalid MIDI percussion metadata")
    if 'midi_approximate_playback' in score:
        if type(score['midi_approximate_playback']) is not bool:raise ValueError('Invalid approximate MIDI consent')
        if score['midi_approximate_playback'] and (not parts or any(
                any(name not in p for name in ('midi_track','midi_port','midi_channel','midi_program')) for p in parts)):
            raise ValueError('Approximate playback requires MIDI part metadata')
    measures = score.get("measures")
    if not isinstance(measures, list) or len(measures) > 100000:
        raise ValueError("Invalid measures")
    end = Fraction(0)
    for i, measure in enumerate(measures, 1):
        if (not isinstance(measure, dict) or type(measure.get("number")) is not int or
                measure["number"] != i or rational(measure.get("onset")) != end):
            raise ValueError("Invalid measure sequence")
        length = rational(measure.get("duration"))
        if length <= 0:
            raise ValueError("Invalid measure length")
        end += length
    if rational(score.get("duration")) != end:
        raise ValueError("Invalid score length")
    notes = score.get("notes")
    if not isinstance(notes, list) or len(notes) > 100000:
        raise ValueError("Invalid individual notes")
    note_ids = set()
    for note in notes:
        if not isinstance(note, dict):
            raise ValueError("Invalid note")
        if not isinstance(note.get("id"), str) or not 0 < len(note["id"]) <= 1000 or note["id"] in note_ids:
            raise ValueError("Invalid note id")
        note_ids.add(note["id"])
        if "velocity" in note and (type(note['velocity']) is not int or not 1<=note['velocity']<=127):raise ValueError("Invalid MIDI velocity")
        if not isinstance(note.get("part_id"), str) or note["part_id"] not in ids or any(not isinstance(note.get(k), str) or not 0 < len(note[k]) <= 100 for k in ("voice", "staff")):
            raise ValueError("Invalid note stream")
        if type(note.get("pitch")) is not int or not 0 <= note["pitch"] <= 127:
            raise ValueError("Invalid pitch")
        onset, duration = rational(note.get("onset")), rational(note.get("duration"))
        m = note.get("measure")
        if type(m) is not int or not 1 <= m <= len(measures):
            raise ValueError("Invalid note measure")
        measure = measures[m - 1]
        start = rational(measure["onset"])
        if not start <= onset < start + rational(measure["duration"]) or duration <= 0 or onset + duration > end:
            raise ValueError("Invalid note time")
    tempos = score.get("tempos")
    if not isinstance(tempos, list) or not tempos or len(tempos) > 100000:
        raise ValueError("Invalid tempo map")
    previous = Fraction(-1)
    for tempo in tempos:
        if not isinstance(tempo, dict):
            raise ValueError("Invalid tempo")
        onset, bpm = rational(tempo.get("onset")), rational(tempo.get("bpm"))
        if not previous < onset <= end or onset < 0 or not 0 < bpm <= 1000:
            raise ValueError("Invalid tempo time/value")
        previous = onset
    if rational(tempos[0]["onset"]) != 0:
        raise ValueError("Missing initial tempo")
    warnings = score.get("warnings")
    if not isinstance(warnings, list) or len(warnings) > 10000 or any(not isinstance(w, str) or len(w) > 1000 for w in warnings):
        raise ValueError("Invalid import warnings")
    return score


def grouped_events(score):
    """Letter attacks only: maximum duration is not a playback source."""
    groups = {}
    for note in score["notes"]:
        groups.setdefault((note["measure"], rational(note["onset"])), []).append(note)
    return [{"measure": measure, "time": float(onset),
             "duration": float(max(rational(n["duration"]) for n in notes)),
             "notes": sorted({n["pitch"] for n in notes}),
             "voices": sorted({n["voice"] + "/" + n["staff"] for n in notes})}
            for (measure, onset), notes in sorted(groups.items())]


def read_musicxml(path):
    with open(path, "rb") as stream:
        raw = stream.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024 or b"<!ENTITY" in raw.upper():
        raise ValueError("MusicXML is too large or contains entities")
    root = ET.fromstring(raw)
    for element in root.iter():
        element.tag = element.tag.rsplit("}", 1)[-1]
    if root.tag != "score-partwise":
        raise ValueError("Only partwise MusicXML is supported")
    score = {"format": 1, "exact": True, "parts": [], "notes": [], "measures": [],
             "tempos": [], "initial_tempo_explicit": False, "duration": [0, 1], "warnings": []}
    def warn(message, uncertain=False):
        if message not in score["warnings"]:
            score["warnings"].append(message)
        if uncertain:
            score["exact"] = False
    local_parts = []
    for part in root.findall("part"):
        pid = part.get("id") or "P" + str(len(local_parts) + 1)
        name = next((p.findtext("part-name", "") for p in root.findall("./part-list/score-part") if p.get("id") == pid), "")
        score["parts"].append({"id": pid, "name": name})
        local = []
        divisions, nominal = Fraction(1), None
        divisions_known = False
        for index, measure in enumerate(part.findall("measure"), 1):
            cursor, extent = Fraction(0), Fraction(0)
            last_attack = None
            notes, tempos = [], []
            for child in measure:
                if child.tag == "attributes":
                    if child.find("divisions") is not None:
                        divisions = number(child.findtext("divisions"), True)
                        divisions_known = True
                    time = child.find("time")
                    if time is not None and time.find("senza-misura") is None:
                        beats, units = time.findall("beats"), time.findall("beat-type")
                        if not beats or len(beats) != len(units):
                            raise ValueError("Invalid time signature")
                        nominal = sum((sum(number(b, True) for b in beat.text.split("+")) * 4 / number(unit.text, True)
                                       for beat, unit in zip(beats, units)), Fraction(0))
                    if child.find("transpose") is not None:
                        warn("Instrument transposition is not applied; exact playback unavailable.", True)
                elif child.tag in ("backup", "forward"):
                    if not divisions_known:
                        warn("Missing divisions; assumed 1, exact playback unavailable.", True)
                    delta = number(child.findtext("duration"), True) / divisions
                    cursor += delta if child.tag == "forward" else -delta
                    if cursor < 0:
                        raise ValueError("Backup crosses a measure boundary")
                    extent = max(extent, cursor)
                    last_attack = None
                elif child.tag in ("direction", "sound"):
                    sound = child if child.tag == "sound" else child.find("sound")
                    if sound is not None and any(k in sound.attrib for k in ("dacapo", "dalsegno", "tocoda", "fine")):
                        warn("Navigation/repeats are not expanded; exact playback unavailable.", True)
                    position = cursor + number(child.findtext("offset", "0")) / divisions
                    bpm = None
                    if sound is not None and sound.get("tempo") is not None:
                        bpm = number(sound.get("tempo"), True)
                    else:
                        metronome = child.find("./direction-type/metronome")
                        if metronome is not None:
                            unit = {"whole": 4, "half": 2, "quarter": 1, "eighth": Fraction(1, 2), "16th": Fraction(1, 4)}.get(metronome.findtext("beat-unit"))
                            if unit and metronome.find("per-minute") is not None and metronome.find("beat-unit-tied") is None:
                                dots = len(metronome.findall("beat-unit-dot"))
                                bpm = number(metronome.findtext("per-minute"), True) * unit * sum((Fraction(1, 2**d) for d in range(dots + 1)), Fraction(0))
                            else:
                                warn("Unsupported metronome mark; exact playback unavailable.", True)
                    if bpm is not None:
                        if position < 0 or bpm > 1000:
                            raise ValueError("Invalid tempo mark")
                        tempos.append((position, bpm))
                    if child.find("./direction-type/wedge") is not None:
                        warn("Dynamics are not interpreted.")
                elif child.tag == "note":
                    if child.find("grace") is not None:
                        warn("Grace notes omitted; exact playback unavailable.", True)
                        last_attack = None
                        continue
                    duration = number(child.findtext("duration"), True) / divisions
                    if not divisions_known:
                        warn("Missing divisions; assumed 1, exact playback unavailable.", True)
                    stream = (child.findtext("voice", "1"), child.findtext("staff", "1"))
                    chord = child.find("chord") is not None
                    if chord:
                        if last_attack is None or last_attack[1] != stream:
                            raise ValueError("Chord has no preceding note in this stream")
                        onset = last_attack[0]
                    else:
                        onset = cursor
                        last_attack = (onset, stream)
                        cursor += duration
                    extent = max(extent, onset + duration, cursor)
                    if child.find("rest") is None:
                        pitch = child.find("pitch")
                        if pitch is None:
                            warn("Unpitched notes omitted; exact playback unavailable.", True)
                            continue
                        step = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}.get(pitch.findtext("step"))
                        alter = number(pitch.findtext("alter", "0"))
                        octave = number(pitch.findtext("octave"))
                        if step is None or octave.denominator != 1:
                            raise ValueError("Invalid pitch")
                        if alter.denominator != 1:
                            warn("Microtonal pitch omitted; exact playback unavailable.", True)
                            continue
                        midi = int((octave + 1) * 12 + step + alter)
                        if not 0 <= midi <= 127:
                            raise ValueError("Pitch outside MIDI range")
                        ties = {t.get("type") for t in child.findall("tie")}
                        notes.append({"id": f"{pid}:{index}:{len(notes)}", "part_id": pid, "voice": stream[0], "staff": stream[1],
                                      "pitch": midi, "onset": onset, "duration": duration, "measure": index, "ties": ties})
                elif child.tag == "barline" and (child.find("repeat") is not None or child.find("ending") is not None):
                    warn("Repeats/endings are not expanded; exact playback unavailable.", True)
            if extent <= 0:
                if nominal is None:
                    raise ValueError("Empty measure has no length")
                extent = nominal
            if nominal is not None and extent < nominal and measure.get("implicit") != "yes":
                warn("Underfilled regular measure padded to its time signature.")
                extent = nominal
            if nominal is not None and extent > nominal:
                warn("Overfilled measure retained at actual length.")
            local.append((extent, notes, tempos))
        local_parts.append(local)
    if not local_parts:
        raise ValueError("MusicXML has no parts")
    count = max(map(len, local_parts))
    if any(len(part) != count for part in local_parts):
        warn("Unequal part measure counts aligned by ordinal position.", True)
    absolute = Fraction(0)
    tempo_map = {}
    for index in range(count):
        lengths = [part[index][0] for part in local_parts if index < len(part)]
        length = max(lengths)
        if len(set(lengths)) != 1:
            warn("Part measure lengths differ; aligned to longest measure.")
        score["measures"].append({"number": index + 1, "onset": pair(absolute), "duration": pair(length)})
        for part in local_parts:
            if index >= len(part):
                continue
            for note in part[index][1]:
                note["onset"] += absolute
                score["notes"].append(note)
            for onset, bpm in part[index][2]:
                if onset > length:
                    raise ValueError("Tempo outside measure")
                position = absolute + onset
                if position in tempo_map and tempo_map[position] != bpm:
                    warn("Conflicting tempo marks; exact playback unavailable.", True)
                tempo_map.setdefault(position, bpm)
        absolute += length
    score["initial_tempo_explicit"] = Fraction(0) in tempo_map
    tempo_map.setdefault(Fraction(0), Fraction(110))
    if not any(part[index][2] for part in local_parts for index in range(len(part))):
        warn("No tempo specified; default 110 quarter notes/minute.")
    score["tempos"] = [{"onset": pair(t), "bpm": pair(b)} for t, b in sorted(tempo_map.items())]
    score["duration"] = pair(absolute)
    merged, active = [], {}
    for note in sorted(score["notes"], key=lambda n: (n["onset"], n["part_id"], n["id"])):
        key = (note["part_id"], note["voice"], note["staff"], note["pitch"])
        ties = note.pop("ties")
        previous = active.pop(key, None) if "stop" in ties else None
        if previous is not None and previous["onset"] + previous["duration"] == note["onset"]:
            previous["duration"] += note["duration"]
            current = previous
        else:
            if "stop" in ties:
                warn("Unmatched/discontinuous tie stop; exact playback unavailable.", True)
            current = note
            merged.append(note)
        if "start" in ties:
            if key in active:
                warn("Overlapping tie starts; exact playback unavailable.", True)
            active[key] = current
    if active:
        warn("Unfinished tie; exact playback unavailable.", True)
    for note in merged:
        note["onset"], note["duration"] = pair(note["onset"]), pair(note["duration"])
    score["notes"] = merged
    return validate_score(score)


def merge_scores(scores):
    if not scores:
        raise ValueError("No pages")
    result = {"format": 1, "exact": True, "parts": [], "notes": [], "measures": [], "tempos": [], "initial_tempo_explicit": scores[0].get("initial_tempo_explicit", False), "duration": [0, 1], "warnings": []}
    offset, measure_offset = Fraction(0), 0
    for page_index, original in enumerate(scores):
        validate_score(original)
        score = copy.deepcopy(original)
        mapping = {p["id"]: f"page{page_index + 1}:{p['id']}" for p in score["parts"]}
        for part in score["parts"]:
            part["id"] = mapping[part["id"]]
        for note in score["notes"]:
            note["id"] = f"page{page_index + 1}:{note['id']}"
            note["part_id"] = mapping[note["part_id"]]
            note["onset"] = pair(rational(note["onset"]) + offset)
            note["measure"] += measure_offset
        for measure in score["measures"]:
            measure["onset"] = pair(rational(measure["onset"]) + offset)
            measure["number"] += measure_offset
        for tempo in score["tempos"]:
            if page_index and rational(tempo["onset"]) == 0 and not score["initial_tempo_explicit"]:
                continue  # A missing mark on a continuation page inherits the preceding tempo.
            tempo["onset"] = pair(rational(tempo["onset"]) + offset)
            if result["tempos"] and tempo["onset"] == result["tempos"][-1]["onset"]:
                result["tempos"].pop()
            result["tempos"].append(tempo)
        for key in ("parts", "notes", "measures", "warnings"):
            if key == "warnings" and page_index and not score["initial_tempo_explicit"]:
                score[key] = [w for w in score[key] if not w.startswith("No tempo specified;")]
                score[key].append("Continuation page has no initial tempo; preceding tempo retained.")
            result[key].extend(score[key])
        result["exact"] &= score["exact"]
        offset += rational(score["duration"])
        measure_offset += len(score["measures"])
    result["duration"] = pair(offset)
    return validate_score(result)
