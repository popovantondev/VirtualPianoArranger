// Page controller: wires the piano, sound and controls, and offers a mount point
// to the lower panels (sheet, midi, demos).

import * as keymap from "./keymap.js";
import { PianoAudio, Player, LAYERS } from "./audio.js";
import { mountKeyboard } from "./keyboard-ui.js";
import { t as translate } from "./i18n.js";

const LANGS = ["ru", "de", "en"];
const LAYOUTS = ["en", "ru", "de"];
const STORAGE_KEY = "vpa-web-settings";
const PANEL_MODULES = { sheet: "./panels/sheet.js", midi: "./panels/midi.js", demos: "./panels/demos.js" };
const VELOCITY = 108;

const pageLang = (document.documentElement.lang || "en").slice(0, 2).toLowerCase();
const lang = LANGS.includes(pageLang) ? pageLang : "en";
const byId = (id) => document.getElementById(id);
const text = (key, params) => translate(lang, key, params);

// ---------- Saved settings (localStorage may be unavailable) ----------
function loadSettings() {
  const defaults = { layout: "en", labels: "letters", volume: 65, hit: "normal", reverb: "room", reverbAmount: 20 };
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    if (LAYOUTS.includes(saved.layout)) defaults.layout = saved.layout;
    if (["letters", "notes", "none"].includes(saved.labels)) defaults.labels = saved.labels;
    if (Object.hasOwn(LAYERS, saved.hit)) defaults.hit = saved.hit;
    if (["off", "room", "hall"].includes(saved.reverb)) defaults.reverb = saved.reverb;
    if (Number.isFinite(saved.reverbAmount) && saved.reverbAmount >= 0 && saved.reverbAmount <= 100) defaults.reverbAmount = Math.round(saved.reverbAmount);
    if (Number.isFinite(saved.volume) && saved.volume >= 0 && saved.volume <= 100) defaults.volume = Math.round(saved.volume);
  } catch (error) { /* no storage: work without memory */ }
  return defaults;
}

const settings = loadSettings();

function saveSettings() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(settings)); } catch (error) { /* ignore */ }
}

// ---------- Tiny event bus for panels ----------
const listeners = new Map();

function on(name, handler) {
  if (!listeners.has(name)) listeners.set(name, new Set());
  listeners.get(name).add(handler);
  return () => listeners.get(name).delete(handler);
}

function emit(name, ...args) {
  for (const handler of [...(listeners.get(name) || [])]) {
    try { handler(...args); } catch (error) { console.error(error); }
  }
}

// ---------- Panels ----------
const panelMounts = new Map();
const mountedPanels = new Set();
let pageReady = false;
let context = null;

export function registerPanel(id, mountFn) {
  panelMounts.set(id, mountFn);
  if (pageReady) mountPanel(id);
}

function mountPanel(id) {
  if (mountedPanels.has(id) || !panelMounts.has(id)) return;
  const section = byId(id);
  const body = section && section.querySelector("[data-panel-body]");
  if (!body) return;
  mountedPanels.add(id);
  Promise.resolve()
    .then(() => panelMounts.get(id)(body, context))
    .catch((error) => { console.error(`Panel "${id}" failed`, error); });
}

function loadPanelModules() {
  const loads = Object.entries(PANEL_MODULES).map(([id, path]) => import(path).then((module) => {
    if (typeof module.mount === "function") registerPanel(id, module.mount);
  }).catch((error) => {
    const missing = error instanceof TypeError && /dynamically imported|Failed to fetch|Importing a module/i.test(String(error.message));
    if (!missing) console.error(`Panel module "${id}" failed`, error);
  }));
  return Promise.all(loads);
}

// Direct links like play-ru.html#midi: the browser scrolls before panels grow, so scroll again once mounted.
function scrollToHash() {
  const id = decodeURIComponent(location.hash.slice(1));
  const target = id && document.getElementById(id);
  if (target) target.scrollIntoView({ block: "start", behavior: "auto" });
}

// ---------- Key map ----------
async function loadKeyMap() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch("virtual_piano_61_map.json", { signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    keymap.setKeyMap(keymap.parseKeyMapJson(await response.json()));
    return true;
  } catch (error) {
    keymap.setKeyMap(keymap.buildKeyMap());
    return false;
  } finally {
    clearTimeout(timer);
  }
}

