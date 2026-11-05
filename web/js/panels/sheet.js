// "Letter notes" panel: paste or open letter notation, practice it key by key.
// Other panels use it through the exported loadText() / stopPractice() or ctx.sheet.

import { Follow } from "../follow.js";
import { MAX_BYTES, NotationError, decodeNotation, detectLayout, parseLetters } from "../letters.js";

let current = null; // the mounted panel API

// Puts text (and optionally its already known tokens) into the panel; `practice: true` starts the practice.
// Returns {ok, error?}; {ok: false} with no error means the panel is not on the page.
export function loadText(text, options) {
  return current ? current.loadText(text, options) : { ok: false };
}

export function stopPractice() {
  if (current) current.stopPractice();
}

export function isPracticing() {
  return Boolean(current && current.practicing);
}

// A text with clickable, highlightable tokens. tokens: [{from, to}] (positions in the text).
// Classes: is-next (token to play), is-done (before the cursor), is-playing (sounding now).
export function createTokenView(container, { onSelect = null, label = "" } = {}) {
  const element = document.createElement("div");
  element.className = "token-view";
  element.tabIndex = 0;
  if (label) element.setAttribute("aria-label", label);
  container.append(element);
  let spans = [];
  let cursor = 0;
  let playing = -1;

  function scrollTo(index) {
    const span = spans[index];
    if (!span) return;
    const top = span.offsetTop - element.offsetTop;
    const bottom = top + span.offsetHeight;
    if (top < element.scrollTop + 8 || bottom > element.scrollTop + element.clientHeight - 8) {
      element.scrollTop = Math.max(0, top - element.clientHeight * 0.35);
    }
  }

  const view = {
    element,
    get length() { return spans.length; },
    render(text, tokens) {
      const fragment = document.createDocumentFragment();
      spans = [];
      let position = 0;
      tokens.forEach((token, index) => {
        if (token.from > position) fragment.append(text.slice(position, token.from));
        const span = document.createElement("span");
        span.className = "tok";
        span.dataset.i = String(index);
        span.textContent = text.slice(token.from, token.to);
        fragment.append(span);
        spans.push(span);
        position = token.to;
      });
      if (position < text.length) fragment.append(text.slice(position));
      element.replaceChildren(fragment);
      cursor = 0;
      playing = -1;
      element.scrollTop = 0;
    },
    // Cursor: tokens before it are done, the token at it is next. index >= length means "all done".
    setCurrent(index, { scroll = true } = {}) {
      const next = Math.max(0, Math.min(spans.length, index));
      if (spans[cursor]) spans[cursor].classList.remove("is-next");
      for (let i = Math.min(cursor, next); i < Math.max(cursor, next); i++) spans[i].classList.toggle("is-done", i < next);
      cursor = next;
      if (spans[cursor]) {
        spans[cursor].classList.add("is-next");
        if (scroll) scrollTo(cursor);
      }
    },
    get cursor() { return cursor; },
    setPlaying(index, { scroll = true } = {}) {
      if (spans[playing]) spans[playing].classList.remove("is-playing");
      playing = spans[index] ? index : -1;
      if (playing >= 0) {
        spans[playing].classList.add("is-playing");
        if (scroll) scrollTo(playing);
      }
    },
    clear() {
      spans = [];
      cursor = 0;
      playing = -1;
      element.replaceChildren();
    }
  };

  element.addEventListener("click", (event) => {
    const span = event.target.closest && event.target.closest(".tok");
    if (span && onSelect) onSelect(Number(span.dataset.i));
  });
  element.addEventListener("keydown", (event) => {
    if (!onSelect || event.ctrlKey || event.altKey || event.metaKey) return;
    const steps = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: 1, ArrowUp: -1 };
    let target = null;
    if (event.key in steps) target = cursor + steps[event.key];
    else if (event.key === "Home") target = 0;
    else if (event.key === "End") target = spans.length - 1;
    if (target === null) return;
    event.preventDefault();
    if (spans.length) onSelect(Math.max(0, Math.min(spans.length - 1, target)));
  });
  return view;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function mount(body, ctx) {
  const t = ctx.t;
  const section = body.closest("section") || body;
  const ids = { input: "sheet-input", error: "sheet-error", info: "sheet-info" };

  const label = el("label", "group-label", t("sheet.fieldLabel"));
  label.htmlFor = ids.input;
  const input = el("textarea", "sheet-input");
  input.id = ids.input;
  input.rows = 6;
  input.spellcheck = false;
  input.autocomplete = "off";
  input.placeholder = t("sheet.placeholder");
  input.setAttribute("aria-describedby", `${ids.error} ${ids.info}`);

  const fileInput = el("input");
  fileInput.type = "file";
  fileInput.accept = ".txt,text/plain";
  fileInput.hidden = true;

  const view = createTokenView(body, {
    label: t("sheet.viewLabel"),
    onSelect(index) {
      if (!practicing) return;
      follow.reset(index);
      refresh("click");
    }
  });
  view.element.hidden = true;

  const errorEl = el("p", "sheet-error");
  errorEl.id = ids.error;
  errorEl.setAttribute("role", "alert");
  errorEl.hidden = true;
  const infoEl = el("p", "sheet-info");
  infoEl.id = ids.info;

  const emptyEl = el("div", "sheet-empty");
  const demoLink = el("a", "btn small", t("sheet.openDemo"));
  demoLink.href = "#demos";
  emptyEl.append(el("p", "", t("sheet.emptyHint")), demoLink);

  const openButton = el("button", "btn", t("sheet.open"));
  const practiceButton = el("button", "btn primary", t("sheet.practice"));
  const restartButton = el("button", "btn", t("sheet.restart"));
  for (const button of [openButton, practiceButton, restartButton]) button.type = "button";
  restartButton.hidden = true;
  const actions = el("div", "actions sheet-actions");
  actions.append(openButton, practiceButton, restartButton);

  const statusEl = el("p", "sheet-status");
  statusEl.setAttribute("role", "status");
  statusEl.setAttribute("aria-live", "polite");

  body.replaceChildren(label, input, view.element, errorEl, infoEl, emptyEl, actions, statusEl, fileInput);

  let practicing = false;
  let tokens = [];
  let follow = null;
  let provided = null; // {text, tokens} given by another panel
  let parseTimer = 0;

  // ---------- Reading the text ----------
  function messageFor(error, layout) {
    const params = { line: error.line, char: error.char, layout: String(layout).toUpperCase() };
    switch (error.code) {
      case "unknown": return t("sheet.errUnknown", params);
      case "too_long": return t("sheet.errTooLong", params);
      case "too_many": return t("sheet.errTooMany");
      case "too_large": return t("sheet.errTooLarge");
      case "encoding": return t("sheet.errEncoding");
      case "binary": return t("sheet.errBinary");
      default: return t("sheet.errRead");
    }
  }

  function showError(message) {
    errorEl.textContent = message || "";
    errorEl.hidden = !message;
    input.setAttribute("aria-invalid", String(Boolean(message)));
  }

  // Parses the field; shows the error or the note count. Returns {tokens, error}.
  function analyze() {
    const text = input.value;
    const blank = !text.trim();
    emptyEl.hidden = !blank || practicing;
    infoEl.textContent = "";
    showError("");
    tokens = [];
    if (blank) return { tokens, error: null };
    let parsed;
    let layout;
    if (provided && provided.text === text) {
      parsed = provided.tokens;
      layout = provided.layout || ctx.getLayout();
    } else {
      layout = detectLayout(text, ctx.getLayout());
      try {
        parsed = parseLetters(text, layout);
      } catch (error) {
        if (!(error instanceof NotationError)) throw error;
        showError(messageFor(error, layout));
        return { tokens, error };
      }
    }
    tokens = parsed;
    const detected = layout !== ctx.getLayout() ? ` ${t("sheet.layoutAuto")}` : "";
    infoEl.textContent = `${t("sheet.info", { count: parsed.filter((token) => token.notes.length).length, layout: String(layout).toUpperCase() })}${detected}`;
    return { tokens, error: null };
  }

  input.addEventListener("input", () => {
    provided = provided && provided.text === input.value ? provided : null;
    clearTimeout(parseTimer);
    parseTimer = setTimeout(analyze, 200);
    statusEl.textContent = "";
  });

  // ---------- Opening a file (read in the browser only) ----------
  openButton.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files && fileInput.files[0];
    fileInput.value = "";
    if (!file) return;
    try {
      if (file.size > MAX_BYTES) throw new NotationError("too_large");
      const text = decodeNotation(await file.arrayBuffer());
      stopPractice();
      provided = null;
      input.value = text;
      const result = analyze();
      if (!result.error) statusEl.textContent = t("sheet.fileLoaded", { name: file.name });
    } catch (error) {
      showError(error instanceof NotationError ? messageFor(error, ctx.getLayout()) : t("sheet.errRead"));
      statusEl.textContent = "";
    }
  });

  // ---------- Practice ----------
  function showStatus(message, state) {
    statusEl.textContent = message;
    statusEl.dataset.state = state || "";
  }

  function refresh(action) {
    ctx.keyboard.clearHighlights("next");
    view.setCurrent(follow.cursor);
    if (follow.done) {
      showStatus(t("sheet.done"), "done");
      return;
    }
    const notes = follow.tokens[follow.cursor];
    for (const midi of notes) ctx.keyboard.highlight(midi, "next", true);
    const sorted = [...notes].sort((a, b) => a - b);
    ctx.keyboard.scrollToMidi(sorted[Math.floor((sorted.length - 1) / 2)], { smooth: true });
    const params = { position: follow.cursor + 1, total: follow.tokens.length };
    if (action === "wait") showStatus(t("sheet.stepWrong", params), "wrong");
    else if (action === "partial") showStatus(t("sheet.stepPartial", params), "");
    else if (action === "skip") showStatus(t("sheet.stepSkip", params), "");
    else showStatus(t("sheet.stepWaiting", params), "");
  }

  function startPractice() {
    clearTimeout(parseTimer);
    const result = analyze();
    if (result.error) {
      if (result.error.from !== null) {
        input.focus();
        try { input.setSelectionRange(result.error.from, result.error.to); } catch (error) { /* ignore */ }
      }
      return false;
    }
    if (!tokens.some((token) => token.notes.length)) {
      showStatus(t("sheet.noTokens"), "wrong");
      return false;
    }
    ctx.stopAll();
    follow = new Follow(tokens);
    practicing = true;
    view.render(input.value, tokens);
    input.hidden = true;
    view.element.hidden = false;
    emptyEl.hidden = true;
    restartButton.hidden = false;
    practiceButton.textContent = t("sheet.edit");
    practiceButton.classList.remove("primary");
    refresh("start");
    view.element.focus({ preventScroll: true });
    return true;
  }

  function stopPractice() {
    if (!practicing) return;
    practicing = false;
    follow = null;
    ctx.keyboard.clearHighlights("next");
    input.hidden = false;
    view.element.hidden = true;
    restartButton.hidden = true;
    practiceButton.textContent = t("sheet.practice");
    practiceButton.classList.add("primary");
    showStatus("", "");
    analyze();
  }

  practiceButton.addEventListener("click", () => {
    ctx.unlock();
    if (practicing) stopPractice();
    else startPractice();
  });
  restartButton.addEventListener("click", () => {
    if (!practicing) return;
    follow.reset(0);
    refresh("start");
    view.element.focus({ preventScroll: true });
  });

  ctx.on("press", (midi, ms) => {
    if (!practicing || ctx.player.playing) return;
    refresh(follow.press(midi, ms).action);
  });
  ctx.on("layout", () => {
    if (!practicing) analyze();
  });

  current = {
    get practicing() { return practicing; },
    stopPractice,
    startPractice,
    loadText(text, { tokens: given = null, layout = null, practice = false, scroll = true } = {}) {
      stopPractice();
      input.value = text;
      provided = given ? { text, tokens: given, layout } : null;
      const result = analyze();
      if (scroll) section.scrollIntoView({ block: "start" });
      if (result.error) return { ok: false, error: result.error };
      return { ok: practice ? startPractice() : true };
    }
  };
  ctx.sheet = current;
  analyze();
}
