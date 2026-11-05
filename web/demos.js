// Demo melodies. All are folk tunes or works by composers who died long ago (public domain).
// The notes were typed in by hand as data: [midi, startBeat, lengthInBeats]; a beat is a quarter note.
// Nothing here comes from other sheet-music sites.

// Writes consecutive notes: items are [midi, length] (midi null = rest); the clock starts at `begin`.
function line(begin, items) {
  const notes = [];
  let time = begin;
  for (const [midi, length] of items) {
    if (midi !== null) notes.push([midi, time, length]);
    time += length;
  }
  return notes;
}

// Pitches (middle C = 60).
const C4 = 60, D4 = 62, E4 = 64, F4 = 65, G4 = 67, A4 = 69, B4 = 71;
const C5 = 72, D5 = 74, E5 = 76, F5 = 77, G5 = 79;
const G3 = 55;
const DS5 = 75, GS4 = 68, FS4 = 66; // D#5, G#4, F#4

// Beethoven, "Ode to Joy" (4/4).
const odeBars = {
  rise: [[E4, 1], [E4, 1], [F4, 1], [G4, 1], [G4, 1], [F4, 1], [E4, 1], [D4, 1], [C4, 1], [C4, 1], [D4, 1], [E4, 1]],
  endA: [[E4, 1.5], [D4, 0.5], [D4, 2]],
  endB: [[D4, 1.5], [C4, 0.5], [C4, 2]],
  middle: [
    [D4, 1], [D4, 1], [E4, 1], [C4, 1],
    [D4, 1], [E4, 0.5], [F4, 0.5], [E4, 1], [C4, 1],
    [D4, 1], [E4, 0.5], [F4, 0.5], [E4, 1], [D4, 1],
    [C4, 1], [D4, 1], [G3, 2]
  ]
};
const ode = line(0, [
  ...odeBars.rise, ...odeBars.endA,
  ...odeBars.rise, ...odeBars.endB,
  ...odeBars.middle,
  ...odeBars.rise, ...odeBars.endB
]);

// Beethoven, "Fur Elise", opening theme (3/8; two sixteenth notes of pickup, then bars of 1.5 beats).
const S = 0.25;
const elise = line(0, [
  [E5, S], [DS5, S],
  [E5, S], [DS5, S], [E5, S], [B4, S], [D5, S], [C5, S],
  [A4, 2 * S], [null, S], [C4, S], [E4, S], [A4, S],
  [B4, 2 * S], [null, S], [E4, S], [GS4, S], [B4, S],
  [C5, 2 * S], [null, S], [E4, S], [E5, S], [DS5, S],
  [E5, S], [DS5, S], [E5, S], [B4, S], [D5, S], [C5, S],
  [A4, 2 * S], [null, S], [C4, S], [E4, S], [A4, S],
  [B4, 2 * S], [null, S], [E4, S], [C5, S], [B4, S],
  [A4, 6 * S]
]);

// "Ah! vous dirai-je, maman" (French folk song, 18th century), 2/4.
const twinklePhrase = (a, b, c, last) => [[a, 1], [a, 1], [b, 1], [b, 1], [c, 1], [c, 1], [last, 2]];
const twinkle = line(0, [
  ...twinklePhrase(C4, G4, A4, G4),
  ...twinklePhrase(F4, E4, D4, C4),
  ...twinklePhrase(G4, F4, E4, D4),
  ...twinklePhrase(G4, F4, E4, D4),
  ...twinklePhrase(C4, G4, A4, G4),
  ...twinklePhrase(F4, E4, D4, C4)
]);

