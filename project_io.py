"""Bounded v8/v9 project reading and atomic writes, independent of Qt."""
import json
import math
import os
import tempfile
from pathlib import Path
from music_time import validate_score, grouped_events

MAX_BYTES = 16 * 1024 * 1024


def validate_project(data):
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] not in (8, 9):
        raise ValueError("Expected a supported v8/v9 project")
    if data["version"] == 8:
        if "schema_version" in data or "musical_score" in data:
            raise ValueError("Legacy project cannot contain a new musical schema")
    else:
        if type(data.get("schema_version")) is not int or data["schema_version"] != 9:
            raise ValueError("Unsupported project schema")
        validate_score(data.get("musical_score"))
        if data.get("events") != grouped_events(data["musical_score"]):
            raise ValueError("Letter events disagree with the musical score")
    events = data.get("events")
    if not isinstance(events, list) or len(events) > 100000:
        raise ValueError("Invalid event list")
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Invalid event")
        for name in ("time", "duration"):
            value = event.get(name)
            if type(value) not in (int, float) or not 0 <= value <= 1e12 or not math.isfinite(value):
                raise ValueError("Invalid musical time")
        if type(event.get("measure")) is not int or event["measure"] < 0:
            raise ValueError("Invalid measure")
        notes = event.get("notes")
        if not isinstance(notes, list) or len(notes) > 128 or any(type(n) is not int or not 0 <= n <= 127 for n in notes):
            raise ValueError("Invalid notes")
    for name in ("score_path", "musicxml_path"):
        value = data.get(name)
        if value is not None and (not isinstance(value, str) or len(value) > 32768 or "\0" in value):
            raise ValueError("Invalid source path")
    for name in ("transcription", "generated_transcription"):
        if name in data and (not isinstance(data[name], str) or len(data[name]) > 2000000):
            raise ValueError("Invalid transcription")
    for name in ("merge_near_notes", "spacing", "transcription_is_manual"):
        if name in data and type(data[name]) is not bool:
            raise ValueError("Invalid boolean setting")
    for name, limits in {"comfort": (0, 100), "chord_simplification": (0, 100), "transpose_play": (-12, 12)}.items():
        if name in data and (type(data[name]) is not int or not limits[0] <= data[name] <= limits[1]):
            raise ValueError("Invalid setting: " + name)
    if "practice_mode" in data and data["practice_mode"] not in ("off","normal","single","upper","keyboard","balanced","musical"):raise ValueError("Invalid practice mode")
    if 'text_source' in data and data['text_source'] is not None:
        source=data['text_source']
        if (not isinstance(source,dict) or set(source)!={'text','layout'} or
                not isinstance(source['text'],str) or len(source['text'])>2000000 or
                source['layout'] not in ('Русская','English','Deutsch') or
                data['version']!=8 or data['events']):raise ValueError('Invalid untimed text source')
    if "piano_shift" in data and (type(data["piano_shift"]) is not int or not -12<=data["piano_shift"]<=12):raise ValueError("Invalid piano shift")
    if "link_piano_shift" in data and type(data["link_piano_shift"]) is not bool:raise ValueError("Invalid piano link")
    for name, choices in {"ui_language": ("Русский", "English", "Deutsch"), "physical_layout": ("Русская", "English", "Deutsch"), "display_layout": ("Русская", "English", "Deutsch")}.items():
        if name in data and data[name] not in choices:
            raise ValueError("Invalid layout/language")
    return data


def read_project(path):
    with open(path, "rb") as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Project is too large")
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except RecursionError as error:
        raise ValueError("Project nesting is too deep") from error
    return validate_project(data)


def atomic_write_text(path, text):
    target = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=target.parent,
                                         prefix=".vpa-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def write_project(path, data):
    validate_project(data)
    text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Project is too large")
    atomic_write_text(path, text)
