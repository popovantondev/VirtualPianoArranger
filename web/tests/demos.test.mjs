import test from "node:test";
import assert from "node:assert/strict";
import { DEMOS, LEVELS, LEVEL_LABELS, demoEvents, demoPlan } from "../demos.js";
import { parseLetters, renderTokens } from "../js/letters.js";

const byId = (id) => DEMOS.find((demo) => demo.id === id);
const endOf = (demo) => Math.max(...demo.notes.map(([, start, length]) => start + length));

test("public-domain pieces with names in three languages", () => {
  assert.deepEqual(DEMOS.map((demo) => demo.id).sort(), ["fur-elise", "fur-elise-two-hands", "greensleeves", "ode-to-joy", "pachelbel-canon", "prelude-bwv846", "rondo-alla-turca", "twinkle"]);
  for (const demo of DEMOS) {
    for (const field of ["title", "composer"]) {
      for (const lang of ["ru", "de", "en"]) {
        assert.ok(typeof demo[field][lang] === "string" && demo[field][lang].length > 0, `${demo.id} ${field} ${lang}`);
      }
    }
    assert.ok(demo.bpm > 0 && demo.beatsPerMeasure > 0, demo.id);
  }
});

test("every note is inside the 36-96 keyboard and has a positive length", () => {
  for (const demo of DEMOS) {
    assert.ok(demo.notes.length > 10, demo.id);
    for (const [midi, start, length] of demo.notes) {
      assert.ok(Number.isInteger(midi) && midi >= 36 && midi <= 96, `${demo.id} pitch ${midi}`);
      assert.ok(start >= 0, `${demo.id} start ${start}`);
      assert.ok(length > 0, `${demo.id} length ${length}`);
    }
  }
});

test("notes are in time order and the music fills whole measures", () => {
  for (const demo of DEMOS) {
    const starts = demo.notes.map(([, start]) => start);
    assert.deepEqual(starts, [...starts].sort((a, b) => a - b), demo.id);
    const pickup = demo.pickup || 0;
    const bars = (endOf(demo) - pickup) / demo.beatsPerMeasure;
    assert.equal(bars, Math.round(bars), `${demo.id} has ${bars} measures`);
  }
});

test("Ode to Joy: first phrase and its length are as in the score", () => {
  const ode = byId("ode-to-joy");
  assert.deepEqual(ode.notes.slice(0, 15).map(([midi]) => midi), [64, 64, 65, 67, 67, 65, 64, 62, 60, 60, 62, 64, 64, 62, 62]);
  assert.deepEqual(ode.notes[12].slice(1), [12, 1.5]);
  assert.equal(ode.notes.length, 62);
  assert.equal(endOf(ode), 64);
});

test("the other melodies start with their well-known notes", () => {
  assert.deepEqual(byId("twinkle").notes.slice(0, 7).map(([midi]) => midi), [60, 60, 67, 67, 69, 69, 67]);
  assert.equal(endOf(byId("twinkle")), 48);
  assert.deepEqual(byId("fur-elise").notes.slice(0, 8).map(([midi]) => midi), [76, 75, 76, 75, 76, 71, 74, 72]);
  assert.equal(byId("greensleeves").notes[0][0], 69);
});

test("demoEvents groups notes into events and numbers measures", () => {
  const ode = demoEvents(byId("ode-to-joy"));
  assert.equal(ode.length, 62);
  assert.deepEqual(ode[0], { measure: 1, time: 0, notes: [64] });
  assert.equal(ode[ode.length - 1].measure, 16);
  const elise = demoEvents(byId("fur-elise"));
  // Two pickup notes form measure 1, the first full measure is measure 2.
  assert.deepEqual(elise.slice(0, 3).map((event) => event.measure), [1, 1, 2]);
  const chord = demoEvents({ bpm: 60, beatsPerMeasure: 4, notes: [[60, 0, 1], [64, 0, 1], [62, 1, 1]] });
  assert.deepEqual(chord.map((event) => event.notes), [[60, 64], [62]]);
});

