import test from "node:test";
import assert from "node:assert/strict";
import { readMidi, selectParts, scoreClock, previewPlan, MidiError } from "../js/midi.js";

// Synthetic SMF builders, same as vlq() / smf() in test_midi_import.py.
function vlq(value) {
  const bytes = [value & 127];
  value >>= 7;
  while (value) {
    bytes.unshift((value & 127) | 128);
    value >>= 7;
  }
  return bytes;
}

function smf(tracks, { format = 1, ppqn = 480 } = {}) {
  const word = (value) => [(value >> 8) & 255, value & 255];
  const long = (value) => [(value >>> 24) & 255, (value >>> 16) & 255, (value >>> 8) & 255, value & 255];
  const out = [0x4d, 0x54, 0x68, 0x64, ...long(6), ...word(format), ...word(tracks.length), ...word(ppqn)];
  for (const events of tracks) {
    const body = [];
    for (const [delta, event] of events) body.push(...vlq(delta), ...event);
    body.push(0, 0xff, 0x2f, 0);
    out.push(0x4d, 0x54, 0x72, 0x6b, ...long(body.length), ...body);
  }
  return Uint8Array.from(out);
}

const bytes = (...values) => values;
const text = (value) => [...Buffer.from(value, "latin1")];

function failure(action) {
  try { action(); } catch (error) { return error; }
  return null;
}

test("format 0 with running status, velocity-0 note-off and trailing silence", () => {
  const score = readMidi(smf([[[480, bytes(0x90, 0x3c, 0x40)], [480, bytes(0x3c, 0x00)], [480, bytes(0xff, 0x01, 0x01, 0x78)]]], { format: 0 }));
  assert.equal(score.exact, true);
  assert.equal(score.notes.length, 1);
  assert.equal(score.notes[0].onset, 1);
  assert.equal(score.notes[0].duration, 1);
  assert.equal(score.notes[0].velocity, 64);
  assert.equal(score.duration, 3);
  const clock = scoreClock(score);
  assert.equal(clock(score.notes[0].onset), 0.5);
  assert.equal(clock(score.notes[0].onset + score.notes[0].duration), 1);
  assert.equal(clock(score.duration), 1.5);
});

test("the sustain pedal extends the release", () => {
  const score = readMidi(smf([[[0, bytes(0xb0, 0x40, 0x7f)], [0, bytes(0x90, 0x3c, 0x40)], [480, bytes(0x80, 0x3c, 0)], [480, bytes(0xb0, 0x40, 0)]]], { format: 0 }));
  assert.equal(score.exact, true);
  assert.equal(score.notes[0].duration, 2);
});

test("a note-off in another track matches only a unique channel and pitch", () => {
  const on = [[0, bytes(0x90, 0x3c, 0x40)]];
  const off = [[960, bytes(0x80, 0x3c, 0)]];
  const single = readMidi(smf([on, off]));
  assert.equal(single.exact, true);
  assert.equal(single.notes[0].duration, 2);
  assert.equal(single.parts[0].midiTrack, 0);
  const ambiguous = readMidi(smf([on, on, off]));
  assert.equal(ambiguous.exact, false);
  assert.deepEqual(ambiguous.notes, []);
  assert.ok(ambiguous.warnings.some((warning) => warning.includes("ambiguous cross-track")));
});

test("all-notes-off respects the pedal but all-sound-off does not", () => {
  for (const [controller, length] of [[123, 3], [120, 1]]) {
    const score = readMidi(smf([[[0, bytes(0xb0, 0x40, 0x7f)], [0, bytes(0x90, 0x3c, 0x40)], [480, bytes(0xb0, controller, 0)], [960, bytes(0xb0, 0x40, 0)]]], { format: 0 }));
    assert.equal(score.exact, true);
    assert.equal(score.notes[0].duration, length, `controller ${controller}`);
  }
});

test("ports do not share programs or pedals", () => {
  const first = [[0, bytes(0xff, 0x21, 0x01, 0x01)], [0, bytes(0xc0, 0x07)], [0, bytes(0xb0, 0x40, 0x7f)], [0, bytes(0x90, 0x3c, 0x40)], [480, bytes(0x80, 0x3c, 0)], [960, bytes(0xb0, 0x40, 0)]];
  const second = [[0, bytes(0xff, 0x21, 0x01, 0x02)], [0, bytes(0x90, 0x40, 0x40)], [480, bytes(0x80, 0x40, 0)]];
  const score = readMidi(smf([first, second]));
  assert.equal(score.exact, true);
  assert.deepEqual(score.parts.map((part) => [part.midiPort, part.midiProgram]), [[1, 7], [2, 0]]);
  const byPitch = Object.fromEntries(score.notes.map((note) => [note.pitch, note]));
  assert.equal(byPitch[60].duration, 3);
  assert.equal(byPitch[64].duration, 1);
  assert.equal(failure(() => readMidi(smf([[[0, bytes(0xff, 0x21, 0x02, 0x01, 0x02)]]]))).code, "bad_port");
});

