import test from "node:test";
import assert from "node:assert/strict";
import {
  roundHalfEven, simplifyNotes, selectPitches, groupedEvents, melodyOnly, findBestTransposition,
  eventsToPlan, demoToScore
} from "../js/arrange.js";
import { readMidi, scoreClock } from "../js/midi.js";
import { renderTokens } from "../js/letters.js";
import { DEMOS, demoEvents } from "../demos.js";

// Score like score() in test_arrangement.py: notes are [pitch, onset, duration] in quarters, 8 quarters, 120 bpm.
function makeScore(notes, tempos = [{ onset: 0, bpm: 120 }]) {
  return {
    exact: true,
    warnings: [],
    parts: [{ id: "P", name: "Piano" }],
    measures: [{ number: 1, start: 0 }],
    duration: 8,
    tempos,
    notes: notes.map(([pitch, onset, duration], i) => ({ id: String(i), partId: "P", pitch, velocity: 64, onset, duration, measure: 1 }))
  };
}

const events = (...groups) => groups.map((notes, i) => ({ measure: 1, time: i, duration: 1, notes }));

test("roundHalfEven rounds halves to the even neighbour like Python", () => {
  assert.deepEqual([0.5, 1.5, 2.5, 3.5, -0.5, 2.4, 2.6].map(roundHalfEven), [0, 2, 2, 4, 0, 2, 3]);
});

test("simplifyNotes: monotonic, ends kept, all at 10, two at 100", () => {
  const pitches = Array.from({ length: 12 }, (_, i) => 48 + i);
  let previous = pitches.length;
  for (let value = 0; value <= 100; value++) {
    const picked = simplifyNotes(pitches, value);
    assert.ok(picked.length <= previous, `value ${value}`);
    assert.deepEqual([picked[0], picked[picked.length - 1]], [48, 59]);
    previous = picked.length;
  }
  assert.deepEqual(simplifyNotes(pitches, 10), pitches);
  assert.deepEqual(simplifyNotes(pitches, 100), [48, 59]);
});

test("simplifyNotes picks interior notes with half-to-even rounding and removes duplicates", () => {
  // 6 notes, value 25 -> limit 5: interior indexes 0, round(1.5) = 2, 3 -> 49, 51, 52.
  assert.deepEqual(simplifyNotes([48, 49, 50, 51, 52, 53], 25), [48, 49, 51, 52, 53]);
  // 8 notes, value 25 -> interior indexes 0, round(2.5) = 2 (not 3), 5 -> 49, 51, 54 (Python gives the same).
  assert.deepEqual(simplifyNotes([48, 49, 50, 51, 52, 53, 54, 55], 25), [48, 49, 51, 54, 55]);
  assert.deepEqual(simplifyNotes([60, 60, 64, 64, 60], 100), [60, 64]);
  assert.deepEqual(simplifyNotes([], 40), []);
});

test("selectPitches splits at the keyboard edges 35/36/96/97", () => {
  assert.deepEqual(selectPitches([35, 36, 96, 97], 0), { inside: [36, 96], outside: [35, 97] });
  assert.deepEqual(selectPitches([24, 108], 12), { inside: [36], outside: [120] });
});

test("groupedEvents joins equal onsets inside a measure and keeps true durations per note", () => {
  const score = makeScore([[64, 3, 1], [60, 0, 2], [67, 0, 1], [60, 0, 3]]);
  const result = groupedEvents(score);
  assert.deepEqual(result.map((event) => event.notes), [[60, 67], [64]]);
  assert.deepEqual(result.map((event) => event.time), [0, 3]);
  assert.deepEqual(result.map((event) => event.timeSec), [0, 1.5]);
  assert.equal(result[0].duration, 3);
  assert.equal(result[0].sources.length, 3);
});

test("groupedEvents compares onsets by integer ticks", () => {
  // Two notes one tick apart at ppqn 3: 1/3 and 2/3 of a quarter are different events.
  const data = Uint8Array.from([
    0x4d, 0x54, 0x68, 0x64, 0, 0, 0, 6, 0, 0, 0, 1, 0, 3,
    0x4d, 0x54, 0x72, 0x6b, 0, 0, 0, 0x1c,
    1, 0x90, 60, 64, 0, 0x90, 64, 64, 1, 0x90, 67, 64,
    3, 0x80, 60, 0, 0, 0x80, 64, 0, 0, 0x80, 67, 0, 0, 0xff, 0x2f, 0
  ]);
  const score = readMidi(data);
  assert.deepEqual(groupedEvents(score).map((event) => event.notes), [[60, 64], [67]]);
});

