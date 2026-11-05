import test from "node:test";
import assert from "node:assert/strict";
import {
  TOKEN_PATTERN, NotationError, decodeNotation, detectLayout, parseLetters, renderTokens
} from "../js/letters.js";

// Labels from test_letter_practice.py (custom map: midi -> printed letter).
const LABELS = new Map([[36, "1"], [48, "2"], [60, "a"], [61, "A"], [64, "d"], [67, "g"], [72, "h"], [70, "("]]);

const buffer = (bytes) => Uint8Array.from(bytes).buffer;
const utf8 = (text) => Buffer.from(text, "utf8");
const utf16le = (text) => Buffer.from("﻿" + text, "utf16le");
const utf16be = (text) => {
  const le = Buffer.from("﻿" + text, "utf16le");
  for (let i = 0; i + 1 < le.length; i += 2) [le[i], le[i + 1]] = [le[i + 1], le[i]];
  return le;
};
const toBuffer = (bytes) => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);

function failure(action) {
  try { action(); } catch (error) { return error; }
  return null;
}

test("TOKEN_PATTERN splits brackets, parenthesised chords and single characters", () => {
  const found = [..."[aAdg]  (adg)\n(".matchAll(TOKEN_PATTERN)].map((match) => match[0]);
  assert.deepEqual(found, ["[aAdg]", "(adg)", "("]);
});

test("parseLetters reads both chord syntaxes and a literal parenthesis", () => {
  const tokens = parseLetters("[aAdg]  (adg)\n(", LABELS);
  assert.deepEqual(tokens.map((token) => token.notes), [[60, 61, 64, 67], [60, 64, 67], [70]]);
  assert.deepEqual(tokens.map((token) => token.line), [1, 1, 2]);
  assert.deepEqual(tokens.map((token) => token.index), [0, 1, 2]);
  assert.deepEqual(tokens.map((token) => [token.from, token.to]), [[0, 6], [8, 13], [14, 15]]);
});

test("parseLetters uses the real key map for a named layout", () => {
  assert.deepEqual(parseLetters("t T", "en").map((token) => token.notes), [[60], [61]]);
});

test("parseLetters reports the unknown symbol with its line", () => {
  const error = failure(() => parseLetters("a\n[a?]", LABELS));
  assert.ok(error instanceof NotationError);
  assert.equal(error.code, "unknown");
  assert.equal(error.line, 2);
  assert.equal(error.char, "?");
});

test("parseLetters rejects an empty chord", () => {
  assert.equal(failure(() => parseLetters("a []", LABELS)).code, "unknown");
});

test("parseLetters limits a token to 128 characters", () => {
  assert.equal(parseLetters(`[${"a".repeat(128)}]`, LABELS)[0].notes.length, 128);
  const error = failure(() => parseLetters(`[${"a".repeat(129)}]`, LABELS));
  assert.ok(error instanceof NotationError);
  assert.equal(error.code, "too_long");
});

test("parseLetters limits the text to 100000 attacks", () => {
  assert.equal(parseLetters("a ".repeat(100000), LABELS).length, 100000);
  assert.equal(failure(() => parseLetters("a ".repeat(100001), LABELS)).code, "too_many");
});

test("detectLayout picks ru for Cyrillic and keeps the fallback otherwise", () => {
  assert.equal(detectLayout("я (6г)", "en"), "ru");
  assert.equal(detectLayout("[tuo] s", "de"), "de");
  assert.equal(detectLayout("", "en"), "en");
});

test("decodeNotation reads utf-8, utf-8 with BOM and utf-16 and normalises newlines", () => {
  const source = "я (6г)\r\nо\rу";
  const expected = "я (6г)\nо\nу";
  assert.equal(decodeNotation(toBuffer(utf8(source))), expected);
  assert.equal(decodeNotation(toBuffer(Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), utf8(source)]))), expected);
  assert.equal(decodeNotation(toBuffer(utf16le(source))), expected);
  assert.equal(decodeNotation(toBuffer(utf16be(source))), expected);
});

