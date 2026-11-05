import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  LOW, HIGH, PHYSICAL_WHITE_KEYS, buildKeyMap, parseKeyMapJson, setKeyMap,
  isBlack, keyLabel, noteName, midiFromKeyEvent, labelsFor, reverseLabels
} from "../js/keymap.js";

const json = JSON.parse(readFileSync(new URL("../../virtual_piano_61_map.json", import.meta.url), "utf8"));

test("range is C2..C7 and white-key row has 36 keys", () => {
  assert.equal(LOW, 36);
  assert.equal(HIGH, 96);
  assert.equal(PHYSICAL_WHITE_KEYS, "1234567890QWERTYUIOPASDFGHJKLZXCVBNM");
});

test("buildKeyMap and the JSON file agree on all 61 entries", () => {
  const built = buildKeyMap();
  const parsed = parseKeyMapJson(json);
  assert.equal(Object.keys(json).length, 61);
  assert.equal(built.size, 61);
  assert.equal(parsed.size, 61);
  for (let midi = 36; midi <= 96; midi++) {
    assert.deepEqual(built.get(midi), parsed.get(midi), `midi ${midi}`);
  }
  // Hand-checked entries from the JSON file.
  assert.deepEqual(parsed.get(36), { key: "1", shift: false });
  assert.deepEqual(parsed.get(37), { key: "1", shift: true });
  assert.deepEqual(parsed.get(96), { key: "M", shift: false });
});

test("parseKeyMapJson rejects incomplete data", () => {
  assert.throws(() => parseKeyMapJson({ C2: { physical_key: "1", shift: false } }));
  assert.throws(() => parseKeyMapJson(null));
});

test("key labels per layout", () => {
  setKeyMap(buildKeyMap());
  assert.equal(keyLabel(60, "en"), "t");
  assert.equal(keyLabel(60, "ru"), "е");
  assert.equal(keyLabel(60, "de"), "t");
  assert.equal(keyLabel(61, "en"), "T");
  assert.equal(keyLabel(61, "ru"), "Е");
  assert.equal(keyLabel(37, "en"), "!");
  assert.equal(keyLabel(37, "ru"), "!");
  assert.equal(keyLabel(39, "ru"), "\"");
  assert.equal(keyLabel(42, "en"), "$");
  assert.equal(keyLabel(96, "en"), "m");
  assert.equal(keyLabel(96, "ru"), "ь");
  assert.equal(keyLabel(96, "de"), "m");
  // German swaps Y and Z. Physical Y is white key 15 (D4 = 62), Z is white key 29 (D6 = 86).
  assert.equal(keyLabel(62, "de"), "z");
  assert.equal(keyLabel(86, "de"), "y");
  assert.equal(keyLabel(62, "en"), "y");
  assert.equal(keyLabel(62, "ru"), "н");
  assert.equal(keyLabel(3, "en"), "?");
});

test("german shift digits", () => {
  setKeyMap(buildKeyMap());
  assert.equal(keyLabel(39, "de"), "\"");
  assert.equal(keyLabel(46, "de"), "&");
  assert.equal(keyLabel(46, "en"), "^");
  assert.equal(keyLabel(46, "ru"), ":");
});

test("note names in three languages", () => {
  assert.equal(noteName(60, "ru"), "до4");
  assert.equal(noteName(61, "ru"), "до♯4");
  assert.equal(noteName(67, "ru"), "соль4");
  assert.equal(noteName(60, "de"), "C4");
  assert.equal(noteName(61, "de"), "Cis4");
  assert.equal(noteName(71, "de"), "H4");
  assert.equal(noteName(60, "en"), "C4");
  assert.equal(noteName(61, "en"), "C♯4");
  assert.equal(noteName(71, "en"), "B4");
  assert.equal(noteName(36, "en"), "C2");
  assert.equal(noteName(96, "ru"), "до7");
});

test("isBlack follows the piano pattern", () => {
  const blacks = [];
  for (let m = 36; m <= 47; m++) if (isBlack(m)) blacks.push(m);
  assert.deepEqual(blacks, [37, 39, 42, 44, 46]);
});

test("midiFromKeyEvent uses physical codes and shift", () => {
  setKeyMap(buildKeyMap());
  assert.equal(midiFromKeyEvent({ code: "Digit1", shiftKey: false }), 36);
  assert.equal(midiFromKeyEvent({ code: "Digit1", shiftKey: true }), 37);
  assert.equal(midiFromKeyEvent({ code: "KeyT", shiftKey: false }), 60);
  assert.equal(midiFromKeyEvent({ code: "KeyT", shiftKey: true }), 61);
  assert.equal(midiFromKeyEvent({ code: "Numpad1", shiftKey: false }), 36);
  assert.equal(midiFromKeyEvent({ code: "KeyM", shiftKey: false }), 96);
  assert.equal(midiFromKeyEvent({ code: "Space", shiftKey: false }), null);
  assert.equal(midiFromKeyEvent({ code: "KeyM", shiftKey: true }), null);
});

test("labelsFor and reverseLabels are inverse", () => {
  setKeyMap(buildKeyMap());
  for (const layout of ["en", "ru", "de"]) {
    const forward = labelsFor(layout);
    const backward = reverseLabels(layout);
    assert.equal(forward.size, 61);
    assert.equal(backward.size, 61, layout);
    for (const [midi, label] of forward) assert.equal(backward.get(label), midi);
  }
});

test("setKeyMap switches the map used by every function", () => {
  const custom = new Map(buildKeyMap());
  custom.set(60, { key: "Q", shift: false });
  setKeyMap(custom);
  assert.equal(keyLabel(60, "en"), "q");
  assert.equal(midiFromKeyEvent({ code: "KeyQ", shiftKey: false }), 60);
  setKeyMap(buildKeyMap());
  assert.equal(keyLabel(60, "en"), "t");
});