// ---------- Sound status ----------
const statusEl = byId("sound-status");
const retryButton = byId("sound-retry");
const progressEl = byId("sound-progress");
const progressBar = byId("sound-progress-bar");

function setStatus(message, state) {
  statusEl.textContent = message;
  statusEl.dataset.state = state;
}

function showReadyStatus() {
  setStatus(audio.unlocked ? text("soundReady") : text("soundNeedsTap"), "ready");
}

function setProgress(done, total) {
  progressEl.hidden = false;
  progressBar.style.setProperty("--p", String(total ? done / total : 0));
  setStatus(text("soundLoading", { done, total }), "loading");
}

// ---------- Sound ----------
const audio = new PianoAudio({ baseUrl: "assets/offline_piano/samples/", layer: LAYERS[settings.hit] });
audio.setReverb(settings.reverb, settings.reverbAmount);
const player = new Player(audio);
let tune = 0; // sound shift in semitones, -12..12 (keys and letters stay put)
let pedal = false;
let keyboard = null;

function errorMessage(error) {
  return location.protocol === "file:" ? text("soundErrorFile") : text("soundError");
}

async function startLoading() {
  retryButton.hidden = true;
  setProgress(0, 21);
  try {
    await audio.load(setProgress);
    progressEl.hidden = true;
    showReadyStatus();
    if (LAYERS[settings.hit] !== audio.layer) await applyHit(settings.hit);
    if (tune !== 0) await applyTune();
  } catch (error) {
    console.warn(error);
    progressEl.hidden = true;
    setStatus(errorMessage(error), "error");
    retryButton.hidden = false;
  }
}

function signed(value) {
  return value > 0 ? `+${value}` : value < 0 ? `−${-value}` : "0";
}

async function applyTune() {
  tune = Math.max(-12, Math.min(12, tune));
  const output = byId("tune-value");
  output.textContent = signed(tune);
  output.setAttribute("aria-label", text("tuneValue", { value: tune > 0 ? `+${tune}` : String(tune) }));
  byId("tune-down").disabled = tune <= -12;
  byId("tune-up").disabled = tune >= 12;
  releaseEverything();
  if (audio.state !== "ready") {
    audio.shift = tune;
    return;
  }
  const pending = audio.setShift(tune);
  setStatus(text("soundExtra"), "loading");
  try {
    await pending;
    showReadyStatus();
  } catch (error) {
    console.warn(error);
    setStatus(errorMessage(error), "error");
    retryButton.hidden = false;
  }
}

// "Hit": the chosen layer loads on demand with progress; the previous one sounds until it is ready.
let hitRequest = 0;
async function applyHit(name) {
  const request = ++hitRequest;
  const layer = LAYERS[name];
  if (audio.state !== "ready") return; // startLoading applies the saved choice once the first set is in
  if (layer === audio.layer) {
    progressEl.hidden = true;
    return;
  }
  try {
    await audio.setLayer(layer, setProgress);
    if (request !== hitRequest) return;
    progressEl.hidden = true;
    showReadyStatus();
  } catch (error) {
    if (request !== hitRequest) return;
    console.warn(error);
    progressEl.hidden = true;
    setStatus(errorMessage(error), "error");
    retryButton.hidden = false;
  }
}

function unlockAudio() {
  if (audio.unlocked) return;
  audio.unlock().then(() => {
    if (audio.unlocked) {
      removeUnlockListeners();
      if (audio.state === "ready" && retryButton.hidden && progressEl.hidden) showReadyStatus();
    }
  });
}

const UNLOCK_EVENTS = ["pointerdown", "pointerup", "touchend", "click", "keydown"];

function removeUnlockListeners() {
  for (const name of UNLOCK_EVENTS) document.removeEventListener(name, unlockAudio, true);
}

function setPedal(on) {
  pedal = Boolean(on);
  audio.setSustain(pedal);
  const button = byId("pedal");
  button.setAttribute("aria-pressed", String(pedal));
  byId("pedal-state").textContent = pedal ? text("pedalOn") : text("pedalOff");
}

function releaseEverything() {
  audio.panic();
  player.pause();
  setPedal(false);
  if (keyboard) {
    keyboard.releaseAll();
    keyboard.clearHighlights("active");
  }
}