test("demoPlan converts beats to seconds and links notes to events", () => {
  const plan = demoPlan({ bpm: 120, beatsPerMeasure: 4, notes: [[60, 0, 1], [62, 1, 2]] }, { gap: 0 });
  assert.equal(plan.duration, 1.5);
  assert.deepEqual(plan.notes.map((note) => [note.midi, note.start, note.end, note.token]), [[60, 0, 0.5, 0], [62, 0.5, 1.5, 1]]);
  const ode = demoPlan(byId("ode-to-joy"));
  assert.ok(Math.abs(ode.duration - 64 * 60 / byId("ode-to-joy").bpm) < 1e-9);
  assert.ok(ode.notes.every((note) => note.end > note.start && note.token >= 0));
});

test("every demo turns into letters whose tokens line up with its events", () => {
  for (const demo of DEMOS) {
    const events = demoEvents(demo);
    const { text, tokens, outside } = renderTokens(events, "en", { chordValue: 40, spacing: true });
    assert.deepEqual(outside, [], demo.id);
    assert.deepEqual(tokens.map((token) => token.event), events.map((_, index) => index), demo.id);
    assert.deepEqual(parseLetters(text, "en").map((token) => token.notes), events.map((event) => event.notes), demo.id);
    const plan = demoPlan(demo);
    assert.ok(plan.notes.every((note) => events[note.token].notes.includes(note.midi)), demo.id);
  }
});

test("Fur Elise third bar has the E4 between the rest and the E5-D#5 pair", () => {
  const midis = byId("fur-elise").notes.map(([midi]) => midi);
  const at = midis.findIndex((midi, i) => midi === 72 && midis[i + 1] === 64);
  assert.ok(at >= 0, "C5 then E4 expected");
  assert.deepEqual(midis.slice(at, at + 4), [72, 64, 76, 75]);
  const c5 = byId("fur-elise").notes[at];
  const e4 = byId("fur-elise").notes[at + 1];
  assert.equal(e4[1], c5[1] + 0.75);
});

test("every demo has a level with labels in three languages; cards go from easy to hard", () => {
  for (const demo of DEMOS) {
    assert.ok(LEVELS.includes(demo.level), demo.id);
    for (const lang of ["ru", "de", "en"]) assert.ok(LEVEL_LABELS[demo.level][lang].length > 0, `${demo.id} ${lang}`);
  }
  const order = DEMOS.map((demo) => LEVELS.indexOf(demo.level));
  assert.deepEqual(order, [...order].sort((a, b) => a - b));
  assert.equal(DEMOS.filter((demo) => demo.level !== "easy").length, 4);
});

test("medium and hard pieces have sounding-together notes (two hands or held notes)", () => {
  for (const demo of DEMOS.filter((d) => d.level !== "easy")) {
    const overlap = demo.notes.some(([, start, length], i) =>
      demo.notes.some(([, other, otherLength], j) => i !== j && start < other + otherLength && other < start + length));
    assert.ok(overlap, demo.id);
  }
});

test("every demo makes letters without ? (all notes are playable)", () => {
  for (const demo of DEMOS) {
    for (const layout of ["en", "ru", "de"]) {
      const { text } = renderTokens(demoEvents(demo), layout, { chordValue: 40, spacing: true });
      assert.ok(!text.includes("?"), `${demo.id} ${layout}`);
    }
  }
});

