// "Demos" panel: old melodies from easy to hard, some with two hands. Play with highlights, practice them, or show their letters.

import { DEMOS, LEVEL_LABELS, demoEvents, demoPlan } from "../../demos.js";
import { renderTokens } from "../letters.js";
import { createTokenView, loadText, stopPractice } from "./sheet.js";

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function mount(body, ctx) {
  const t = ctx.t;
  const lang = ctx.lang;
  let activeCard = null;
  let run = 0;
  let watcher = 0;
  // Keys this panel lit with the "play" highlight; only these are cleared, never another panel's.
  const lit = new Set();

  const list = el("div", "demo-list");
  const cards = DEMOS.map((demo) => buildCard(demo));
  list.append(...cards.map((card) => card.root));
  body.replaceChildren(list);

  function lettersFor(demo) {
    return renderTokens(demoEvents(demo), ctx.getLayout(), { chordValue: 40, spacing: true });
  }

  function buildCard(demo) {
    const title = demo.title[lang] || demo.title.en;
    const root = el("article", "demo-card");
    const head = el("div", "demo-head");
    const heading = el("h3", "demo-title", title);
    const meta = el("p", "demo-meta", `${demo.composer[lang] || demo.composer.en} · ${t("demos.notes", { count: demo.notes.length, bpm: demo.bpm })}`);
    const level = el("span", "tag demo-level", (LEVEL_LABELS[demo.level] || LEVEL_LABELS.easy)[lang] || LEVEL_LABELS.easy.en);
    level.style.marginTop = "6px";
    head.append(heading, meta, level);

    const playButton = el("button", "btn primary small", t("demos.play"));
    const practiceButton = el("button", "btn small", t("demos.practice"));
    const showButton = el("button", "btn small", t("demos.show"));
    for (const button of [playButton, practiceButton, showButton]) button.type = "button";
    const actions = el("div", "actions demo-actions");
    actions.append(playButton, practiceButton, showButton);

    const note = el("p", "demo-note");
    note.setAttribute("role", "status");
    const letters = el("div", "demo-letters");
    letters.hidden = true;
    const view = createTokenView(letters, { label: t("demos.lettersLabel", { title }) });
    root.append(head, actions, note, letters);

    const card = { demo, root, playButton, showButton, note, letters, view, shown: false, rendered: null };

    const renderLetters = () => {
      const result = lettersFor(demo);
      card.rendered = result;
      view.render(result.text, result.tokens);
    };
    card.showLetters = (on) => {
      card.shown = on;
      letters.hidden = !on;
      showButton.textContent = on ? t("demos.hide") : t("demos.show");
      showButton.setAttribute("aria-expanded", String(on));
      if (on) renderLetters();
    };

    playButton.addEventListener("click", () => {
      if (activeCard === card) stopDemo();
      else playDemo(card);
    });
    showButton.addEventListener("click", () => card.showLetters(!card.shown));
    practiceButton.addEventListener("click", () => {
      stopDemo();
      ctx.unlock();
      const result = lettersFor(demo);
      loadText(result.text, { tokens: result.tokens, layout: ctx.getLayout(), practice: true });
    });
    return card;
  }

  // ---------- Playing ----------
  function resetCard(card) {
    card.playButton.textContent = t("demos.play");
    card.playButton.classList.add("primary");
    card.view.setPlaying(-1);
  }

  function clearOwnHighlights() {
    for (const midi of lit) ctx.keyboard.highlight(midi, "play", false);
    lit.clear();
  }

  // Ends the demo's own state only. The player, "next" highlights and other panels' playback are not touched.
  function finish(card) {
    if (activeCard !== card) return;
    clearInterval(watcher);
    activeCard = null;
    resetCard(card);
    clearOwnHighlights();
  }

  // Stops the demo on the user's request (button, another demo, practice): this one stops the player too.
  function stopDemo() {
    if (!activeCard) return;
    const card = activeCard;
    run++;
    ctx.player.stop();
    ctx.audio.releaseTokens("plan:");
    finish(card);
  }

  async function playDemo(card) {
    stopDemo();
    stopPractice();
    ctx.unlock();
    const myRun = ++run;
    activeCard = card;
    card.note.textContent = "";
    card.playButton.textContent = t("demos.stop");
    card.playButton.classList.remove("primary");
    card.showLetters(true);
    const plan = demoPlan(card.demo);
    // The page pauses the player on blur or a hidden tab; then the demo is stopped instead of hanging.
    watcher = setInterval(() => {
      if (activeCard === card && ctx.player.paused) stopDemo();
    }, 250);
    try {
      await ctx.player.play(plan, {
        onNote(midi, on, token) {
          if (myRun !== run) return;
          ctx.keyboard.highlight(midi, "play", on);
          if (on) lit.add(midi);
          else lit.delete(midi);
          if (on) {
            card.view.setPlaying(token);
            ctx.keyboard.scrollToMidi(midi, { smooth: true });
          }
        }
      });
    } catch (error) {
      console.warn(error);
      if (myRun === run) card.note.textContent = t("demos.playError");
    } finally {
      if (myRun === run) finish(card);
    }
  }

  ctx.on("layout", () => {
    for (const card of cards) {
      if (card.shown && card !== activeCard) card.showLetters(true);
    }
  });
}