// ---------- Labels ----------
function refreshLabels() {
  if (!keyboard) return;
  if (settings.labels === "notes") keyboard.setLabels((midi) => keymap.noteName(midi, lang));
  else if (settings.labels === "none") keyboard.setLabels(() => "");
  else keyboard.setLabels((midi) => keymap.keyLabel(midi, settings.layout));
  keyboard.setLabelMode(settings.labels);
}

function bindSegment(attribute, current, onChange) {
  const buttons = [...document.querySelectorAll(`button[data-${attribute}]`)];
  const sync = () => {
    for (const button of buttons) button.setAttribute("aria-pressed", String(button.dataset[attribute] === current()));
  };
  for (const button of buttons) {
    button.addEventListener("click", () => {
      onChange(button.dataset[attribute]);
      sync();
    });
  }
  sync();
}

// ---------- Glow behind the piano ----------
function initGlow(canvas) {
  const draw2d = canvas.getContext && canvas.getContext("2d");
  if (!draw2d) return;
  const reducedQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  let width = 0;
  let height = 0;
  let dots = [];
  let frame = 0;
  let last = 0;
  let onScreen = true;

  function resize() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    width = canvas.clientWidth;
    height = canvas.clientHeight;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    draw2d.setTransform(ratio, 0, 0, ratio, 0, 0);
    let seed = 7;
    const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
    const count = Math.max(16, Math.min(56, Math.round(width / 22)));
    dots = Array.from({ length: count }, () => ({
      x: random() * width, y: random() * height, r: 0.6 + random() * 1.3,
      phase: random() * Math.PI * 2, speed: 0.5 + random() * 1.1, drift: 2 + random() * 5
    }));
    render(0);
  }

  function render(seconds) {
    draw2d.clearRect(0, 0, width, height);
    const still = reducedQuery.matches;
    for (const dot of dots) {
      const twinkle = still ? 0.5 : 0.5 + 0.5 * Math.sin(seconds * dot.speed + dot.phase);
      draw2d.fillStyle = `rgba(229, 195, 141, ${(0.12 + 0.5 * twinkle).toFixed(3)})`;
      draw2d.beginPath();
      draw2d.arc(dot.x, still ? dot.y : (dot.y - seconds * dot.drift % height + height) % height, dot.r, 0, Math.PI * 2);
      draw2d.fill();
    }
  }

  function loop(now) {
    frame = 0;
    if (reducedQuery.matches || !onScreen || document.hidden) return;
    if (now - last > 40) { last = now; render(now / 1000); }
    frame = requestAnimationFrame(loop);
  }

  function restart() {
    cancelAnimationFrame(frame);
    frame = 0;
    if (reducedQuery.matches) render(0);
    else frame = requestAnimationFrame(loop);
  }

  new ResizeObserver(() => { resize(); restart(); }).observe(canvas);
  if ("IntersectionObserver" in window) {
    new IntersectionObserver((entries) => {
      onScreen = entries.some((entry) => entry.isIntersecting);
      if (onScreen && !frame) restart();
    }).observe(canvas);
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden && !frame) restart(); });
  if (reducedQuery.addEventListener) reducedQuery.addEventListener("change", restart);
  resize();
  restart();
}

