import test from "node:test";
import assert from "node:assert/strict";
import { t, STRINGS } from "../js/i18n.js";

test("tonality label counts semitones with the right word form", () => {
  assert.equal(t("ru", "tuneValue", { value: "+1" }), "Тональность +1 полутон");
  assert.equal(t("ru", "tuneValue", { value: "+3" }), "Тональность +3 полутона");
  assert.equal(t("ru", "tuneValue", { value: "-5" }), "Тональность -5 полутонов");
  assert.equal(t("ru", "tuneValue", { value: "0" }), "Тональность 0 полутонов");
  assert.equal(t("en", "tuneValue", { value: "+1" }), "Tonality +1 semitone");
  assert.equal(t("en", "tuneValue", { value: "-12" }), "Tonality -12 semitones");
  assert.equal(t("de", "tuneValue", { value: "+1" }), "Tonart +1 Halbton");
  assert.equal(t("de", "tuneValue", { value: "+7" }), "Tonart +7 Halbtöne");
});

test("the octave strings are gone: tonality replaced the octave shift", () => {
  for (const lang of ["ru", "de", "en"]) {
    assert.equal(STRINGS[lang].octaveValue, undefined);
    assert.doesNotMatch(STRINGS[lang].soundExtra, /октав|oktav|octave/i);
    assert.doesNotMatch(STRINGS[lang].soundMissing, /октав|oktav|octave/i);
  }
});

test("every language has the same set of dynamic messages", () => {
  const keys = (lang) => Object.keys(STRINGS[lang]).sort();
  assert.deepEqual(keys("de"), keys("ru"));
  assert.deepEqual(keys("en"), keys("ru"));
});

test("Russian count forms", () => {
  const f = (count) => t("ru", "demos.notes", { count, bpm: 90 });
  assert.match(f(1), /^1 нота ·/);
  assert.match(f(2), /^2 ноты ·/);
  assert.match(f(5), /^5 нот ·/);
  assert.match(f(11), /^11 нот ·/);
  assert.match(f(21), /^21 нота ·/);
  assert.match(f(62), /^62 ноты ·/);
  assert.match(f(112), /^112 нот ·/);
});

test("Russian semitone forms keep the sign", () => {
  assert.match(t("ru", "midi.autoDone", { value: "+2" }), /\+2 полутона\./);
  assert.match(t("ru", "midi.autoDone", { value: "-5" }), /-5 полутонов\./);
  assert.match(t("ru", "midi.autoDone", { value: "+1" }), /\+1 полутон\./);
  assert.match(t("ru", "midi.autoDone", { value: "0" }), /0 полутонов\./);
});

test("English and German count forms", () => {
  assert.match(t("en", "midi.partStats", { count: 1, low: "a", high: "b" }), /^1 note ·/);
  assert.match(t("en", "midi.partStats", { count: 2, low: "a", high: "b" }), /^2 notes ·/);
  assert.match(t("de", "midi.partStats", { count: 1, low: "a", high: "b" }), /^1 Note ·/);
  assert.match(t("de", "midi.partStats", { count: 62, low: "a", high: "b" }), /^62 Noten ·/);
  assert.match(t("en", "midi.autoDone", { value: "+1" }), /\+1 semitone\./);
  assert.match(t("de", "midi.autoDone", { value: "+1" }), /\+1 Halbton\./);
  assert.match(t("de", "midi.autoDone", { value: "-3" }), /-3 Halbtöne\./);
});

test("unknown placeholders stay untouched", () => {
  assert.equal(t("en", "no.such.key {x}", {}), "no.such.key {x}");
});