test("Prelude BWV 846: held n1 and n2 plus sixteenths n3-n5, no added bass", () => {
  const prelude = byId("prelude-bwv846");
  const right = (from, to) => prelude.notes.filter(([, start, length]) => length === 0.25 && start >= from && start < to).map(([midi]) => midi);
  assert.deepEqual(right(0, 4), [67, 72, 76, 67, 72, 76, 67, 72, 76, 67, 72, 76]);
  assert.deepEqual(right(4, 8), [69, 74, 77, 69, 74, 77, 69, 74, 77, 69, 74, 77]);
  // Bar 1: n1 = C4 held 2 beats (twice per bar), n2 = E4 enters a sixteenth later and is held 1.75 beats.
  assert.deepEqual(prelude.notes.filter(([, start]) => start < 4 && start % 2 === 0).map(([midi, start, length]) => [midi, start, length]), [[60, 0, 2], [60, 2, 2]]);
  assert.deepEqual(prelude.notes.filter(([, start]) => start < 4 && start % 2 === 0.25).map(([midi, start, length]) => [midi, start, length]), [[64, 0.25, 1.75], [64, 2.25, 1.75]]);
  assert.ok(prelude.notes.every(([midi]) => midi >= 59), "nothing below B3: Bach has no extra bass here");
  assert.equal(prelude.notes.length, 8 * 16);
  assert.equal(endOf(prelude), 32);
  // Harmony of bar 3 (G7/B) and bar 6 (D7/C): the pitch classes of each bar.
  const classes = (from) => [...new Set(prelude.notes.filter(([, start]) => start >= from && start < from + 4).map(([midi]) => midi % 12))].sort((a, b) => a - b);
  assert.deepEqual(classes(8), [2, 5, 7, 11]);
  assert.deepEqual(classes(20), [0, 2, 6, 9]);
});

test("Fur Elise two hands: theme A right hand matches the single-line version, left hand is A-E-A / E-E-G#", () => {
  const two = byId("fur-elise-two-hands");
  const single = byId("fur-elise");
  assert.deepEqual(two.notes.filter(([midi]) => midi >= 60).map(([midi]) => midi), single.notes.map(([midi]) => midi));
  const left = two.notes.filter(([midi]) => midi < 60);
  assert.deepEqual(left.slice(0, 6).map(([midi]) => midi), [45, 52, 57, 40, 52, 56]);
  assert.equal(left[0][1], 2);
  // Each left-hand figure is three sixteenths (beats +0, +0.25, +0.5 of the bar), then a rest of three sixteenths.
  assert.deepEqual(left.slice(0, 6).map(([, start, length]) => [start, length]), [[2, 0.25], [2.25, 0.25], [2.5, 0.25], [3.5, 0.25], [3.75, 0.25], [4, 0.25]]);
  assert.equal(endOf(two), 12.5);
});

test("Turkish March: first bars B-A-G#-A-C, D-C-B-C-E, with an Am bass and chord", () => {
  const turca = byId("rondo-alla-turca");
  assert.deepEqual(turca.notes.filter(([, , length]) => length === 0.25).slice(0, 8).map(([midi]) => midi), [71, 69, 68, 69, 74, 72, 71, 72]);
  assert.deepEqual(turca.notes.filter(([midi, , length]) => length === 1 && midi >= 72).map(([midi]) => midi).slice(0, 2), [72, 76]);
  // B-A-G#-A is a one-beat pickup: the bass starts with the first full bar, on the C.
  assert.equal(turca.pickup, 1);
  const events = demoEvents(turca);
  assert.deepEqual(events[0].notes, [71]);
  assert.equal(events[0].measure, 1);
  assert.deepEqual(events[4].notes, [45, 72]);
  assert.deepEqual(events[5].notes, [57, 60, 64, 74]);
  assert.equal(events[4].measure, 2);
  assert.equal(Math.min(...turca.notes.filter(([midi]) => midi < 60).map(([, start]) => start)), 1);
  assert.equal(endOf(turca), 9);
});

test("Pachelbel Canon: ground bass D A B F# G D G A, melody enters on the second round", () => {
  const canon = byId("pachelbel-canon");
  assert.deepEqual(canon.notes.filter(([, start]) => start < 16).map(([midi]) => midi), [50, 45, 47, 42, 43, 38, 43, 45]);
  const melody = canon.notes.filter(([midi, start]) => start >= 16 && midi >= 60);
  assert.deepEqual(melody.map(([midi]) => midi), [78, 76, 74, 73, 71, 69, 71, 73]);
  assert.equal(melody[0][1], 16);
  assert.equal(endOf(canon), 32);
  // Usual tempo: a bass note lasts about a second (half notes at 120-140 beats per minute).
  assert.ok(canon.bpm >= 120 && canon.bpm <= 140, `bpm ${canon.bpm}`);
});