// "Greensleeves" (English folk song, 16th century), 6/8; the beat is a quarter note, an eighth is 0.5.
const e = 0.5;
const greenA = [[C5, 2 * e], [D5, e], [E5, 2 * e], [F5, e]];
const greenB = [[E5, 2 * e], [D5, e], [B4, 2 * e], [G4, e]];
const greenC = [[A4, 2 * e], [B4, e], [C5, e], [B4, e], [A4, e]];
const greenEnd = [[GS4, e], [FS4, e], [GS4, e], [A4, 3 * e]];
const greenChorus = [[G5, 3 * e], [G5, 2 * e], [F5, e]];
const greensleeves = line(0, [
  [A4, e],
  ...greenA, ...greenB,
  [A4, 2 * e], [B4, e], [C5, 2 * e], [A4, e],
  [A4, 2 * e], [GS4, e], [A4, 2 * e], [B4, e],
  [GS4, 2 * e], [E4, 3 * e],
  [A4, e],
  ...greenA, ...greenB, ...greenC, ...greenEnd,
  ...greenChorus, ...greenB, ...greenC, ...greenEnd,
  ...greenChorus, ...greenB, ...greenC, [A4, 6 * e]
]);

// Merges hands into one list in time order (stable: the first list wins on ties).
function together(...hands) {
  return hands.flat().sort((a, b) => a[1] - b[1]);
}

// Bach, Prelude in C major BWV 846, bars 1-8 (4/4). Each bar has the figure n1 n2 n3 n4 n5 n3 n4 n5 twice
// (sixteenths); n1 is held for 2 beats and n2 enters a sixteenth later and is held 1.75 beats, so only n3 n4 n5
// are short notes. There is no separate bass. Chords: C, Dm7/C, G7/B, C, Am/C, D7/C, G/B, Cmaj7/B.
const preludeBars = [
  { bass: 48, n: [60, 64, 67, 72, 76] },
  { bass: 48, n: [60, 62, 69, 74, 77] },
  { bass: 47, n: [59, 62, 67, 74, 77] },
  { bass: 48, n: [60, 64, 67, 72, 76] },
  { bass: 48, n: [60, 64, 69, 76, 81] },
  { bass: 48, n: [60, 62, 66, 69, 74] },
  { bass: 47, n: [59, 62, 67, 74, 79] },
  { bass: 47, n: [59, 60, 64, 67, 72] }
];
const prelude = preludeBars.flatMap((bar, index) =>
  [0, 2].flatMap((half) => {
    const base = index * 4 + half;
    return [
      [bar.n[0], base, 2],
      [bar.n[1], base + 0.25, 1.75],
      ...[2, 3, 4, 2, 3, 4].map((k, i) => [bar.n[k], base + 0.5 + i * 0.25, 0.25])
    ];
  }));

// Beethoven, "Fur Elise", theme A with the left hand (3/8; the same right hand as above, the left hand
// plays A-E-A (A minor) or E-E-G# (E major) in eighths from bar 2).
const A2 = 45, E3 = 52, A3 = 57, E2 = 40, GS3 = 56;
const eliseRight = line(0, [
  [E5, S], [DS5, S],
  [E5, S], [DS5, S], [E5, S], [B4, S], [D5, S], [C5, S],
  [A4, 2 * S], [null, S], [C4, S], [E4, S], [A4, S],
  [B4, 2 * S], [null, S], [E4, S], [GS4, S], [B4, S],
  [C5, 2 * S], [null, S], [E4, S], [E5, S], [DS5, S],
  [E5, S], [DS5, S], [E5, S], [B4, S], [D5, S], [C5, S],
  [A4, 2 * S], [null, S], [C4, S], [E4, S], [A4, S],
  [B4, 2 * S], [null, S], [E4, S], [C5, S], [B4, S],
  [A4, 6 * S]
]);
// Each figure is three sixteenths on the first sixteenths of the bar, then a rest of three sixteenths
// (the right hand plays C-E-A / B-E-G#-B there).
const am = [[A2, S], [E3, S], [A3, S], [null, 3 * S]];
const eMajor = [[E2, S], [E3, S], [GS3, S], [null, 3 * S]];
const eliseLeft = line(0, [
  [null, 2 * S], [null, 6 * S],
  ...am, ...eMajor, ...am,
  [null, 6 * S],
  ...am, ...eMajor, ...am
]);
const eliseTwoHands = together(eliseRight, eliseLeft);

