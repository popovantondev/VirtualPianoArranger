// "MIDI" panel: open a .mid file in the browser, listen to and choose its parts, turn them into letters
// for the 61 keys, play the result with highlights, practice it or save it as TXT.
// The file is read here and never leaves the browser.

import { MAX_BYTES, MidiError, readMidi, selectParts, scoreClock, previewPlan } from "../midi.js";
import { groupedEvents, melodyOnly, findBestTransposition, eventsToPlan } from "../arrange.js";
import { renderTokens } from "../letters.js";
import { createTokenView, stopPractice } from "./sheet.js";

const DEFAULT_CHORDS = 40;
const COMFORT = 50;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function button(label, className = "btn") {
  const node = el("button", className, label);
  node.type = "button";
  return node;
}

function signed(value) {
  return value > 0 ? `+${value}` : value < 0 ? `−${-value}` : "0";
}

export function mount(body, ctx) {
  const t = ctx.t;
  const section = body.closest("section") || body;

  // ---------- Markup ----------
  const fileInput = el("input");
  fileInput.type = "file";
  fileInput.accept = ".mid,.midi,audio/midi,audio/x-midi";
  fileInput.hidden = true;

  const openButton = button(t("midi.open"), "btn primary");
  const dropHint = el("p", "midi-drop-hint", t("midi.drop"));
  const privacy = el("p", "midi-privacy", t("midi.privacy"));
  const drop = el("div", "midi-drop");
  drop.append(openButton, dropHint, privacy);

  const errorEl = el("p", "sheet-error");
  errorEl.setAttribute("role", "alert");
  errorEl.hidden = true;
  const warningEl = el("p", "midi-warning");
  warningEl.hidden = true;
  const fileInfo = el("p", "sheet-info");

  // Parts
  const partsBox = el("div", "midi-parts-box");
  partsBox.hidden = true;
  const partsTitle = el("p", "group-label", t("midi.partsTitle"));
  const partsHint = el("p", "midi-hint", t("midi.partsHint"));
  const partsList = el("ul", "midi-parts");
  partsList.setAttribute("aria-label", t("midi.partsTitle"));
  const listenSelected = button(t("midi.listenSelected"), "btn small");
  const stopPreview = button(t("midi.stop"), "btn small");
  const convertButton = button(t("midi.convert"), "btn primary");
  const partActions = el("div", "actions midi-part-actions");
  partActions.append(listenSelected, stopPreview, convertButton);
  const partStatus = el("p", "sheet-status");
  partStatus.setAttribute("role", "status");
  partStatus.setAttribute("aria-live", "polite");
  partsBox.append(partsTitle, partsHint, partsList, partActions, partStatus);

  // Result
  const resultBox = el("div", "midi-result");
  resultBox.hidden = true;
  const resultTitle = el("p", "group-label", t("midi.resultTitle"));

  const shiftDown = button("−");
  shiftDown.setAttribute("aria-label", t("midi.shiftDown"));
  const shiftUp = button("+");
  shiftUp.setAttribute("aria-label", t("midi.shiftUp"));
  const shiftValue = el("output", "", "0");
  shiftValue.setAttribute("aria-label", t("midi.shift"));
  const shiftSeg = el("div", "seg stepper");
  shiftSeg.append(shiftDown, shiftValue, shiftUp);
  const autoButton = button(t("midi.auto"), "btn small");
  const shiftRow = el("div", "midi-inline");
  shiftRow.append(shiftSeg, autoButton);
  const shiftGroup = el("div", "group");
  shiftGroup.setAttribute("role", "group");
  shiftGroup.append(el("span", "group-label", t("midi.shift")), shiftRow);

  const chordsId = "midi-chords";
  const chords = el("input");
  chords.type = "range";
  chords.id = chordsId;
  chords.min = "10";
  chords.max = "100";
  chords.step = "5";
  chords.value = String(DEFAULT_CHORDS);
  const chordsValue = el("output", "", String(DEFAULT_CHORDS));
  chordsValue.htmlFor = chordsId;
  const chordsLabel = el("label", "group-label", t("midi.chords"));
  chordsLabel.htmlFor = chordsId;
  const chordsEnds = el("span", "midi-ends");
  chordsEnds.append(el("span", "", t("midi.chordsFull")), el("span", "", t("midi.chordsSimple")));
  const chordsSlider = el("div", "slider");
  chordsSlider.append(chords, chordsValue);
  const chordsGroup = el("div", "group group-wide");
  chordsGroup.append(chordsLabel, chordsSlider, chordsEnds);

  const melodyButton = button(t("midi.melody"), "btn small midi-toggle");
  melodyButton.setAttribute("aria-pressed", "false");
  const melodyGroup = el("div", "group");
  melodyGroup.append(el("span", "group-label", t("midi.melodyLabel")), melodyButton);

  const settings = el("div", "controls midi-controls");
  settings.append(shiftGroup, chordsGroup, melodyGroup);

  const outsideEl = el("p", "midi-warning");
  outsideEl.hidden = true;
  const view = createTokenView(resultBox, { label: t("midi.viewLabel") });
  const emptyEl = el("p", "sheet-info", t("midi.empty"));
  emptyEl.hidden = true;

  const playButton = button(t("midi.play"), "btn primary");
  const stopButton = button(t("midi.stop"));
  const speed = el("input");
  speed.type = "range";
  speed.id = "midi-speed";
  speed.min = "50";
  speed.max = "150";
  speed.step = "5";
  speed.value = "100";
  const speedValue = el("output", "", "100%");
  speedValue.htmlFor = speed.id;
  const speedLabel = el("label", "group-label", t("midi.speed"));
  speedLabel.htmlFor = speed.id;
  const speedSlider = el("div", "slider");
  speedSlider.append(speed, speedValue);
  const speedGroup = el("div", "group group-speed");
  speedGroup.append(speedLabel, speedSlider);
  const practiceButton = button(t("midi.practice"));
  const saveButton = button(t("midi.save"));
  const playRow = el("div", "controls midi-play");
  const transport = el("div", "actions");
  transport.append(playButton, stopButton);
  playRow.append(transport, speedGroup);
  const resultActions = el("div", "actions midi-result-actions");
  resultActions.append(practiceButton, saveButton);
  const resultStatus = el("p", "sheet-status");
  resultStatus.setAttribute("role", "status");
  resultStatus.setAttribute("aria-live", "polite");
  resultBox.append(resultTitle, settings, outsideEl, emptyEl, playRow, resultActions, resultStatus);
  // The token view was appended to resultBox by createTokenView; keep it between the warning and the buttons.
  resultBox.insertBefore(view.element, emptyEl);

  body.replaceChildren(drop, errorEl, warningEl, fileInfo, partsBox, resultBox, fileInput);

  // ---------- State ----------
  let score = null;
  let fileName = "midi";
  const selected = new Set();
  let model = null; // {chosen, events, melody, clock}
  let shift = 0;
  let chordValue = DEFAULT_CHORDS;
  let melodyMode = false;
  let rendered = null;
  let mode = null; // null | "part:<id>" | "selected" | "play"
  let userPaused = false;
  let run = 0;
  let watcher = 0;
  const listenButtons = new Map();

  function setSlider(input) {
    input.style.setProperty("--fill", `${((Number(input.value) - Number(input.min)) / (Number(input.max) - Number(input.min))) * 100}%`);
  }

  // ---------- Messages ----------
  function showError(message) {
    errorEl.textContent = message || "";
    errorEl.hidden = !message;
  }

  function errorMessage(error) {
    const code = error instanceof MidiError ? error.code : "read";
    switch (code) {
      case "not_midi": return t("midi.errNotMidi");
      case "format2": return t("midi.errFormat2");
      case "smpte": return t("midi.errSmpte");
      case "too_large": return t("midi.errTooLarge");
      case "truncated": case "trailing": case "bad_track": case "bad_header": return t("midi.errBroken");
      case "too_many_events": case "too_many_notes": case "too_many_parts": case "too_long": case "too_many_measures": return t("midi.errTooMany");
      case "read": return t("midi.errRead");
      default: return t("midi.errBad");
    }
  }

  // ---------- Playing ----------
  function updateButtons() {
    const playing = mode === "play";
    playButton.textContent = playing && !userPaused ? t("midi.pause") : t("midi.play");
    playButton.classList.toggle("primary", !(playing && !userPaused));
    stopButton.disabled = !playing;
    const auditioning = mode !== null && mode !== "play";
    stopPreview.disabled = !auditioning;
    listenSelected.textContent = mode === "selected" ? t("midi.stop") : t("midi.listenSelected");
    for (const [id, node] of listenButtons) node.textContent = mode === `part:${id}` ? t("midi.stop") : t("midi.listen");
  }

  function finishPlayback() {
    clearInterval(watcher);
    mode = null;
    userPaused = false;
    ctx.keyboard.clearHighlights("play");
    view.setPlaying(-1);
    updateButtons();
  }

  function stopPlayback() {
    if (mode === null) return;
    run++;
    ctx.player.stop();
    finishPlayback();
  }

  async function playPlan(owner, plan, options = {}) {
    stopPlayback();
    stopPractice();
    ctx.unlock();
    const myRun = ++run;
    mode = owner;
    userPaused = false;
    updateButtons();
    // The page pauses the player on blur or a hidden tab; then playback is stopped instead of hanging.
    watcher = setInterval(() => {
      if (mode === owner && myRun === run && ctx.player.paused && !userPaused) stopPlayback();
    }, 250);
    try {
      await ctx.player.play(plan, {
        speed: options.speed || 1,
        onNote(midi, on, token) {
          if (myRun !== run) return;
          ctx.keyboard.highlight(midi, "play", on);
          if (on) {
            if (options.showTokens && token !== undefined) view.setPlaying(token);
            ctx.keyboard.scrollToMidi(midi, { smooth: true });
          }
        }
      });
    } catch (error) {
      console.warn(error);
      if (myRun === run) (options.status || partStatus).textContent = t("midi.playError");
    } finally {
      if (myRun === run) finishPlayback();
    }
  }

  function audition(owner, ids) {
    if (mode === owner) {
      stopPlayback();
      return;
    }
    if (!ids.length) {
      partStatus.textContent = t("midi.noSelection");
      return;
    }
    let plan;
    try {
      plan = previewPlan(score, ids);
    } catch (error) {
      if (!(error instanceof MidiError)) throw error;
      partStatus.textContent = error.code === "no_preview_notes" ? t("midi.noPreview") : t("midi.noSelection");
      return;
    }
    partStatus.textContent = t("midi.auditionInfo") + (plan.outside ? ` ${t("midi.auditionOutside", { count: plan.outside })}` : "");
    playPlan(owner, plan, { status: partStatus });
  }

  function togglePlay() {
    if (mode === "play") {
      if (userPaused) {
        userPaused = false;
        ctx.unlock();
        ctx.player.resume();
      } else {
        userPaused = true;
        ctx.player.pause();
      }
      updateButtons();
      return;
    }
    if (!model || !rendered) return;
    const list = melodyMode ? model.melody : model.events;
    const plan = eventsToPlan(list, shift, chordValue, model.clock, { trimStart: true });
    if (!plan.notes.length) {
      resultStatus.textContent = t("midi.empty");
      return;
    }
    resultStatus.textContent = "";
    playPlan("play", plan, { speed: Number(speed.value) / 100, showTokens: true, status: resultStatus });
  }

  // ---------- Parts ----------
  function describePart(part) {
    const low = ctx.keymap.noteName(part.low, ctx.lang);
    const high = ctx.keymap.noteName(part.high, ctx.lang);
    return t("midi.partStats", { count: part.noteCount, low, high });
  }

  function renderParts() {
    listenButtons.clear();
    const items = score.parts.map((part, index) => {
      const item = el("li", "midi-part");
      const id = `midi-part-${index}`;
      const check = el("input");
      check.type = "checkbox";
      check.id = id;
      check.checked = selected.has(part.id);
      check.disabled = !part.active;
      const label = el("label", "midi-part-label");
      label.htmlFor = id;
      label.append(el("span", "midi-part-name", part.name));
      const detail = part.percussion ? t("midi.partPercussion") : part.noteCount ? describePart(part) : t("midi.partEmpty");
      label.append(el("span", "midi-part-stats", detail));
      const listen = button(t("midi.listen"), "btn small");
      listen.disabled = !part.active;
      listen.setAttribute("aria-label", `${t("midi.listen")}: ${part.name}`);
      listenButtons.set(part.id, listen);
      item.classList.toggle("is-disabled", !part.active);
      item.append(check, label, listen);
      check.addEventListener("change", () => {
        if (check.checked) selected.add(part.id);
        else selected.delete(part.id);
        stopPlayback();
        convertButton.disabled = !selected.size;
        partStatus.textContent = selected.size ? "" : t("midi.noSelection");
      });
      listen.addEventListener("click", () => audition(`part:${part.id}`, [part.id]));
      return item;
    });
    partsList.replaceChildren(...items);
    convertButton.disabled = !selected.size;
    partStatus.textContent = "";
    updateButtons();
  }

  // ---------- Letters ----------
  function renderLetters() {
    const list = melodyMode ? model.melody : model.events;
    rendered = renderTokens(list, ctx.getLayout(), { semitones: shift, chordValue, spacing: false });
    view.render(rendered.text, rendered.tokens);
    shiftValue.textContent = signed(shift);
    shiftDown.disabled = shift <= -12;
    shiftUp.disabled = shift >= 12;
    outsideEl.hidden = !rendered.outside.length;
    outsideEl.textContent = rendered.outside.length ? t("midi.outside", { count: rendered.outside.length }) : "";
    const usable = rendered.tokens.some((token) => token.notes.length);
    emptyEl.hidden = usable;
    view.element.hidden = !usable;
    for (const node of [playButton, practiceButton, saveButton]) node.disabled = !usable;
    resultStatus.textContent = "";
  }

  function recompute() {
    stopPlayback();
    renderLetters();
  }

  function convert() {
    if (!score || !selected.size) {
      partStatus.textContent = t("midi.noSelection");
      return;
    }
    let chosen;
    try {
      chosen = selectParts(score, [...selected]);
    } catch (error) {
      if (!(error instanceof MidiError)) throw error;
      partStatus.textContent = t("midi.noSelection");
      return;
    }
    stopPlayback();
    const events = groupedEvents(chosen);
    model = { chosen, events, melody: melodyOnly(events), clock: scoreClock(chosen) };
    shift = findBestTransposition(melodyMode ? model.melody : events, chordValue, COMFORT);
    resultBox.hidden = false;
    renderLetters();
    resultStatus.textContent = t("midi.autoDone", { value: signed(shift) });
    resultBox.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  // ---------- Opening a file (read in the browser only) ----------
  async function openFile(file) {
    const hadScore = Boolean(score);
    let next;
    try {
      if (file.size > MAX_BYTES) throw new MidiError("too_large");
      next = readMidi(await file.arrayBuffer());
      if (!next.parts.some((part) => part.active)) {
        throw new MidiError(next.parts.length && next.parts.every((part) => part.percussion) ? "only_drums" : "no_notes");
      }
    } catch (error) {
      let message;
      if (error instanceof MidiError && error.code === "only_drums") message = t("midi.errDrums");
      else if (error instanceof MidiError && error.code === "no_notes") message = t("midi.errNoNotes");
      else message = errorMessage(error);
      showError(hadScore ? `${message} ${t("midi.errKept")}` : message);
      return;
    }
    showError("");
    stopPlayback();
    score = next;
    model = null;
    rendered = null;
    fileName = file.name.replace(/\.[^.]*$/, "").replace(/[\\/:*?"<>|\u0000-\u001f]/g, "_").trim() || "midi";
    selected.clear();
    for (const part of score.parts) if (part.active) selected.add(part.id);
    fileInfo.textContent = t("midi.fileLoaded", { name: file.name, count: score.parts.filter((part) => part.active).length });
    warningEl.hidden = score.exact;
    warningEl.textContent = score.exact ? "" : t("midi.approx");
    partsBox.hidden = false;
    resultBox.hidden = true;
    renderParts();
  }

  openButton.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    fileInput.value = "";
    if (file) openFile(file);
  });

  const hasFiles = (event) => Boolean(event.dataTransfer && Array.from(event.dataTransfer.types || []).includes("Files"));
  let dragDepth = 0;
  section.addEventListener("dragenter", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    dragDepth++;
    drop.classList.add("is-over");
  });
  section.addEventListener("dragover", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  });
  section.addEventListener("dragleave", (event) => {
    if (!hasFiles(event)) return;
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) drop.classList.remove("is-over");
  });
  section.addEventListener("drop", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    dragDepth = 0;
    drop.classList.remove("is-over");
    const file = event.dataTransfer.files && event.dataTransfer.files[0];
    if (file) openFile(file);
  });

  // ---------- Controls ----------
  listenSelected.addEventListener("click", () => audition("selected", [...selected]));
  stopPreview.addEventListener("click", stopPlayback);
  convertButton.addEventListener("click", convert);

  shiftDown.addEventListener("click", () => { shift = Math.max(-12, shift - 1); recompute(); });
  shiftUp.addEventListener("click", () => { shift = Math.min(12, shift + 1); recompute(); });
  autoButton.addEventListener("click", () => {
    if (!model) return;
    shift = findBestTransposition(melodyMode ? model.melody : model.events, chordValue, COMFORT);
    recompute();
    resultStatus.textContent = t("midi.autoDone", { value: signed(shift) });
  });
  chords.addEventListener("input", () => {
    chordValue = Number(chords.value);
    chordsValue.textContent = String(chordValue);
    setSlider(chords);
    if (model) recompute();
  });
  melodyButton.addEventListener("click", () => {
    melodyMode = !melodyMode;
    melodyButton.setAttribute("aria-pressed", String(melodyMode));
    if (model) recompute();
  });

  playButton.addEventListener("click", togglePlay);
  stopButton.addEventListener("click", stopPlayback);
  speed.addEventListener("input", () => {
    speedValue.textContent = `${speed.value}%`;
    setSlider(speed);
    if (mode === "play") ctx.player.setSpeed(Number(speed.value) / 100);
  });

  practiceButton.addEventListener("click", () => {
    if (!rendered) return;
    stopPlayback();
    ctx.unlock();
    if (!ctx.sheet) {
      resultStatus.textContent = t("midi.practiceUnavailable");
      return;
    }
    const outcome = ctx.sheet.loadText(rendered.text, { tokens: rendered.tokens, layout: ctx.getLayout(), practice: true, scroll: true });
    if (!outcome.ok) resultStatus.textContent = t("midi.practiceUnavailable");
  });

  saveButton.addEventListener("click", () => {
    if (!rendered) return;
    const blob = new Blob([rendered.text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${fileName}.txt`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    resultStatus.textContent = t("midi.saved", { name: `${fileName}.txt` });
  });

  ctx.on("layout", () => {
    if (model) renderLetters();
  });

  setSlider(chords);
  setSlider(speed);
  updateButtons();
}
