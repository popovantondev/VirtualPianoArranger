"""Idempotent shared-kit chrome (header, theme, footer) and responsive polish for existing HTML guides."""
from pathlib import Path
from html.parser import HTMLParser
import html
import json
import re

from build_presentation import ROOT, TEXT, nav_html, footer_html, head_assets, kit_version, load, e

HEAD_START = '<!-- ppk-head:start -->'
HEAD_END = '<!-- ppk-head:end -->'
BODY_START = '<!-- ppk-nav:start -->'
BODY_END = '<!-- ppk-nav:end -->'

CSS = '''/* Guide pages: the shared kit supplies header, footer and tokens (theme.css has the gold palette); assets/guide.css lays out the guide. */
.guide-full-image{display:block;max-width:100%;text-align:center}.guide-full-image img{object-fit:contain}
.guide-note{margin:34px 0 0;padding-top:20px;border-top:1px solid var(--ppk-line);color:var(--ppk-muted);font-size:13px}
.guide-note a{color:var(--ppk-accent)}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto!important}*,*:before,*:after{animation:none!important;transition:none!important}}
'''


def full_images(source, label):
    class Images(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.stack = []
            self.edits = []
            self.lines = source.splitlines(keepends=True)

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'img':
                src = attrs.get('src', '')
                classes = attrs.get('class', '') + ' ' + ' '.join(c for _, c in self.stack)
                if (not any(t == 'a' for t, _ in self.stack)
                        and not re.search(r'(screen-stack|screen-dark|screen-light|preview-dark|preview-light|popup-preview|app-frame)', classes)
                        and re.search(r'(screenshot|guide-(ru|de|en)|interface|demo-|app-(ru|de|en)|main-window|Ui-|control-|recordings-|surface-laptop|filters-)', src, re.I)):
                    line, col = self.getpos()
                    start = sum(map(len, self.lines[:line - 1])) + col
                    tagtext = self.get_starttag_text()
                    replacement = '<a class="guide-full-image" href="' + html.escape(src, quote=True) + '" aria-label="' + label + '">' + tagtext + '</a>'
                    self.edits.append((start, start + len(tagtext), replacement))
            if tag not in ('img', 'input', 'br', 'hr', 'meta', 'link', 'source', 'wbr', 'area', 'base', 'embed', 'param'):
                self.stack.append((tag, attrs.get('class', '')))

        def handle_endtag(self, tag):
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    self.stack = self.stack[:i]
                    break

    p = Images()
    p.feed(source)
    for a, b, text in reversed(p.edits):
        source = source[:a] + text + source[b:]
    return source


def main():
    cfg, d = load()
    site = ROOT / cfg['folder']
    v = kit_version(cfg)
    paths = list(ROOT.glob('Guide-*.html')) + list((ROOT / 'docs').glob('Guide-*.html')) + list((ROOT / 'website').glob('Guide-*.html'))
    for path in paths:
        s = path.read_text(encoding='utf-8')
        lang = path.stem[-2:]
        if lang not in TEXT:
            continue
        t = TEXT[lang]
        # Keep release-summary generator output in sync when removing self links.
        start = s.find('<!-- public-release:start -->')
        end = s.find('<!-- public-release:end -->')
        if start >= 0 and end > start:
            part = s[start:end]
            part = re.sub(r'<a\b[^>]*href="[^"]*Guide-' + lang + r'\.html"[^>]*>.*?</a>', '', part, flags=re.S)
            part = re.sub(r'(<h2) id="section-\d+"', r'\1', part)
            s = s[:start] + part + s[end:]
        # Remove everything earlier runs (and the older guide-polish) added.
        s = re.sub(r'<!-- guide-polish:start -->.*?<!-- guide-polish:end -->\s*', '', s, flags=re.S)
        s = re.sub(r'<link rel="stylesheet" href="guide-polish.css(?:\?[^"]*)?">', '', s)
        s = re.sub(re.escape(HEAD_START) + '.*?' + re.escape(HEAD_END), '', s, flags=re.S)
        s = re.sub(re.escape(BODY_START) + '.*?' + re.escape(BODY_END) + r'\s*', '', s, flags=re.S)
        s = re.sub(r'<footer class="ppk-footer">.*?</footer>\s*', '', s, flags=re.S)
        s = re.sub(r'<meta name="color-scheme"[^>]*>', '', s)
        # The guide's own language bar is replaced by the kit header (same pages, same languages).
        s = re.sub(r'<nav aria-label="Language">.*?</nav>\s*', '', s, count=1, flags=re.S)
        # The old footer text stays as a short note inside the page.
        s = re.sub(r'<footer>(.*?)</footer>', r'<div class="guide-note">\1</div>', s, count=1, flags=re.S)
        # Table of contents from the section headings.
        headings = []
        release_start = s.find('<!-- public-release:start -->')
        release_end = s.find('<!-- public-release:end -->')

        def heading(m):
            if release_start >= 0 and release_start < m.start() < release_end:
                return m[0]
            attrs, title = m.group(1), m.group(2)
            label = html.unescape(re.sub('<[^>]+>', '', title)).strip()
            if not label:
                return m[0]
            existing = re.search(r'\bid="([^"]+)"', attrs)
            key = existing[1] if existing else 'section-' + str(len(headings) + 1)
            if not existing:
                attrs += ' id="' + key + '"'
            headings.append((key, label))
            return '<h2' + attrs + '>' + title + '</h2>'

        s = re.sub(r'<h2\b([^>]*)>(.*?)</h2>', heading, s, flags=re.S)
        s = re.sub(r'<aside class="guide-tools">.*?</aside>\s*', '', s, flags=re.S)
        has_contents = bool(re.search(r'class="[^"]*(?:toc|guide-nav|contents)[^"]*"', s))
        toc = ''
        if len(headings) > 3 and not has_contents:
            toc = ('<aside class="guide-tools"><details><summary>' + t['toc'] + '</summary><ol>'
                   + ''.join('<li><a href="#' + html.escape(k) + '">' + html.escape(lab) + '</a></li>' for k, lab in headings)
                   + '</ol></details></aside>\n')
        # Head: theme script first, kit styles, guide mapping.
        icon = cfg['icon']
        head = (HEAD_START + '<meta name="color-scheme" content="light dark">'
                + ('' if re.search(r'<link rel="icon"', s) else f'<link rel="icon" href="{e(icon)}">')
                + ('' if re.search(r'<meta name="description"', s) else f'<meta name="description" content="{e(d["description"][lang])}">')
                + head_assets(cfg) + f'<link rel="stylesheet" href="guide-kit.css?v={v}">' + HEAD_END)
        s = s.replace('</head>', head + '</head>', 1)
        # Body: class, skip link, kit header.
        nav = (BODY_START + f'<a class="ppk-skip" href="#main-content">{e(t["skip"])}</a>\n' + nav_html(cfg, d, lang, 'guide') + BODY_END + '\n')
        s = re.sub(r'<body\b([^>]*)>\s*', lambda m: _body(m, nav), s, count=1)
        s = re.sub(r'<main(?![^>]*\bid=)', '<main id="main-content"', s, count=1)
        if toc:
            s = s.replace('<main', toc + '<main', 1)
        # Kit footer after the page container.
        s = re.sub(r'</main>\s*</body>', lambda m: '</main>\n' + footer_html(d, lang) + '\n</body>', s, count=1)
        s = full_images(s, t['full'])
        path.write_text(s, encoding='utf-8', newline='\n')
        (path.parent / 'guide-kit.css').write_text(CSS, encoding='utf-8', newline='\n')
        old = path.parent / 'guide-polish.css'
        if old.exists():
            old.unlink()


def _body(m, nav):
    attrs = m.group(1)
    if 'class=' in attrs:
        attrs = re.sub(r'class="([^"]*)"', lambda c: 'class="' + ' '.join(dict.fromkeys((c.group(1) + ' ppk-page ppk-prose').split())) + '"', attrs)
    else:
        attrs += ' class="ppk-page ppk-prose"'
    return '<body' + attrs + '>\n' + nav


if __name__ == '__main__':
    main()