test("a pedal and a program change on a separate track still apply to the channel", () => {
  const controls = [[0, bytes(0xc0, 0x07)], [0, bytes(0xb0, 0x40, 0x7f)], [1440, bytes(0xb0, 0x79, 0)]];
  const notes = [[0, bytes(0x90, 0x3c, 0x64)], [480, bytes(0x80, 0x3c, 0)]];
  const score = readMidi(smf([controls, notes]));
  assert.equal(score.parts[0].midiProgram, 7);
  assert.equal(score.notes[0].duration, 3);
});

test("one zero padding byte after end-of-track is tolerated, later bytes are not", () => {
  const original = smf([[[0, bytes(0x90, 0x3c, 0x40)], [0, bytes(0x80, 0x3c, 0)], [480, bytes(0x90, 0x40, 0x40)], [480, bytes(0x80, 0x40, 0)]]], { format: 0 });
  const withTail = (tail) => {
    const copy = Uint8Array.from([...original, ...tail]);
    const length = new DataView(copy.buffer).getUint32(18) + tail.length;
    new DataView(copy.buffer).setUint32(18, length);
    return copy;
  };
  const padded = readMidi(withTail([0]));
  assert.equal(padded.exact, true);
  assert.equal(padded.notes.length, 1);
  assert.equal(padded.notes[0].onset, 1);
  assert.ok(padded.warnings.some((warning) => warning.includes("padding")));
  assert.ok(padded.warnings.some((warning) => warning.includes("Zero-length")));
  for (const tail of [[0, 0], [1], [0, 0x90, 0x3c, 0x40]]) {
    assert.equal(failure(() => readMidi(withTail(tail))).code, "bad_end", `tail ${tail}`);
  }
});

test("overlap, pitch bend, a missing note-off and percussion are reported, not guessed", () => {
  const score = readMidi(smf([[
    [0, bytes(0x90, 0x3c, 0x40)], [1, bytes(0x90, 0x3c, 0x40)], [1, bytes(0x80, 0x3c, 0)],
    [1, bytes(0xe0, 0x01, 0x40)], [0, bytes(0x99, 0x24, 0x40)], [1, bytes(0x89, 0x24, 0)]
  ]], { format: 0 }));
  assert.equal(score.exact, false);
  assert.equal(score.notes.length, 1);
  assert.equal(score.notes[0].durationTicks, 2);
  assert.ok(score.parts.some((part) => part.percussion && !part.active));
  assert.ok(score.warnings.some((warning) => warning.includes("Unclosed")));
});

test("corrupt and unsupported files fail with a code", () => {
  const cases = [
    [Uint8Array.from(text("bad")), "not_midi"],
    [smf([[]], { format: 2 }), "format2"],
    [smf([[]], { ppqn: 0x8028 }), "smpte"],
    [smf([[]]).slice(0, -1), "truncated"],
    [smf([[[0, bytes(0x3c, 0x40)]]], { format: 0 }), "bad_running"],
    [smf([[[0, bytes(0x90, 0x80, 0x40)]]], { format: 0 }), "bad_data"]
  ];
  for (const [data, code] of cases) {
    const error = failure(() => readMidi(data));
    assert.ok(error instanceof MidiError, `${code}: ${error}`);
    assert.equal(error.code, code);
  }
  assert.equal(failure(() => readMidi(new Uint8Array(16_000_001))).code, "too_large");
});

