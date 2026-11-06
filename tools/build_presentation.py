"""Build localized product landing pages (shared kit) from reviewed release metadata.

Inputs: public-release.json (name, version, platform, texts, urls) and tools/presentation.json
(site folder, icon, palette, stack, bento facts). Output: index.html (German), index-en.html,
index-ru.html, index-de.html (redirect), theme.css (warm gold palette shared by landing pages,
guides and the play pages), presentation.css. Guides: polish_guides.py. Play pages: build_play_pages.py.
"""
from pathlib import Path
from html import escape as e
import json
import re

ROOT = Path(__file__).resolve().parents[1]
LANGS = ('ru', 'de', 'en')
PROFILE = 'https://popovantondev.github.io/popovantondev/'
PAGES = 'https://popovantondev.github.io/'
LANG_NAMES = {'ru': 'RU', 'de': 'DE', 'en': 'EN'}
LANG_TITLES = {'ru': 'Русский', 'de': 'Deutsch', 'en': 'English'}
PEDAL_ORDER = ('ru', 'en', 'de')  # left, middle, right pedal of the app (the shape of the brass pedal follows the position)

TEXT = {
    'ru': dict(
        skip='К содержимому', nav='Основная навигация', back='← Все программы', search='Поиск по программам', search_text='Поиск',
        kbd='Ctrl K', theme='Сменить тему', legal='Правовая информация', new='НОВОЕ', pill='Вышла версия {v}', more='Что нового →',
        download='Скачать для', source='Исходный код', guide='Руководство', play='Играть в браузере', requirements='Перед запуском', start='Первые шаги',
        flow='Как это работает', bento='Что внутри', bento_sub='Установка, функции, передача данных и проверка.', inst='Установка',
        feat='Функции', checks='Проверено', release='Выпуск', preview='Предварительная версия', only='Только исходники',
        shot='Демонстрационный интерфейс с искусственными данными. Открыть изображение целиком.',
        illustration='Демонстрационная иллюстрация, не снимок работающей программы.', open_full='Открыть целиком',
        study='Демонстрация рабочего пространства на русском; локализованные снимки пока не опубликованы.',
        source_note='Готового установочного пакета нет. Инструкции описывают настройку из исходников.',
        toc='Содержание', full='Открыть изображение целиком'),
    'de': dict(
        skip='Zum Inhalt', nav='Hauptnavigation', back='← Alle Programme', search='Programme durchsuchen', search_text='Suchen',
        kbd='Strg K', theme='Farbschema wechseln', legal='Rechtliches', new='NEU', pill='Version {v} ist da', more='Was ist neu →',
        download='Herunterladen für', source='Quellcode', guide='Anleitung', play='Im Browser spielen', requirements='Vor dem Start', start='Erste Schritte',
        flow='So funktioniert es', bento='Was drin steckt', bento_sub='Installation, Funktionen, Datenverbindung und Prüfung.',
        inst='Installation', feat='Funktionen', checks='Geprüft', release='Release', preview='Vorabversion', only='Nur Quellcode',
        shot='Demo-Oberfläche mit künstlichen Daten. Vollständiges Bild öffnen.',
        illustration='Demo-Illustration, kein Screenshot der laufenden Anwendung.', open_full='Vollständig öffnen',
        study='Demo-Arbeitsbereich auf Russisch; lokalisierte Ansichten sind noch nicht veröffentlicht.',
        source_note='Kein fertiges Installationspaket. Die Anleitung beschreibt die Einrichtung aus dem Quellcode.',
        toc='Inhalt', full='Vollständiges Bild öffnen'),
    'en': dict(
        skip='Skip to content', nav='Main navigation', back='← All programs', search='Search programs', search_text='Search',
        kbd='Ctrl K', theme='Switch colour scheme', legal='Legal', new='NEW', pill='Version {v} is out', more="What's new →",
        download='Download for', source='Source code', guide='User guide', play='Play in the browser', requirements='Before you start', start='First steps',
        flow='How it works', bento="What's inside", bento_sub='Installation, features, data flow and checks.', inst='Installation',
        feat='Features', checks='Checked', release='Release', preview='Preview', only='Source only',
        shot='Demonstration interface with artificial data. Open the full image.',
        illustration='Demonstration illustration, not a screenshot of the running application.', open_full='Open in full',
        study='Demonstration workspace in Russian; localized screenshots have not been published yet.',
        source_note='No ready-to-install package. The guide explains how to set up the source version.',
        toc='Contents', full='Open the full image'),
}


def load():
    cfg = json.loads((ROOT / 'tools/presentation.json').read_text(encoding='utf-8'))
    d = json.loads((ROOT / 'public-release.json').read_text(encoding='utf-8'))
    return cfg, d