test("decodeNotation refuses big, binary and undecodable files", () => {
  const big = failure(() => decodeNotation(new Uint8Array(2_000_001).fill(120).buffer));
  assert.ok(big instanceof NotationError);
  assert.equal(big.code, "too_large");
  assert.equal(decodeNotation(new Uint8Array(2_000_000).fill(120).buffer).length, 2_000_000);
  assert.equal(failure(() => decodeNotation(buffer([120, 1, 121]))).code, "binary");
  assert.equal(failure(() => decodeNotation(buffer([0xe4, 0x20, 0x7a]))).code, "encoding");
  assert.equal(failure(() => decodeNotation(buffer([0x61, 0x00, 0x62, 0x00]))).code, "encoding");
  assert.equal(failure(() => decodeNotation(buffer([0xff, 0xfe, 0x61, 0x00, 0x00, 0x00]))).code, "binary");
});

test("renderTokens writes one character, a chord in brackets and one measure per line", () => {
  const events = [
    { measure: 1, notes: [60, 64, 67] },
    { measure: 1, notes: [72] },
    { measure: 2, notes: [61] }
  ];
  const result = renderTokens(events, "en", { semitones: 0, chordValue: 40, spacing: false });
  assert.equal(result.text, "[tuo]s\nT");
  assert.deepEqual(result.outside, []);
  assert.deepEqual(result.tokens.map((token) => [token.from, token.to, token.line, token.index]),
    [[0, 5, 1, 0], [5, 6, 1, 1], [7, 8, 2, 2]]);
  assert.equal(renderTokens(events, "en", { spacing: true }).text, "[tuo] s\nT");
});

test("renderTokens output parses back to the same notes", () => {
  const events = [
    { measure: 1, notes: [60, 64, 67] }, { measure: 1, notes: [72] },
    { measure: 2, notes: [61, 66] }, { measure: 3, notes: [36] }, { measure: 3, notes: [96] }
  ];
  for (const layout of ["en", "ru", "de"]) {
    const { text, tokens } = renderTokens(events, layout, { chordValue: 40, spacing: true });
    const parsed = parseLetters(text, layout);
    assert.deepEqual(parsed.map((token) => token.notes), events.map((event) => event.notes), layout);
    assert.deepEqual(parsed.map((token) => [token.from, token.to]), tokens.map((token) => [token.from, token.to]), layout);
    assert.deepEqual(tokens.map((token) => token.notes), events.map((event) => event.notes), layout);
  }
});

test("renderTokens moves notes by semitones and reports notes outside 36-96", () => {
  const result = renderTokens(
    [{ measure: 1, notes: [60, 30] }, { measure: 1, notes: [20] }, { measure: 2, notes: [90, 100] }],
    "en", { semitones: 12 });
  // 60+12 -> 's'; 30+12=42 is inside ('3'-row key), 20+12=32 is outside, 100+12 and 90+12 are outside.
  assert.deepEqual(result.outside, [{ measure: 1, midi: 32 }, { measure: 2, midi: 102 }, { measure: 2, midi: 112 }]);
  assert.equal(result.text.split("\n")[1], "?");
  assert.deepEqual(result.tokens[1].notes, []);
});

test("renderTokens keeps both ends of a chord at full simplification", () => {
  const notes = Array.from({ length: 12 }, (_, i) => 48 + i);
  assert.equal(renderTokens([{ measure: 1, notes }], "en", { chordValue: 100 }).text, "[8r]");
  assert.equal(renderTokens([{ measure: 1, notes }], "en", { chordValue: 10 }).tokens[0].notes.length, 12);
});

test("renderTokens rounds interior chord picks half to even like Python", () => {
  const notes = [60, 61, 62, 63, 64, 65, 66, 67];
  // chord value 40 keeps 5 notes: ends plus interior indexes 0, round(2.5)=2, 5.
  const { tokens } = renderTokens([{ measure: 1, notes }], "en", { chordValue: 40 });
  assert.deepEqual(tokens[0].notes, [60, 61, 63, 66, 67]);
});
