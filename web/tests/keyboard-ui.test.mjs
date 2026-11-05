import test from "node:test";
import assert from "node:assert/strict";
import { spaceBelongsToControl, computeKeyLayout } from "../js/keyboard-ui.js";

const whites = (layout) => layout.keys.filter((key) => !key.black);
const blacks = (layout) => layout.keys.filter((key) => key.black);
const byMidi = (layout, midi) => layout.keys.find((key) => key.midi === midi);

test("layout: 61 keys, 36 white and 25 black", () => {
  const layout = computeKeyLayout(1380);
  assert.equal(layout.keys.length, 61);
  assert.equal(whites(layout).length, 36);
  assert.equal(blacks(layout).length, 25);
});

test("layout: white keys fill the container exactly, no gaps, widths differ by at most 1 px", () => {
  for (const available of [1000, 1033, 1380, 1757, 1800]) {
    const layout = computeKeyLayout(available, 24);
    const row = whites(layout);
    assert.equal(layout.width, available);
    assert.equal(row.reduce((sum, key) => sum + key.width, 0), available);
    assert.equal(row[0].left, 0);
    for (let i = 1; i < row.length; i++) assert.equal(row[i].left, row[i - 1].left + row[i - 1].width);
    const widths = row.map((key) => key.width);
    assert.ok(Math.max(...widths) - Math.min(...widths) <= 1, `uneven widths at ${available}`);
    assert.ok(layout.keys.every((key) => Number.isInteger(key.left) && Number.isInteger(key.width)));
  }
});

test("layout: black keys sit off-centre inside their groups (hand-computed at 1008 px)", () => {
  const layout = computeKeyLayout(1008); // every white key is 28 px, black keys 17 px wide
  assert.equal(whites(layout)[0].width, 28);
  assert.deepEqual([37, 39, 42, 46].map((midi) => byMidi(layout, midi).left), [17, 50, 101, 162]);
  assert.ok(blacks(layout).every((key) => key.width === 17));
  // C#2 is left of the D/E edge-centre, D#2 right of it: the gap pattern of a real keyboard.
  const centre = (midi) => byMidi(layout, midi).left + 8.5;
  assert.ok(centre(37) < 28 && centre(39) > 56);
  assert.ok(Math.abs(centre(44) - 140) <= 1); // G# stays centred on the G/A edge
});

test("layout: narrow containers keep white keys at least 28 px wide and scroll", () => {
  const layout = computeKeyLayout(330);
  assert.equal(layout.width, 36 * 28);
  assert.ok(whites(layout).every((key) => key.width === 28));
  assert.equal(layout.height, 154);
});

test("layout: white key height is about 5.5 widths, clamped to 120..220 px", () => {
  assert.equal(computeKeyLayout(1008).height, 154);
  assert.equal(computeKeyLayout(1368).height, 209);
  assert.equal(computeKeyLayout(1800).height, 220);
  assert.equal(computeKeyLayout(900, 20).height, 138);
  assert.equal(computeKeyLayout(36 * 10, 10).height, 120);
});

// Minimal stand-in for a DOM element: closest(selector) matches by class/tag names listed in the selector.
const element = (...names) => ({
  closest: (selector) => (names.some((name) => selector.split(",").some((part) => part.trim() === name)) ? {} : null)
});

test("Space on a piano key (a button) is the pedal, not a button press", () => {
  assert.equal(spaceBelongsToControl(element("button", ".piano-key")), false);
});

test("Space on an ordinary button, checkbox or link stays with the control", () => {
  assert.equal(spaceBelongsToControl(element("button")), true);
  assert.equal(spaceBelongsToControl(element("input[type='checkbox']")), true);
  assert.equal(spaceBelongsToControl(element("a")), true);
});

test("Space on the page body is the pedal", () => {
  assert.equal(spaceBelongsToControl(element()), false);
  assert.equal(spaceBelongsToControl(null), false);
});
