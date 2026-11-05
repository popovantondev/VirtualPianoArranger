// Letter notation: reading text, writing tokens. Pure module (no DOM), tested with node.
// Port of letter_practice.py (parse_letters), text_import.py (read_notation) and render_events in main.py.

import { LOW, HIGH, reverseLabels, keyLabel } from "./keymap.js";
import { simplifyNotes } from "./arrange.js";

export const MAX_BYTES = 2_000_000;
export const MAX_TOKEN_CHARS = 128;
export const MAX_ATTACKS = 100_000;

// Same pattern as PATTERN in letter_practice.py: [chord], (chord) of 2+ symbols, or one symbol.
export const TOKEN_PATTERN = /\[[^\]\r\n]*\]|\([^()\s]{2,}\)|[^\s]/gu;

// code: "unknown" | "too_long" | "too_many" | "too_large" | "encoding" | "binary"
export class NotationError extends Error {
  constructor(code, details = {}) {
    super(details.message || code);
    this.name = "NotationError";
    this.code = code;
    this.line = details.line ?? null;
    this.char = details.char ?? null;
    this.from = details.from ?? null;
    this.to = details.to ?? null;
  }
}

// ---------- Reading a file ----------
function decodeUtf16(bytes, littleEndian) {
  const body = bytes.subarray(2);
  if (body.length % 2) throw new NotationError("encoding");
  const units = new Array(body.length / 2);
  for (let i = 0; i < units.length; i++) {
    units[i] = littleEndian ? body[2 * i] | (body[2 * i + 1] << 8) : (body[2 * i] << 8) | body[2 * i + 1];
  }
  for (let i = 0; i < units.length; i++) {
    const unit = units[i];
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = units[i + 1];
      if (next === undefined || next < 0xdc00 || next > 0xdfff) throw new NotationError("encoding");
      i++;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      throw new NotationError("encoding");
    }
  }
  let text = "";
  for (let i = 0; i < units.length; i += 8192) text += String.fromCharCode(...units.slice(i, i + 8192));
  return text;
}

// Port of read_notation: UTF-8 (with or without BOM) or UTF-16 with BOM; other encodings are refused.
export function decodeNotation(input) {
  const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
  if (bytes.length > MAX_BYTES) throw new NotationError("too_large");
  const bom16 = bytes.length >= 2 && ((bytes[0] === 0xff && bytes[1] === 0xfe) || (bytes[0] === 0xfe && bytes[1] === 0xff));
  let text;
  if (bom16) {
    text = decodeUtf16(bytes, bytes[0] === 0xff);
  } else {
    try {
      text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    } catch (error) {
      throw new NotationError("encoding");
    }
  }
  if (text.includes("\u0000")) throw new NotationError(bom16 ? "binary" : "encoding");
  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i);
    if (code < 32 && code !== 10 && code !== 13 && code !== 9) throw new NotationError("binary");
  }
  return text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

// Cyrillic letters in the text mean the Russian layout.
export function detectLayout(text, fallback) {
  return /[Ѐ-ӿ]/.test(text) ? "ru" : fallback;
}

// ---------- Reading letters ----------
// layout: "en" | "ru" | "de", or a Map midi -> printed symbol (custom labels).
function reverseMap(layout) {
  if (typeof layout === "string") return reverseLabels(layout);
  const reverse = new Map();
  for (const [midi, label] of layout) reverse.set(label, midi);
  return reverse;
}

export function parseLetters(text, layout) {
  const reverse = reverseMap(layout);
  const tokens = [];
  let line = 1;
  let previous = 0;
  for (const match of text.matchAll(TOKEN_PATTERN)) {
    const raw = match[0];
    const from = match.index;
    const to = from + raw.length;
    const grouped = raw.startsWith("[") || (raw.startsWith("(") && raw.endsWith(")") && raw.length > 3);
    const chars = [...(grouped ? raw.slice(1, -1) : raw)];
    line += countNewlines(text, previous, from);
    previous = to;
    const location = { line, from, to };
    if (chars.length > MAX_TOKEN_CHARS) throw new NotationError("too_long", { ...location, char: raw.slice(0, 12) });
    const notes = [];
    for (const char of chars) {
      if (!reverse.has(char)) throw new NotationError("unknown", { ...location, char });
      notes.push(reverse.get(char));
    }
    if (!notes.length) throw new NotationError("unknown", { ...location, char: raw });
    tokens.push({ notes, line, index: tokens.length, from, to });
    if (tokens.length > MAX_ATTACKS) throw new NotationError("too_many", location);
  }
  return tokens;
}

function countNewlines(text, start, end) {
  let count = 0;
  for (let i = text.indexOf("\n", start); i !== -1 && i < end; i = text.indexOf("\n", i + 1)) count++;
  return count;
}

// ---------- Writing letters ----------
// Port of render_events (range_labels = false).
// events: [{measure, notes: number[]}] in time order. Returns the text, one token per event
// ({notes, line, index, from, to, event}) and the notes that did not fit the keyboard ({measure, midi}).
export function renderTokens(events, layout, { semitones = 0, chordValue = 40, spacing = false } = {}) {
  const outside = [];
  const byMeasure = new Map();
  events.forEach((event, eventIndex) => {
    const shifted = simplifyNotes(event.notes.map((midi) => midi + semitones), chordValue);
    const notes = [];
    for (const midi of shifted) {
      if (midi < LOW || midi > HIGH) outside.push({ measure: event.measure, midi });
      else notes.push(midi);
    }
    const chars = notes.map((midi) => keyLabel(midi, layout));
    const symbol = !chars.length ? "?" : chars.length === 1 ? chars[0] : `[${chars.join("")}]`;
    if (!byMeasure.has(event.measure)) byMeasure.set(event.measure, []);
    byMeasure.get(event.measure).push({ symbol, notes, event: eventIndex });
  });
  const separator = spacing ? " " : "";
  const tokens = [];
  const lines = [];
  let offset = 0;
  [...byMeasure.keys()].sort((a, b) => a - b).forEach((measure, lineIndex) => {
    let text = "";
    byMeasure.get(measure).forEach((item, position) => {
      if (position) text += separator;
      const from = offset + text.length;
      text += item.symbol;
      tokens.push({ notes: item.notes, line: lineIndex + 1, index: tokens.length, from, to: from + item.symbol.length, event: item.event });
    });
    lines.push(text);
    offset += text.length + 1;
  });
  return { text: lines.join("\n"), tokens, outside };
}