// Mozart, "Rondo alla Turca" from Piano Sonata K. 331, bars 1-4 (2/4, A minor), bass + chord in the left hand.
// B-A-G#-A is a one-beat pickup; the left hand starts with the first full bar (beat 1).
const B5 = 83, A5 = 81, GS5 = 80, C6 = 84;
const turca = line(0, [
  [B4, S], [A4, S], [GS4, S], [A4, S], [C5, 1],
  [D5, S], [C5, S], [B4, S], [C5, S], [E5, 1],
  [F5, S], [E5, S], [DS5, S], [E5, S], [B5, S], [A5, S], [GS5, S], [A5, S],
  [B5, S], [A5, S], [GS5, S], [A5, S], [C6, 1]
]);
const turcaLeft = [
  [A2, 1, 1], [[A3, C4, E4], 2, 1],
  [A2, 3, 1], [[A3, C4, E4], 4, 1],
  [E2, 5, 1], [[E3, GS3, 59], 6, 1],
  [E2, 7, 1], [[A3, C4, E4], 8, 1]
].flatMap(([pitch, start, length]) => (Array.isArray(pitch) ? pitch : [pitch]).map((midi) => [midi, start, length]));
const turcaTwoHands = together(turca, turcaLeft);

// Pachelbel, Canon in D, bars 1-8 (4/4): the ground bass in half notes (D A B F# G D G A), twice;
// the melody enters on the second round with F# E D C# B A B C#.
const D2 = 38, D3 = 50, FS2 = 42, G2 = 43, B2 = 47, FS5 = 78, CS5 = 73;
const groundBass = [D3, 45, B2, FS2, G2, D2, G2, 45];
const canonBass = [...groundBass, ...groundBass].map((midi, index) => [midi, index * 2, 2]);
const canonMelody = [FS5, E5, D5, CS5, B4, A4, B4, CS5].map((midi, index) => [midi, 16 + index * 2, 2]);
const canon = together(canonBass, canonMelody);
// Difficulty labels shown on the demo cards.
export const LEVELS = ["easy", "medium", "hard"];
export const LEVEL_LABELS = {
  easy: { ru: "Легко", de: "Leicht", en: "Easy" },
  medium: { ru: "Средне", de: "Mittel", en: "Medium" },
  hard: { ru: "Сложно", de: "Schwer", en: "Hard" }
};

