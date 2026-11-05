// Key layout and labels for the 61-key piano (C2..C7).
// Pure module: no DOM access, so it can be tested with node.

export const LOW = 36;
export const HIGH = 96;
export const PHYSICAL_WHITE_KEYS = "1234567890QWERTYUIOPASDFGHJKLZXCVBNM";

const WHITE_PITCH_CLASSES = [0, 2, 4, 5, 7, 9, 11];
const BLACK_PITCH_CLASSES = [1, 3, 6, 8, 10];

const RU_BASE = {
  "1": "1", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7", "8": "8", "9": "9", "0": "0",
  Q: "й", W: "ц", E: "у", R: "к", T: "е", Y: "н", U: "г", I: "ш", O: "щ", P: "з",
  A: "ф", S: "ы", D: "в", F: "а", G: "п", H: "р", J: "о", K: "л", L: "д",
  Z: "я", X: "ч", C: "с", V: "м", B: "и", N: "т", M: "ь"
};
const SHIFT_DIGITS = {
  en: ["!", "@", "#", "$", "%", "^", "&", "*", "(", ")"],
  ru: ["!", "\"", "№", ";", "%", ":", "?", "*", "(", ")"],
  de: ["!", "\"", "§", "$", "%", "&", "/", "(", ")", "="]
};
const NOTE_NAMES = {
  ru: ["до", "до♯", "ре", "ре♯", "ми", "фа", "фа♯", "соль", "соль♯", "ля", "ля♯", "си"],
  de: ["C", "Cis", "D", "Dis", "E", "F", "Fis", "G", "Gis", "A", "Ais", "H"],
  en: ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"]
};
const NOTE_PREFIX_TO_PITCH_CLASS = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

// Fallback map: same rule as build_virtual_piano_map() in main.py.
export function buildKeyMap() {
  const map = new Map();
  let whiteIndex = 0;
  for (let midi = LOW; midi <= HIGH; midi++) {
    if (WHITE_PITCH_CLASSES.includes(midi % 12)) {
      map.set(midi, { key: PHYSICAL_WHITE_KEYS[whiteIndex], shift: false });
      whiteIndex++;
    } else {
      map.set(midi, { key: PHYSICAL_WHITE_KEYS[whiteIndex - 1], shift: true });
    }
  }
  return map;
}

// Parses virtual_piano_61_map.json: {"C2": {"physical_key": "1", "shift": false}, ...}
export function parseKeyMapJson(obj) {
  if (!obj || typeof obj !== "object") throw new Error("Key map is not an object");
  const map = new Map();
  for (const [name, entry] of Object.entries(obj)) {
    const match = /^([A-G])(#?)(-?\d+)$/.exec(name);
    if (!match || !entry || typeof entry.physical_key !== "string" || typeof entry.shift !== "boolean") {
      throw new Error(`Bad key map entry: ${name}`);
    }
    const midi = (Number(match[3]) + 1) * 12 + NOTE_PREFIX_TO_PITCH_CLASS[match[1]] + (match[2] ? 1 : 0);
    if (midi < LOW || midi > HIGH) throw new Error(`Key map note out of range: ${name}`);
    if (!PHYSICAL_WHITE_KEYS.includes(entry.physical_key)) throw new Error(`Unknown physical key: ${entry.physical_key}`);
    map.set(midi, { key: entry.physical_key, shift: entry.shift });
  }
  if (map.size !== HIGH - LOW + 1) throw new Error(`Key map has ${map.size} entries, expected 61`);
  return map;
}

let currentMap = buildKeyMap();
let reverseCodes = indexByPhysical(currentMap);

function indexByPhysical(map) {
  const index = new Map();
  for (const [midi, { key, shift }] of map) index.set(`${key}|${shift}`, midi);
  return index;
}

export function setKeyMap(map) {
  currentMap = map;
  reverseCodes = indexByPhysical(map);
}

export function isBlack(midi) {
  return BLACK_PITCH_CLASSES.includes(((midi % 12) + 12) % 12);
}

// Label of the key as printed in the program (render_key in main.py).
export function keyLabel(midi, layout) {
  const info = currentMap.get(midi);
  if (!info) return "?";
  const isDigit = /^[0-9]$/.test(info.key);
  if (info.shift && isDigit) return SHIFT_DIGITS[layout][(Number(info.key) + 9) % 10];
  let base = layout === "ru" ? RU_BASE[info.key] : info.key.toLowerCase();
  if (layout === "de") {
    if (base === "y") base = "z";
    else if (base === "z") base = "y";
  }
  return info.shift ? base.toUpperCase() : base;
}

export function noteName(midi, lang) {
  const names = NOTE_NAMES[lang] || NOTE_NAMES.en;
  return `${names[((midi % 12) + 12) % 12]}${Math.floor(midi / 12) - 1}`;
}

// Physical key from event.code: KeyQ, Digit1, Numpad1. Independent of the OS layout.
export function midiFromKeyEvent({ code, shiftKey }) {
  let physical = null;
  if (/^Key[A-Z]$/.test(code)) physical = code.slice(3);
  else if (/^Digit[0-9]$/.test(code)) physical = code.slice(5);
  else if (/^Numpad[0-9]$/.test(code)) physical = code.slice(6);
  if (physical === null) return null;
  const midi = reverseCodes.get(`${physical}|${Boolean(shiftKey)}`);
  return midi === undefined ? null : midi;
}

export function labelsFor(layout) {
  const labels = new Map();
  for (const midi of currentMap.keys()) labels.set(midi, keyLabel(midi, layout));
  return labels;
}

export function reverseLabels(layout) {
  const reverse = new Map();
  for (const [midi, label] of labelsFor(layout)) reverse.set(label, midi);
  return reverse;
}
