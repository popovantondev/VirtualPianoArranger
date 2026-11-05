import test from "node:test";
import assert from "node:assert/strict";
import { Follow } from "../js/follow.js";

const single = (...pitches) => pitches.map((midi) => ({ notes: [midi] }));
const run = (count, base = 60) => Array.from({ length: count }, (_, i) => ({ notes: [base + i] }));

test("a correct key steps forward and the last one finishes", () => {
  const follow = new Follow(single(60, 62));
  assert.equal(follow.cursor, 0);
  assert.deepEqual(follow.press(60, 0), { action: "step", cursor: 1 });
  assert.equal(follow.done, false);
  assert.deepEqual(follow.press(62, 500), { action: "done", cursor: 2 });
  assert.equal(follow.done, true);
  assert.deepEqual(follow.press(62, 900), { action: "done", cursor: 2 });
});

test("a wrong key leaves the cursor in place", () => {
  const follow = new Follow(single(60, 62, 64));
  assert.deepEqual(follow.press(90, 0), { action: "wait", cursor: 0 });
  assert.deepEqual(follow.press(61, 10), { action: "wait", cursor: 0 });
  assert.equal(follow.cursor, 0);
});

test("a chord counts when all its notes are pressed within 300 ms", () => {
  const follow = new Follow([{ notes: [60, 64, 67] }, { notes: [62] }]);
  assert.deepEqual(follow.press(60, 0), { action: "partial", cursor: 0 });
  assert.deepEqual(follow.press(64, 100), { action: "partial", cursor: 0 });
  assert.deepEqual(follow.press(67, 300), { action: "step", cursor: 1 });
});

test("a chord note older than 300 ms no longer counts", () => {
  const follow = new Follow([{ notes: [60, 64, 67] }, { notes: [62] }]);
  follow.press(60, 0);
  follow.press(64, 100);
  assert.deepEqual(follow.press(67, 301), { action: "partial", cursor: 0 });
  // 64 (100) and 67 (301) are fresh, 60 must be pressed again.
  assert.deepEqual(follow.press(60, 350), { action: "step", cursor: 1 });
});

test("a chord note alone does not jump to a later single note with the same pitch", () => {
  const follow = new Follow([{ notes: [60, 64] }, { notes: [64] }, { notes: [67] }]);
  assert.deepEqual(follow.press(64, 0), { action: "partial", cursor: 0 });
  assert.deepEqual(follow.press(60, 100), { action: "step", cursor: 1 });
});

test("repeated notes are taken one by one", () => {
  const follow = new Follow(single(60, 60, 62));
  assert.deepEqual(follow.press(60, 0), { action: "step", cursor: 1 });
  assert.deepEqual(follow.press(60, 500), { action: "step", cursor: 2 });
});

test("a note of a later token does not move the cursor", () => {
  const follow = new Follow(run(10));
  assert.deepEqual(follow.press(66, 0), { action: "wait", cursor: 0 });
  assert.deepEqual(follow.press(61, 100), { action: "wait", cursor: 0 });
  assert.deepEqual(follow.press(60, 200), { action: "step", cursor: 1 });
});

test("two attacks of far tokens in a row still do not skip", () => {
  const follow = new Follow(run(12));
  assert.deepEqual(follow.press(67, 0), { action: "wait", cursor: 0 });
  assert.deepEqual(follow.press(68, 100), { action: "wait", cursor: 0 });
  assert.equal(follow.cursor, 0);
});

test("reset to a later token is the only way to move ahead", () => {
  const follow = new Follow(run(10));
  follow.reset(5);
  assert.equal(follow.cursor, 5);
  assert.deepEqual(follow.press(65, 0), { action: "step", cursor: 6 });
});

test("reset moves the cursor and clears the finished state", () => {
  const follow = new Follow(single(60, 62));
  follow.press(60, 0);
  follow.press(62, 400);
  assert.equal(follow.done, true);
  follow.reset();
  assert.equal(follow.cursor, 0);
  assert.equal(follow.done, false);
  follow.reset(1);
  assert.equal(follow.cursor, 1);
  assert.deepEqual(follow.press(62, 5000), { action: "done", cursor: 2 });
});

test("tokens without notes are passed over", () => {
  const follow = new Follow([{ notes: [60] }, { notes: [] }, { notes: [62] }]);
  assert.deepEqual(follow.press(60, 0), { action: "step", cursor: 2 });
  assert.equal(new Follow([{ notes: [] }, { notes: [60] }]).cursor, 1);
  assert.equal(new Follow([]).done, true);
});
