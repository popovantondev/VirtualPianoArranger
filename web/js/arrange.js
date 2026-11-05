// Turning a Score into events for the 61-key keyboard. Pure module (no DOM), tested with node.
// Port of arrangement.py (simplify_notes, select_pitches), music_time.py (grouped_events) and
// main.py (key_position, score_transposition, find_best_transposition); `single` mode of letter_practice.py.

import { LOW, HIGH } from "./keymap.js";
import { scoreClock } from "./midi.js";

// Python round(): halves go to the even neighbour.
export function roundHalfEven(x) {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff < 0.5) return floor;
  if (diff > 0.5) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1;
}

// Distinct pitches by rank: the two ends first, then evenly spread interior notes.
// chordValue 10 and below keeps everything, 100 keeps two notes.
export function simplifyNotes(notes, chordValue) {
  const sorted = [...new Set(notes)].sort((a, b) => a - b);
  if (sorted.length <= 2 || chordValue <= 10) return sorted;
  const limit = Math.max(2, roundHalfEven(6 - ((chordValue - 10) * 4) / 90));
  if (sorted.length <= limit) return sorted;
  const selected = [sorted[0], sorted[sorted.length - 1]];
  const interior = sorted.slice(1, -1);
  const slots = limit - 2;
  if (slots) {
    const indexes = slots === 1
      ? [Math.floor(interior.length / 2)]
      : Array.from({ length: slots }, (_, i) => roundHalfEven((i * (interior.length - 1)) / (slots - 1)));
    for (const index of indexes) selected.push(interior[index]);
  }
  return [...new Set(selected)].sort((a, b) => a - b);
}

// Shift, simplify, then split into notes that fit the keyboard (36..96) and the rest.
export function selectPitches(notes, semitones, chordValue = 0) {
  const selected = simplifyNotes(notes.map((pitch) => pitch + semitones), chordValue);
  return {
    inside: selected.filter((pitch) => pitch >= LOW && pitch <= HIGH),
    outside: selected.filter((pitch) => pitch < LOW || pitch > HIGH)
  };
}

// Simultaneous notes (same measure, same onset tick) become one event, in time order.
// Event = {measure, time /* quarters */, timeSec, duration /* longest note */, notes /* sorted distinct */, sources}.
// `sources` keeps every real note ({pitch, end, velocity}) so that playback uses true durations.
export function groupedEvents(score) {
  const groups = new Map();
  for (const note of score.notes) {
    const moment = note.onsetTicks !== undefined ? note.onsetTicks : note.onset;
    const key = `${note.measure}|${moment}`;
    if (!groups.has(key)) groups.set(key, { measure: note.measure, moment, onset: note.onset, items: [] });
    groups.get(key).items.push(note);
  }
  const clock = scoreClock(score);
  return [...groups.values()]
    .sort((a, b) => a.measure - b.measure || a.moment - b.moment)
    .map(({ measure, onset, items }) => ({
      measure,
      time: onset,
      timeSec: clock(onset),
      duration: Math.max(...items.map((note) => note.duration)),
      notes: [...new Set(items.map((note) => note.pitch))].sort((a, b) => a - b),
      sources: items.map((note) => ({ pitch: note.pitch, end: note.end !== undefined ? note.end : note.onset + note.duration, velocity: note.velocity }))
    }));
}

// "Melody only": the top note of every event (mode `single`).
export function melodyOnly(events) {
  return events.map((event) => {
    if (!event.notes.length) return event;
    const top = event.notes[event.notes.length - 1];
    return {
      ...event,
      notes: [top],
      ...(event.sources ? { sources: event.sources.filter((source) => source.pitch === top) } : {})
    };
  });
}

// ---------- Best transposition (main.py) ----------
const BLACK = new Set([1, 3, 6, 8, 10]);

// Left-to-right position on the virtual piano: index of the white key, +0.35 for a black key.
function keyPosition(midi) {
  if (midi < LOW || midi > HIGH) return null;
  let whites = 0;
  for (let pitch = LOW; pitch <= midi; pitch++) if (!BLACK.has(pitch % 12)) whites++;
  return whites - 1 + (BLACK.has(midi % 12) ? 0.35 : 0);
}
const POSITIONS = new Map();
for (let midi = LOW; midi <= HIGH; midi++) POSITIONS.set(midi, keyPosition(midi));