const ALL_DEMOS = [
  {
    id: "ode-to-joy",
    level: "easy",
    title: { ru: "Ода к радости", de: "Ode an die Freude", en: "Ode to Joy" },
    composer: { ru: "Людвиг ван Бетховен", de: "Ludwig van Beethoven", en: "Ludwig van Beethoven" },
    bpm: 100,
    beatsPerMeasure: 4,
    notes: ode
  },
  {
    id: "fur-elise",
    level: "easy",
    title: { ru: "К Элизе (начало)", de: "Für Elise (Anfang)", en: "Für Elise (opening)" },
    composer: { ru: "Людвиг ван Бетховен", de: "Ludwig van Beethoven", en: "Ludwig van Beethoven" },
    bpm: 100,
    beatsPerMeasure: 1.5,
    pickup: 0.5,
    notes: elise
  },
  {
    id: "twinkle",
    level: "easy",
    title: { ru: "Ah! vous dirai-je, maman", de: "Ah! vous dirai-je, maman", en: "Ah! vous dirai-je, maman (Twinkle)" },
    composer: { ru: "Французская народная песня", de: "Französisches Volkslied", en: "French folk song" },
    bpm: 100,
    beatsPerMeasure: 2,
    notes: twinkle
  },
  {
    id: "greensleeves",
    level: "easy",
    title: { ru: "Greensleeves", de: "Greensleeves", en: "Greensleeves" },
    composer: { ru: "Английская народная песня", de: "Englisches Volkslied", en: "English folk song" },
    bpm: 90,
    beatsPerMeasure: 3,
    pickup: 0.5,
    notes: greensleeves
  },
  {
    id: "prelude-bwv846",
    level: "hard",
    title: { ru: "Прелюдия до мажор BWV 846 (начало)", de: "Präludium C-Dur BWV 846 (Anfang)", en: "Prelude in C major BWV 846 (opening)" },
    composer: { ru: "Иоганн Себастьян Бах", de: "Johann Sebastian Bach", en: "Johann Sebastian Bach" },
    bpm: 72,
    beatsPerMeasure: 4,
    notes: prelude
  },
  {
    id: "fur-elise-two-hands",
    level: "medium",
    title: { ru: "К Элизе, тема A (двумя руками)", de: "Für Elise, Thema A (zweihändig)", en: "Für Elise, theme A (two hands)" },
    composer: { ru: "Людвиг ван Бетховен", de: "Ludwig van Beethoven", en: "Ludwig van Beethoven" },
    bpm: 100,
    beatsPerMeasure: 1.5,
    pickup: 0.5,
    notes: eliseTwoHands
  },
  {
    id: "rondo-alla-turca",
    level: "hard",
    title: { ru: "Турецкий марш (начало)", de: "Türkischer Marsch (Anfang)", en: "Turkish March (opening)" },
    composer: { ru: "Вольфганг Амадей Моцарт", de: "Wolfgang Amadeus Mozart", en: "Wolfgang Amadeus Mozart" },
    bpm: 88,
    beatsPerMeasure: 2,
    pickup: 1,
    notes: turcaTwoHands
  },
  {
    id: "pachelbel-canon",
    level: "medium",
    title: { ru: "Канон ре мажор (начало)", de: "Kanon in D-Dur (Anfang)", en: "Canon in D (opening)" },
    composer: { ru: "Иоганн Пахельбель", de: "Johann Pachelbel", en: "Johann Pachelbel" },
    bpm: 132, // the beat is a quarter, the bass moves in half notes: about 66 half notes a minute
    beatsPerMeasure: 4,
    notes: canon
  }
];
// Sorted from easy to hard; the order inside one level stays as written.
export const DEMOS = ALL_DEMOS.sort((a, b) => LEVELS.indexOf(a.level) - LEVELS.indexOf(b.level));

// Notes starting together form one event: {measure, time /* beats */, notes}. `pickup` is the length
// of an incomplete first measure; it still counts as measure 1.
export function demoEvents(demo) {
  const offset = demo.pickup ? demo.pickup - demo.beatsPerMeasure : 0;
  const groups = new Map();
  for (const [midi, start] of demo.notes) {
    if (!groups.has(start)) groups.set(start, []);
    groups.get(start).push(midi);
  }
  return [...groups.keys()].sort((a, b) => a - b).map((time) => ({
    measure: Math.floor((time - offset + 1e-9) / demo.beatsPerMeasure) + 1,
    time,
    notes: [...new Set(groups.get(time))].sort((a, b) => a - b)
  }));
}

// A plan for Player: seconds, each note linked to its event by `token`. `gap` is the shortening of a note
// in seconds, so repeated notes are heard separately.
export function demoPlan(demo, { gap = 0.04, velocity = 96 } = {}) {
  const seconds = (beats) => (beats * 60) / demo.bpm;
  const events = demoEvents(demo);
  const eventOf = new Map(events.map((event, index) => [event.time, index]));
  let duration = 0;
  const notes = demo.notes.map(([midi, start, length]) => {
    const end = seconds(start + length);
    duration = Math.max(duration, end);
    return { midi, start: seconds(start), end: Math.max(seconds(start) + 0.02, end - gap), velocity, token: eventOf.get(start) };
  });
  return { duration, notes };
}
