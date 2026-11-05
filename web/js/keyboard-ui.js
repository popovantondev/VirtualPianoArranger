// On-screen 61-key piano: pointer/touch input, computer keyboard input, highlights.

import { LOW, HIGH, isBlack, midiFromKeyEvent } from "./keymap.js";

const WHITE_COUNT = 36;
const BLACK_WIDTH = 0.62; // black key width, in white keys
const BLACK_OFFSET = { 1: -0.08, 3: 0.08, 6: -0.1, 8: 0, 10: 0.1 }; // off-centre shift inside the C#/D# and F#/G#/A# groups
const HEIGHT_RATIO = 5.5;
const HEIGHT_MIN = 120;
const HEIGHT_MAX = 220;
const TEXT_INPUT_TYPES = new Set(["text", "search", "email", "url", "tel", "password", "number"]);
const HIGHLIGHT_CLASS = { active: "is-active", next: "is-next", play: "is-play" };

function reducedMotion() {
  return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Keys must not play while the user types into a field.
function isTextTarget(target) {
  if (!target || !target.closest) return false;
  if (target.closest("textarea, select, [contenteditable='true'], [contenteditable='']")) return true;
  const input = target.closest("input");
  return Boolean(input && TEXT_INPUT_TYPES.has((input.getAttribute("type") || "text").toLowerCase()));
}

// Space would activate a focused button or checkbox; leave it alone there.
// Piano keys are buttons too, but Space there always means the pedal.
export function spaceBelongsToControl(target) {
  if (target && target.closest && target.closest(".piano-key")) return false;
  return Boolean(target && target.closest && target.closest("button, a, summary, input[type='checkbox'], input[type='radio'], input[type='file']"));
}

// Pure key geometry in whole pixels. Fills `available` px when the white keys stay at least
// `minWhite` wide, otherwise the board is 36 * minWhite wide and the container scrolls.
// Returns {width, height, whiteWidth, keys: [{midi, black, left, width}]}.
export function computeKeyLayout(available, minWhite = 28) {
  const width = Math.max(Math.floor(available) || 0, Math.ceil(minWhite) * WHITE_COUNT);
  const whiteWidth = width / WHITE_COUNT;
  const edge = (index) => Math.round(index * width / WHITE_COUNT);
  const blackWidth = Math.max(2, Math.round(BLACK_WIDTH * whiteWidth));
  const keys = [];
  let whiteIndex = 0;
  for (let midi = LOW; midi <= HIGH; midi++) {
    if (isBlack(midi)) {
      // The black key straddles the edge before the next white key, then moves by its group offset.
      const centre = edge(whiteIndex) + BLACK_OFFSET[midi % 12] * whiteWidth;
      keys.push({ midi, black: true, left: Math.round(centre - blackWidth / 2), width: blackWidth });
    } else {
      keys.push({ midi, black: false, left: edge(whiteIndex), width: edge(whiteIndex + 1) - edge(whiteIndex) });
      whiteIndex++;
    }
  }
  const height = Math.round(Math.max(HEIGHT_MIN, Math.min(HEIGHT_MAX, whiteWidth * HEIGHT_RATIO)));
  return { width, height, whiteWidth, keys };
}

export function mountKeyboard(container, { onPress = () => {}, onRelease = () => {}, onPedal = () => {} } = {}) {
  const board = document.createElement("div");
  board.className = "piano-board";
  board.setAttribute("role", "group");
  const keys = new Map();
  for (let midi = LOW; midi <= HIGH; midi++) {
    const key = document.createElement("button");
    key.type = "button";
    key.tabIndex = -1;
    key.className = `piano-key ${isBlack(midi) ? "black" : "white"}`;
    key.dataset.midi = String(midi);
    const label = document.createElement("span");
    label.className = "piano-label";
    key.append(label);
    board.append(key);
    keys.set(midi, { element: key, label });
  }
  container.replaceChildren(board);

  // Sizes are recomputed in whole pixels whenever the container changes size.
  function layout() {
    const style = window.getComputedStyle(container);
    const minWhite = parseFloat(style.getPropertyValue("--white-key-min")) || 28;
    const available = container.clientWidth;
    if (!available) return;
    const result = computeKeyLayout(available, minWhite);
    board.style.width = `${result.width}px`;
    board.style.height = `${result.height}px`;
    for (const key of result.keys) {
      const element = keys.get(key.midi).element;
      element.style.left = `${key.left}px`;
      element.style.width = `${key.width}px`;
    }
  }
  layout();
  const resizeObserver = typeof ResizeObserver === "function" ? new ResizeObserver(layout) : null;
  if (resizeObserver) resizeObserver.observe(container);
  else window.addEventListener("resize", layout);

  // Pointer input: one pointerId per finger, so chords and multi-touch work.
  const pointers = new Map();
  const typed = new Map();

  function press(midi) {
    const entry = keys.get(midi);
    if (entry) entry.element.classList.add("is-active");
    onPress(midi);
  }

  function release(midi) {
    const entry = keys.get(midi);
    if (entry) entry.element.classList.remove("is-active");
    onRelease(midi);
  }

  board.addEventListener("pointerdown", (event) => {
    const element = event.target.closest(".piano-key");
    if (!element || (event.pointerType === "mouse" && event.button !== 0)) return;
    event.preventDefault();
    const midi = Number(element.dataset.midi);
    try { element.setPointerCapture(event.pointerId); } catch (error) { /* synthetic events */ }
    pointers.set(event.pointerId, midi);
    press(midi);
  });
  const pointerEnd = (event) => {
    if (!pointers.has(event.pointerId)) return;
    const midi = pointers.get(event.pointerId);
    pointers.delete(event.pointerId);
    release(midi);
  };
  // Mouse clicks must not move focus to the key (keys are tabindex -1 buttons).
  board.addEventListener("mousedown", (event) => { if (event.target.closest(".piano-key")) event.preventDefault(); });
  board.addEventListener("pointerup", pointerEnd);
  board.addEventListener("pointercancel", pointerEnd);
  board.addEventListener("lostpointercapture", pointerEnd);
  board.addEventListener("contextmenu", (event) => event.preventDefault());

  // Computer keyboard: physical key (event.code), Shift gives black keys.
  function onKeyDown(event) {
    if (event.ctrlKey || event.altKey || event.metaKey || isTextTarget(event.target)) return;
    if (event.code === "Space") {
      if (spaceBelongsToControl(event.target)) return;
      event.preventDefault();
      if (!event.repeat) onPedal();
      return;
    }
    const midi = midiFromKeyEvent(event);
    if (midi === null) return;
    event.preventDefault();
    if (event.repeat || typed.has(event.code)) return;
    typed.set(event.code, midi);
    press(midi);
  }

  function onKeyUp(event) {
    // Some browsers fire a click on a focused button at Space keyup even if keydown was cancelled.
    if (event.code === "Space" && !isTextTarget(event.target) && !spaceBelongsToControl(event.target)) event.preventDefault();
    if (!typed.has(event.code)) return;
    const midi = typed.get(event.code);
    typed.delete(event.code);
    release(midi);
  }

  function releaseAll() {
    for (const midi of pointers.values()) release(midi);
    for (const midi of typed.values()) release(midi);
    pointers.clear();
    typed.clear();
  }

  function onVisibility() {
    if (document.hidden) releaseAll();
  }

  document.addEventListener("keydown", onKeyDown);
  document.addEventListener("keyup", onKeyUp);
  window.addEventListener("blur", releaseAll);
  document.addEventListener("visibilitychange", onVisibility);

  function scrollTo(left, smooth) {
    const max = container.scrollWidth - container.clientWidth;
    container.scrollTo({ left: Math.max(0, Math.min(max, left)), behavior: smooth && !reducedMotion() ? "smooth" : "auto" });
  }

  return {
    board,
    setLabels(labelFor) {
      for (const [midi, entry] of keys) entry.label.textContent = labelFor(midi);
    },
    setLabelMode(mode) {
      board.dataset.labels = mode;
    },
    highlight(midi, kind, on) {
      const entry = keys.get(midi);
      const name = HIGHLIGHT_CLASS[kind];
      if (entry && name) entry.element.classList.toggle(name, Boolean(on));
    },
    clearHighlights(kind) {
      const name = HIGHLIGHT_CLASS[kind];
      if (!name) return;
      for (const entry of keys.values()) entry.element.classList.remove(name);
    },
    // Brings a key into view when it is outside (or close to the edge of) the visible part.
    scrollToMidi(midi, { smooth = true, center = false } = {}) {
      const entry = keys.get(midi);
      if (!entry) return;
      const element = entry.element;
      const start = element.offsetLeft;
      const end = start + element.offsetWidth;
      const margin = element.offsetWidth * 2;
      const visibleStart = container.scrollLeft;
      const visibleEnd = visibleStart + container.clientWidth;
      if (center) scrollTo(start - (container.clientWidth - element.offsetWidth) / 2, smooth);
      else if (start < visibleStart + margin) scrollTo(start - margin, smooth);
      else if (end > visibleEnd - margin) scrollTo(end + margin - container.clientWidth, smooth);
    },
    // Scrolls by whole octaves (7 white keys): direction -1 or +1.
    scrollOctave(direction) {
      scrollTo(container.scrollLeft + direction * 7 * board.offsetWidth / WHITE_COUNT, true);
    },
    releaseAll,
    destroy() {
      if (resizeObserver) resizeObserver.disconnect();
      else window.removeEventListener("resize", layout);
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", releaseAll);
      document.removeEventListener("visibilitychange", onVisibility);
    }
  };
}