def site_dir(cfg):
    return ROOT / cfg['folder']


def kit_version(cfg):
    return (site_dir(cfg) / 'assets/kit/KIT_VERSION').read_text(encoding='utf-8').strip()


def landing(lang):
    """File name of the landing page of a language (German is the root page)."""
    return {'de': 'index.html', 'en': 'index-en.html', 'ru': 'index-ru.html'}[lang]


def catalog(lang):
    return PROFILE + landing(lang)


def status_label(d, lang):
    t = TEXT[lang]
    return t[{'release': 'release', 'preview': 'preview', 'source': 'only'}[d['status']]] + ' · ' + d['version']


def nav_html(cfg, d, lang, page):
    """Kit header. page: 'landing' or 'guide' (the language switcher keeps the page kind)."""
    t = TEXT[lang]
    icon = cfg['icon']
    target = {'landing': landing, 'guide': lambda x: 'Guide-' + x + '.html', 'play': lambda x: 'play-' + x + '.html'}[page]
    langs = ''.join(
        f'<a href="{target(x)}" lang="{x}" hreflang="{x}"' + (' aria-current="page"' if x == lang else '') + f'>{LANG_NAMES[x]}</a>'
        for x in LANGS)
    langs_html = f'<div class="ppk-langs">{langs}</div>'
    if page == 'play':
        # The game page keeps the brass language pedals of the app in the shared header (styles: web/play.css).
        pedals = ''.join(
            f'<a class="pedal-link" href="{target(x)}" lang="{x}" hreflang="{x}" aria-label="{LANG_TITLES[x]}" title="{LANG_TITLES[x]}"'
            + (' aria-current="page"' if x == lang else '') + f'><span class="pedal-label">{LANG_NAMES[x]}</span></a>'
            for x in PEDAL_ORDER)
        langs_html = f'<div class="languages">{pedals}</div>'
    return (
        f'<div class="ppk-nav-wrap" id="ppk-nav-wrap">\n'
        f'  <nav class="ppk-nav" aria-label="{e(t["nav"])}">\n'
        f'    <a class="ppk-brand" href="{landing(lang)}"><img src="{e(icon)}" alt="" width="34" height="34"><span>{e(d["name"])}</span></a>\n'
        f'    <span class="ppk-spacer"></span>\n'
        f'    <a class="ppk-back" href="{catalog(lang)}">{e(t["back"])}</a>\n'
        f'    <button class="ppk-search-btn" type="button" data-ppk-open-search aria-label="{e(t["search"])}"><span>{e(t["search_text"])}</span><kbd>{e(t["kbd"])}</kbd></button>\n'
        f'    {langs_html}\n'
        f'    <button class="ppk-icon-btn ppk-theme-btn" type="button" data-ppk-theme aria-label="{e(t["theme"])}"></button>\n'
        f'    <a class="ppk-icon-btn ppk-gh-btn" href="{e(d["source_url"])}" aria-label="GitHub"></a>\n'
        f'  </nav>\n</div>')


def footer_html(d, lang):
    t = TEXT[lang]
    return (
        f'<footer class="ppk-footer">\n  <span>© 2026 Anton Popov · {e(d["name"])} {e(d["version"])}</span>\n'
        f'  <nav aria-label="{e(t["legal"])}"><a href="{PROFILE}impressum.html">Impressum</a>'
        f'<a href="{PROFILE}datenschutz.html">Datenschutz</a><a href="{e(d["source_url"])}">GitHub</a></nav>\n</footer>')


def head_assets(cfg, rel=''):
    v = kit_version(cfg)
    return (
        f'<script src="{rel}assets/kit/kit-theme.js"></script>'
        f'<link rel="stylesheet" href="{rel}assets/kit/kit.css?v={v}">'
        f'<link rel="stylesheet" href="{rel}theme.css?v={v}">'
        f'<script src="{rel}assets/kit/programs.js?v={v}" defer></script>'
        f'<script src="{rel}assets/kit/kit.js?v={v}" defer></script>')


def css_block(selector, values):
    return selector + '{' + ';'.join('--ppk-' + k + ':' + v for k, v in values.items()) + '}'


def theme_css(cfg):
    """Warm gold palette on the kit tokens (light, dark, system dark). Zero extra specificity needed:
    kit tokens use :where(), so these plain selectors win regardless of load order."""
    light = dict(cfg['palette'])
    dark = dict(cfg['palette_dark'])
    return (
        '/* Virtual Piano Arranger palette on the shared kit tokens (assets/kit/kit.css). Generated by tools/build_presentation.py. */\n'
        + css_block(':root', light) + '\n'
        + css_block(':root[data-theme="dark"]', dark) + '\n'
        + '@media (prefers-color-scheme:dark){' + css_block(':root:not([data-theme])', dark) + '}\n')