test("findBestTransposition agrees with main.find_best_transposition", () => {
  // Expected values come from running the Python function on the same events (comfort 50).
  assert.equal(findBestTransposition(events([24], [26], [28], [30]), 40, 50), 12);
  assert.equal(findBestTransposition(events([100], [103], [105], [108]), 40, 50), -12);
  assert.equal(findBestTransposition(events([60], [62], [64]), 40, 50), 0);
  assert.equal(findBestTransposition(events([30], [110]), 40, 50), 6);
  assert.equal(findBestTransposition(events([60, 61, 64, 67, 70], [58, 62, 65]), 40, 50), -5);
  assert.equal(findBestTransposition(events([60, 61, 64, 67, 70], [58, 62, 65]), 100, 50), -1);
  assert.equal(findBestTransposition(events([40], [90], [40], [90], [41]), 40, 50), 1);
  assert.equal(findBestTransposition(events([40, 64, 87]), 40, 50), 1);
  // The penalty for mixing black and white keys in one chord decides this one (without it the answer would be 2).
  assert.equal(findBestTransposition(events([74, 83], [51, 84]), 40, 50), -1);
  assert.equal(findBestTransposition([], 40, 50), 0);
});

test("melodyOnly keeps the top note of each event", () => {
  const melody = melodyOnly(events([48, 60, 64], [52], []));
  assert.deepEqual(melody.map((event) => event.notes), [[64], [52], []]);
  const text = renderTokens(melody, "en", { chordValue: 40 }).text;
  assert.equal(text, "u0?");
});

test("eventsToPlan: letters and sound agree, outside notes stay silent, duplicates stay separate", () => {
  const score = makeScore([[35, 0, 1], [60, 0, 2], [97, 0, 1], [64, 3, 1]]);
  const list = groupedEvents(score);
  const plan = eventsToPlan(list, 0, 0, scoreClock(score));
  assert.deepEqual(plan.notes.map((note) => note.midi), [60, 64]);
  assert.deepEqual(plan.notes.map((note) => note.token), [0, 1]);
  assert.deepEqual(plan.notes.map((note) => [note.start, note.end]), [[0, 1], [1.5, 2]]);
  assert.equal(plan.notes[0].velocity, 64);
  const letters = renderTokens(list, "en", { semitones: 0, chordValue: 0 });
  assert.equal(letters.tokens.length, plan.notes.length);
  assert.deepEqual(letters.outside.map((item) => item.midi), [35, 97]);

  const same = makeScore([[60, 0, 1], [60, 0, 3], [64, 0, 2]]);
  const doubled = eventsToPlan(groupedEvents(same), 0, 100, scoreClock(same));
  assert.equal(doubled.notes.length, 3);
  const twice = makeScore([[60, 0, 1], [60, 0, 3]]);
  assert.deepEqual(eventsToPlan(groupedEvents(twice), 0, 0, scoreClock(twice)).notes.map((note) => note.end), [0.5, 1.5]);
});

test("eventsToPlan applies the transposition and the tempo map, and can trim the leading silence", () => {
  const score = makeScore([[24, 1, 4]], [{ onset: 0, bpm: 120 }, { onset: 2, bpm: 60 }]);
  const list = groupedEvents(score);
  const plan = eventsToPlan(list, 12, 0, scoreClock(score));
  assert.deepEqual(plan.notes.map((note) => [note.midi, note.start, note.end]), [[36, 0.5, 4]]);
  assert.equal(plan.duration, 4);
  const trimmed = eventsToPlan(list, 12, 0, scoreClock(score), { trimStart: true });
  assert.deepEqual(trimmed.notes.map((note) => [note.start, note.end]), [[0, 3.5]]);
  assert.deepEqual(eventsToPlan(list, 0, 0, scoreClock(score)).notes, []);
});

test("melodyOnly plan sounds only the top notes", () => {
  const score = makeScore([[48, 0, 2], [60, 0, 1], [64, 0, 1]]);
  const plan = eventsToPlan(melodyOnly(groupedEvents(score)), 0, 40, scoreClock(score));
  assert.deepEqual(plan.notes.map((note) => note.midi), [64]);
});

test("demoToScore takes the same road as MIDI and gives the demo's own events", () => {
  for (const demo of DEMOS) {
    const fromScore = groupedEvents(demoToScore(demo));
    const expected = demoEvents(demo);
    assert.deepEqual(fromScore.map((event) => [event.measure, event.time, event.notes]), expected.map((event) => [event.measure, event.time, event.notes]), demo.id);
  }
  const ode = demoToScore(DEMOS[0]);
  assert.equal(scoreClock(ode)(1), 0.6);
});
