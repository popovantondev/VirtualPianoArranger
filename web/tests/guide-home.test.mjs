import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Every guide opens with a visible button to the program page of its own language.
const root = fileURLToPath(new URL("../../", import.meta.url));
const labels = { ru: "\u2190 \u041d\u0430 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0443 \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u044b", de: "\u2190 Zur Programmseite", en: "\u2190 Program page" };
const pages = { de: "index.html", en: "index-en.html", ru: "index-ru.html" };

for (const lang of Object.keys(labels)) {
  test(`Guide-${lang} links to ${pages[lang]}`, () => {
    const html = readFileSync(`${root}Guide-${lang}.html`, "utf8");
    assert.match(html, new RegExp(`<a\\b[^>]*href="${pages[lang]}"[^>]*>\\s*${labels[lang]}\\s*</a>`));
    assert.ok(existsSync(`${root}${pages[lang]}`), "the landing page exists");
    assert.ok(html.indexOf(labels[lang]) < html.indexOf("<h1"), "the button comes before the heading");
  });
}