test("two tracks with tempo changes and 3/4 give parts, measures and seconds", () => {
  const conductor = [
    [0, bytes(0xff, 0x51, 0x03, 0x07, 0xa1, 0x20)],
    [960, bytes(0xff, 0x51, 0x03, 0x0f, 0x42, 0x40)],
    [960, bytes(0xff, 0x58, 0x04, 0x03, 0x02, 0x18, 0x08)],
    [2000, bytes(0xff, 0x01, 0x01, 0x78)]
  ];
  const treble = [[0, bytes(0xff, 0x03, 0x04, ...text("Keys"))], [0, bytes(0xc0, 0x00)], [0, bytes(0x90, 0x3c, 0x64)], [1440, bytes(0x80, 0x3c, 0)]];
  const bass = [[480, bytes(0xc1, 0x20)], [0, bytes(0x91, 0x3c, 0x30)], [480, bytes(0x81, 0x3c, 0)]];
  const score = readMidi(smf([conductor, treble, bass]));
  assert.equal(score.notes.length, 2);
  assert.equal(score.parts.length, 2);
  assert.equal(score.parts[0].name, "Keys · PORT 1 · CH 1 · GM 1");
  assert.equal(score.parts[1].name, "Track 3 · PORT 1 · CH 2 · GM 33");
  assert.deepEqual(score.measures.map((measure) => measure.start), [0, 4, 7]);
  assert.equal(score.measures[1].beats, 3);
  assert.deepEqual(score.notes.map((note) => note.measure), [1, 1]);
  const clock = scoreClock(score);
  const keys = score.notes.find((note) => note.pitch === 60 && note.partId === score.parts[0].id);
  assert.equal(clock(keys.onset + keys.duration), 2);
  const chosen = selectParts(score, [score.parts[1].id]);
  assert.equal(chosen.notes.length, 1);
  assert.equal(chosen.duration, score.duration);
  assert.equal(score.notes.length, 2);
  assert.equal(failure(() => selectParts(score, [])).code, "select_parts");
  assert.equal(failure(() => selectParts(score, ["nope"])).code, "select_parts");
});

test("scoreClock follows a tempo change inside a note", () => {
  const clock = scoreClock({ tempos: [{ onset: 0, bpm: 120 }, { onset: 2, bpm: 60 }] });
  assert.equal(clock(1), 0.5);
  assert.equal(clock(5), 4);
  assert.equal(clock(8), 7);
});

test("percussion-only and note-less files leave nothing to select", () => {
  const drums = readMidi(smf([[[0, bytes(0x99, 0x24, 0x40)], [480, bytes(0x89, 0x24, 0)]]], { format: 0 }));
  assert.equal(drums.parts.length, 1);
  assert.equal(drums.parts[0].active, false);
  assert.equal(failure(() => selectParts(drums, [drums.parts[0].id])).code, "select_parts");
  const empty = readMidi(smf([[[0, bytes(0xff, 0x03, 0x01, 0x78)]]], { format: 0 }));
  assert.deepEqual(empty.parts, []);
  assert.deepEqual(empty.notes, []);
});

test("previewPlan keeps original pitches, starts at the first note and stops at 30 seconds", () => {
  const low = readMidi(smf([[[960, bytes(0x90, 0x1e, 0x64)], [480, bytes(0x80, 0x1e, 0)]]], { format: 0 }));
  const plan = previewPlan(low, [low.parts[0].id]);
  assert.equal(plan.notes[0].midi, 30);
  assert.deepEqual([plan.notes[0].start, plan.notes[0].end], [0, 0.5]);
  assert.equal(plan.outside, 0);

  // 100 notes, one per second at 120 bpm (two per second -> every 2 quarters = 1 s): only the first 30 s are kept.
  const events = [];
  for (let i = 0; i < 100; i++) events.push([i === 0 ? 0 : 480, bytes(0x90, 0x3c, 0x40)], [240, bytes(0x80, 0x3c, 0)]);
  const long = readMidi(smf([events], { format: 0 }));
  const cut = previewPlan(long, [long.parts[0].id]);
  assert.equal(cut.duration, 30);
  assert.ok(cut.notes.length >= 30 && cut.notes.length < 100);
  assert.ok(cut.notes.every((note) => note.start < 30 && note.end <= 30));

  const outside = readMidi(smf([[[0, bytes(0x90, 0x14, 0x40)], [0, bytes(0x90, 0x3c, 0x40)], [480, bytes(0x80, 0x14, 0)], [0, bytes(0x80, 0x3c, 0)]]], { format: 0 }));
  const mixed = previewPlan(outside, [outside.parts[0].id]);
  assert.equal(mixed.outside, 1);
  assert.deepEqual(mixed.notes.map((note) => note.midi), [60]);
});

test("notes one tick apart keep distinct tick positions", () => {
  const score = readMidi(smf([[[479, bytes(0x90, 0x3c, 0x40)], [1, bytes(0x90, 0x40, 0x40)], [10, bytes(0x80, 0x3c, 0)], [0, bytes(0x80, 0x40, 0)]]], { format: 0 }));
  assert.deepEqual(score.notes.map((note) => note.onsetTicks), [479, 480]);
});