def page_css(cfg):
    return (
        '/* Landing-page-only rules. Components come from assets/kit/kit.css, the palette from theme.css. */\n'
        + '.ppk-meta-chip{margin-left:6px}\n'
        + '.ppk-start{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:24px;align-items:center;padding:28px;border:1px solid var(--ppk-line);border-radius:var(--ppk-radius-l);background:var(--ppk-panel)}\n'
        + '.ppk-start h2{margin:0 0 8px}.ppk-start p{margin:0;color:var(--ppk-muted)}.ppk-start .ppk-actions{margin:0}\n'
        + '.ppk-notice{margin:14px 0 0;padding:12px 14px;border-radius:var(--ppk-radius-m);background:var(--ppk-tint);color:var(--ppk-ink);font-size:15px}\n'
        + '.ppk-hero-laptop{grid-template-columns:minmax(0,.8fr) minmax(0,1.3fr);gap:24px}\n'
        + '.laptop-hero{margin:0 -28px 0 0;text-align:center}\n'
        + '.laptop-hero a.laptop-link{display:block}\n'
        + '.laptop-hero img{display:block;width:100%;height:auto;filter:drop-shadow(0 16px 22px rgba(40,28,10,.22))}\n'
        + '.laptop-hero figcaption{margin:2px auto 0;max-width:64ch;color:var(--ppk-muted);font-size:13px;line-height:1.5}\n'
        + '@media (max-width:900px){.ppk-hero-laptop{grid-template-columns:1fr;gap:18px}.laptop-hero{margin:0}}\n'
        + '.ppk-open{display:block;margin-top:4px;color:var(--ppk-accent);font-weight:600;text-underline-offset:3px}\n'
        + '@media (max-width:760px){.ppk-start{grid-template-columns:1fr;padding:22px}}\n')


def bento_html(cfg, d, lang):
    t = TEXT[lang]
    b = cfg['bento'][lang]
    v = d['version']
    lines = ''.join(f'<div class="ppk-{k}">{e(x)}</div>' for k, x in b['term'])
    tile = b['tile']
    extra = ''
    if tile.get('live'):
        extra = f'<span class="ppk-live">{e(tile["live"])}</span>'
    elif tile.get('chips'):
        extra = '<div class="ppk-chips">' + ''.join(f'<span>{e(x)}</span>' for x in tile['chips']) + '</div>'
    chips = ''.join(f'<span>{e(x)}</span>' for x in b['features'])
    checks = ''.join(f'<li>{e(x.replace("{v}", v))}</li>' for x in b['checks'])
    return (
        f'<section class="ppk-bento-section ppk-section ppk-reveal">\n'
        f'<h2>{e(t["bento"])}</h2>\n<p class="ppk-sub">{e(t["bento_sub"])}</p>\n<div class="ppk-bento">\n'
        f'<div class="ppk-tile ppk-wide"><h3>{e(t["inst"])}</h3><p>{e(b["inst_text"])}</p>'
        f'<div class="ppk-term" role="group" aria-label="{e(t["inst"])}"><div class="ppk-term-bar"><i></i><i></i><i></i></div>'
        f'<div class="ppk-term-out">{lines}</div></div></div>\n'
        f'<div class="ppk-tile"><h3>{e(tile["title"])}</h3><p>{e(tile["text"])}</p>{extra}</div>\n'
        f'<div class="ppk-tile"><h3>{e(t["feat"])}</h3><div class="ppk-chips">{chips}</div></div>\n'
        f'<div class="ppk-tile ppk-wide"><h3>{e(t["checks"])}</h3><ul class="ppk-checks">{checks}</ul></div>\n'
        f'</div>\n</section>')


def pill_html(d, lang):
    t = TEXT[lang]
    if d['status'] == 'source' or not re.match(r'^\d', d['version']):
        return ''
    url = d.get('release_url') or d['source_url'] + '/blob/main/CHANGELOG.md'
    return (f'<a class="ppk-pill" href="{e(url)}"><span class="ppk-new">{e(t["new"])}</span>'
            f'<span>{e(t["pill"].format(v=d["version"]))}</span> <span class="ppk-more">{e(t["more"])}</span></a>')