// ---------- Start ----------
async function init() {
  await loadKeyMap();

  const scroller = byId("piano-scroll");
  keyboard = mountKeyboard(scroller, {
    onPress(midi) {
      unlockAudio();
      const played = audio.noteOn(midi, VELOCITY, `key:${midi}`);
      if (!played && audio.state === "ready" && audio.shift !== 0 && !audio.hasSample(midi)) {
        setStatus(text("soundMissing"), "loading");
      }
      emit("press", midi, performance.now());
    },
    onRelease(midi) {
      audio.noteOff(midi, `key:${midi}`);
      emit("release", midi, performance.now());
    },
    onPedal() {
      unlockAudio();
      setPedal(!pedal);
    }
  });
  keyboard.board.setAttribute("aria-label", byId("play").dataset.keyboardLabel || text("keyboardLabel"));
  refreshLabels();

  bindSegment("layout", () => settings.layout, (value) => {
    if (!LAYOUTS.includes(value)) return;
    settings.layout = value;
    saveSettings();
    refreshLabels();
    emit("layout", value);
  });
  bindSegment("labels", () => settings.labels, (value) => {
    settings.labels = value;
    saveSettings();
    refreshLabels();
    emit("labels", value);
  });

  const volume = byId("volume");
  const applyVolume = () => {
    const value = Number(volume.value);
    audio.setVolume(value);
    byId("volume-value").textContent = String(value);
    volume.style.setProperty("--fill", `${value}%`);
    settings.volume = value;
  };
  volume.value = String(settings.volume);
  volume.addEventListener("input", applyVolume);
  volume.addEventListener("change", saveSettings);
  applyVolume();

  byId("pedal").addEventListener("click", () => { unlockAudio(); setPedal(!pedal); });
  byId("tune-down").addEventListener("click", () => { tune -= 1; applyTune(); });
  byId("tune-up").addEventListener("click", () => { tune += 1; applyTune(); });
  // Sound tab: touch (layer), reverb preset and amount. Everything is remembered.
  bindSegment("hit", () => settings.hit, (value) => {
    if (!Object.hasOwn(LAYERS, value)) return;
    settings.hit = value;
    saveSettings();
    applyHit(value);
  });
  bindSegment("reverb", () => settings.reverb, (value) => {
    if (!["off", "room", "hall"].includes(value)) return;
    settings.reverb = value;
    saveSettings();
    audio.setReverb(settings.reverb, settings.reverbAmount);
    amount.disabled = value === "off";
  });
  const amount = byId("reverb-amount");
  const applyAmount = () => {
    settings.reverbAmount = Number(amount.value);
    byId("reverb-amount-value").textContent = `${settings.reverbAmount}%`;
    amount.style.setProperty("--fill", `${settings.reverbAmount}%`);
    audio.setReverb(settings.reverb, settings.reverbAmount);
  };
  amount.value = String(settings.reverbAmount);
  amount.disabled = settings.reverb === "off";
  amount.addEventListener("input", applyAmount);
  amount.addEventListener("change", saveSettings);
  applyAmount();
  applyTune();
  byId("scroll-left").addEventListener("click", () => keyboard.scrollOctave(-1));
  byId("scroll-right").addEventListener("click", () => keyboard.scrollOctave(1));
  retryButton.addEventListener("click", async () => {
    if (audio.state === "ready") {
      await applyHit(settings.hit);
      await applyTune();
    } else {
      await startLoading();
    }
  });

  const nav = byId("scroll-nav");
  const updateScrollNav = () => { nav.hidden = scroller.scrollWidth <= scroller.clientWidth + 1; };
  new ResizeObserver(updateScrollNav).observe(scroller);
  updateScrollNav();
  keyboard.scrollToMidi(60, { smooth: false, center: true });

  for (const name of UNLOCK_EVENTS) document.addEventListener(name, unlockAudio, true);
  window.addEventListener("blur", releaseEverything);
  document.addEventListener("visibilitychange", () => { if (document.hidden) releaseEverything(); });

  const glow = byId("glow-canvas");
  if (glow) initGlow(glow);

  context = {
    lang,
    t: text,
    audio,
    player,
    keyboard,
    keymap,
    getLayout: () => settings.layout,
    getLabelMode: () => settings.labels,
    // Events: "press" (midi, ms), "release" (midi, ms), "layout" (layout), "labels" (mode).
    on,
    unlock: unlockAudio,
    // Stops plan playback and clears "next" / "play" highlights.
    stopAll() {
      player.stop();
      audio.releaseTokens("plan:");
      keyboard.clearHighlights("next");
      keyboard.clearHighlights("play");
    }
  };
  window.vpa = context;
  pageReady = true;
  for (const id of panelMounts.keys()) mountPanel(id);
  loadPanelModules().then(() => {
    // Panel mounts are async; wait for layout, then once more after the page's resources settle.
    // Content above the target keeps growing for a moment; re-align until the user scrolls on their own.
    let userMoved = false;
    for (const name of ["wheel", "touchstart", "keydown", "pointerdown"]) {
      window.addEventListener(name, () => { userMoved = true; }, { once: true, passive: true });
    }
    for (const delay of [150, 600, 1500]) setTimeout(() => { if (!userMoved) scrollToHash(); }, delay);
  });

  startLoading();
}

init();
