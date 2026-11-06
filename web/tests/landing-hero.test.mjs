import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// The landing hero is just the laptop cut-out: no card, no stage, size set up front.
const root = fileURLToPath(new URL("../../", import.meta.url));
const pages = { de: "index.html", en: "index-en.html", ru: "index-ru.html" };

for (const [lang, page] of Object.entries(pages)) {
  test(`${page} hero shows the laptop cut-out without a stage`, () => {
    const html = readFileSync(`${root}${page}`, "utf8");
    const hero = html.slice(html.indexOf('class="laptop-hero"'), html.indexOf("</figure>", html.indexOf('class="laptop-hero"')));
    assert.ok(hero.length > 0, "figure.laptop-hero exists");
    assert.match(hero, new RegExp(`<img\\b[^>]*src="assets/surface-laptop-cutout-${lang}\\.webp"[^>]*width="1496"[^>]*height="974"`));
    assert.ok(!html.includes("ppk-stage"), "no ppk-stage");
    assert.ok(!html.includes("ppk-preview"), "no ppk-preview card");
    assert.match(hero, new RegExp(`<a class="ppk-open" href="assets/surface-laptop-cutout-${lang}\\.webp"`), "the full-size link opens the same language image");
  });
}

test("each language has its own cut-out file", () => {
  for (const lang of Object.keys(pages)) assert.ok(existsSync(`${root}assets/surface-laptop-cutout-${lang}.webp`));
});