def landing_html(cfg, d, lang):
    t = TEXT[lang]
    status = status_label(d, lang)
    ready = d['status'] != 'source' and d.get('release_url')
    os_name = 'macOS' if 'macOS' in d['platform'] else 'Windows'
    action = t['download'] + ' ' + os_name if ready else t['source']
    target = d['release_url'] if ready else d['source_url']
    caption = t[cfg.get('caption', 'shot')]
    shot = cfg['shots'][lang]
    flow = ''.join('<li>' + e(x) + '</li>' for x in cfg['flow'][lang])
    extra = cfg.get('notice', {}).get(lang, '')
    if not ready:
        extra = t['source_note'] + ' ' + extra
    notice = f'<p class="ppk-notice">{e(extra.strip())}</p>' if extra.strip() else ''
    open_link = f'<a class="ppk-open" href="{e(shot)}">{e(t["open_full"])}</a>' if cfg.get('caption') == 'illustration' else ''
    guide = 'Guide-' + lang + '.html'
    title = f'{d["name"]} — {t["guide"]} · {status}'
    return f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="description" content="{e(d['description'][lang])}">
<title>{e(title)}</title>
<link rel="icon" href="{e(cfg['icon'])}">
{head_assets(cfg)}
<link rel="stylesheet" href="presentation.css?v={kit_version(cfg)}-laptop">
</head>
<body class="ppk-page">
<a class="ppk-skip" href="#main">{e(t['skip'])}</a>
{nav_html(cfg, d, lang, 'landing')}
<main class="ppk-shell" id="main">
<div class="ppk-hero ppk-hero-laptop">
<div>
{pill_html(d, lang)}
<h1>{e(d['name'])}</h1>
<p class="ppk-lead">{e(d['description'][lang])}</p>
<span class="ppk-status">{e(status)}</span> <span class="ppk-chip ppk-meta-chip">{e(d['platform'])}</span>
<div class="ppk-actions">
<a class="ppk-btn ppk-btn-primary" href="{e(target)}">{e(action)}</a>
<a class="ppk-btn" href="play-{lang}.html">{e(t['play'])} →</a>
<a class="ppk-btn ppk-btn-gh" href="{e(d['source_url'])}">{e(t['source'])} <span class="ppk-chip"><i class="ppk-dot"></i>{e(cfg['stack'])}</span></a>
<a class="ppk-btn" href="{guide}">{e(t['guide'])} ↗</a>
</div>
<p class="ppk-requirements"><strong>{e(t['requirements'])}</strong>{e(d['requirements'][lang])}</p>
{notice}
</div>
<figure class="laptop-hero">
<a class="laptop-link" href="{e(shot)}"><img src="{e(shot)}" alt="{e(d['name'])} — {e(caption)}" width="1496" height="974" decoding="async"></a>
<figcaption>{e(caption)}{open_link}</figcaption>
</figure>
</div>

{bento_html(cfg, d, lang)}

<section class="ppk-section ppk-process ppk-reveal" aria-labelledby="process-title">
<h2 id="process-title">{e(t['flow'])}</h2>
<ol class="ppk-flow">{flow}</ol>
</section>

<section class="ppk-section ppk-start ppk-reveal">
<div><h2>{e(t['start'])}</h2><p>{e(d['start'][lang])}</p></div>
<div class="ppk-actions"><a class="ppk-btn" href="play-{lang}.html">{e(t['play'])} →</a><a class="ppk-btn" href="{guide}">{e(t['guide'])} →</a></div>
</section>
</main>
{footer_html(d, lang)}
</body>
</html>
'''


def redirect_html(d):
    repo = d['repo']
    return f'''<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script>location.replace('index.html'+location.hash)</script>
<meta http-equiv="refresh" content="0; url=index.html">
<link rel="canonical" href="{PAGES}{repo}/index.html">
<meta name="robots" content="noindex">
<title>{e(d['name'])} — Weiterleitung</title>
</head>
<body>
<p>Diese Seite ist umgezogen: <a href="index.html">{e(d['name'])} — Startseite</a></p>
<p><a href="index-en.html" lang="en" hreflang="en">English</a> · <a href="index-ru.html" lang="ru" hreflang="ru">Русский</a></p>
</body>
</html>
'''


def main():
    cfg, d = load()
    site = site_dir(cfg)
    site.mkdir(exist_ok=True)
    (site / 'theme.css').write_text(theme_css(cfg), encoding='utf-8', newline='\n')
    (site / 'presentation.css').write_text(page_css(cfg), encoding='utf-8', newline='\n')
    for lang in LANGS:
        (site / landing(lang)).write_text(landing_html(cfg, d, lang), encoding='utf-8', newline='\n')
    (site / 'index-de.html').write_text(redirect_html(d), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
    import polish_guides
    polish_guides.main()
    import build_play_pages
    build_play_pages.main()