export function scoreTransposition(events, semitones, chordValue, comfort) {
  let score = 0;
  let outside = 0;
  let previousCenter = null;
  for (const event of events) {
    const notes = simplifyNotes(event.notes.map((pitch) => pitch + semitones), chordValue);
    const modifiers = new Set(notes.filter((pitch) => pitch >= LOW && pitch <= HIGH).map((pitch) => BLACK.has(((pitch % 12) + 12) % 12)));
    if (modifiers.size > 1) score += 1000;
    const positions = [];
    for (const pitch of notes) {
      const position = POSITIONS.get(pitch);
      if (position === undefined) {
        outside++;
        score += 100000;
        continue;
      }
      positions.push(position);
      if (BLACK.has(pitch % 12)) score += 0.25;
    }
    if (!positions.length) continue;
    if (positions.length > 2) score += (positions.length - 2) * (4 + comfort / 20);
    score += (Math.max(...positions) - Math.min(...positions)) * (0.1 + comfort / 400);
    const center = positions.reduce((sum, value) => sum + value, 0) / positions.length;
    if (previousCenter !== null) score += Math.max(0, Math.abs(center - previousCenter) - 7) * (0.15 + comfort / 500);
    previousCenter = center;
  }
  return { score, outside };
}

// Best shift in -12..12: smallest (score, outside, |shift|, shift).
export function findBestTransposition(events, chordValue, comfort = 50) {
  let best = null;
  for (let semitones = -12; semitones <= 12; semitones++) {
    const { score, outside } = scoreTransposition(events, semitones, chordValue, comfort);
    const candidate = [score, outside, Math.abs(semitones), semitones];
    if (!best || compareTuples(candidate, best) < 0) best = candidate;
  }
  return best[3];
}

function compareTuples(a, b) {
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  return 0;
}

// ---------- Playback of the result ----------
// Plan = {duration, notes: [{midi, start, end, velocity, token}]} in seconds; `token` is the event index,
// which is also the index of its token in the letters (renderTokens keeps events in time order).
// Notes that do not fit the keyboard stay silent, like the letters. trimStart drops the silence before the first note.
export function eventsToPlan(events, semitones, chordValue, clock, { trimStart = false } = {}) {
  const notes = [];
  events.forEach((event, index) => {
    const { inside } = selectPitches(event.notes, semitones, chordValue);
    if (!inside.length) return;
    const chosen = new Set(inside);
    const start = clock(event.time);
    const sources = event.sources && event.sources.length
      ? event.sources.filter((source) => chosen.has(source.pitch + semitones))
      : inside.map((pitch) => ({ pitch: pitch - semitones, end: event.time + (event.duration || 0), velocity: undefined }));
    for (const source of sources) {
      const end = Math.max(start + 0.02, clock(source.end));
      notes.push({ midi: source.pitch + semitones, start, end, ...(source.velocity !== undefined ? { velocity: source.velocity } : {}), token: index });
    }
  });
  notes.sort((a, b) => a.start - b.start || a.midi - b.midi);
  const shift = trimStart && notes.length ? notes[0].start : 0;
  if (shift) for (const note of notes) { note.start -= shift; note.end -= shift; }
  return { duration: notes.reduce((last, note) => Math.max(last, note.end), 0), notes };
}

// A demo ({bpm, beatsPerMeasure, pickup?, notes: [[midi, startBeat, lengthBeats]]}) as a Score,
// so that demos and MIDI files take the same road to the letters.
export function demoToScore(demo, { velocity = 96 } = {}) {
  const offset = demo.pickup ? demo.pickup - demo.beatsPerMeasure : 0;
  const measureOf = (time) => Math.floor((time - offset + 1e-9) / demo.beatsPerMeasure) + 1;
  const notes = demo.notes.map(([pitch, onset, duration], index) => ({
    id: `demo:${index}`, partId: "demo", pitch, velocity, onset, duration, end: onset + duration, measure: measureOf(onset)
  }));
  const last = notes.reduce((max, note) => Math.max(max, note.measure), 1);
  const measures = Array.from({ length: last }, (_, i) => ({
    number: i + 1, start: i === 0 ? 0 : offset + i * demo.beatsPerMeasure, beats: demo.beatsPerMeasure, beatType: 4
  }));
  const pitches = notes.map((note) => note.pitch);
  return {
    exact: true,
    warnings: [],
    parts: [{ id: "demo", name: "demo", percussion: false, noteCount: notes.length, low: Math.min(...pitches), high: Math.max(...pitches), active: true }],
    notes: notes.sort((a, b) => a.onset - b.onset),
    tempos: [{ onset: 0, bpm: demo.bpm }],
    measures,
    duration: notes.reduce((max, note) => Math.max(max, note.end), 0)
  };
}
