"""Build play-ru.html, play-de.html and play-en.html from tools/play_template.html.

Static page text lives in TEXT below; dynamic messages live in web/js/i18n.js.
Run again at any time: the output is deterministic.
"""
from pathlib import Path
from html import escape
import re

from build_presentation import footer_html, head_assets, landing, load, nav_html

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ru", "de", "en")

SALAMANDER = "https://archive.org/details/SalamanderGrandPianoV3"
LICENSE = "https://creativecommons.org/licenses/by/3.0/"
MP3_SOURCE = "https://github.com/darosh/samples-piano-mp3"

TEXT = {
    "ru": {
        "title": "Virtual Piano Arranger — пианино в браузере",
        "description": "Пианино на 61 клавишу прямо в браузере: играй мышкой, пальцем или буквами с клавиатуры. Без установки, ничего не отправляется.",
        "skip": "К пианино",
        "menu_label": "Разделы страницы",
        "m_play": "Играть", "m_sheet": "Ноты", "m_midi": "MIDI", "m_demos": "Демо", "m_about": "О программе",
        "tag": "Virtual Piano Arranger · веб-версия",
        "h1_html": "Играй на пианино <em>прямо в браузере</em>",
        "lead": "Мышкой, пальцем или буквами с клавиатуры. Без установки и без регистрации.",
        "play_title": "Пианино",
        "piano_label": "Пианино на 61 клавишу, C2–C7",
        "sound_initial": "Звук загружается…",
        "retry": "Повторить",
        "scroll_left": "Прокрутить пианино влево",
        "scroll_right": "Прокрутить пианино вправо",
        "g_labels": "Подписи", "opt_letters": "Буквы", "opt_notes": "Ноты", "opt_none": "Без подписей",
        "g_layout": "Раскладка букв",
        "g_tune": "Тональность", "tune_down": "Тональность ниже на полутон", "tune_up": "Тональность выше на полутон",
        "g_volume": "Громкость",
        "g_sound": "Звук",
        "g_hit": "Удар", "hit_soft": "Мягкий", "hit_normal": "Обычный", "hit_bright": "Яркий",
        "g_reverb": "Реверберация", "rv_off": "Сухо", "rv_room": "Комната", "rv_hall": "Зал",
        "g_amount": "Количество",
        "g_pedal": "Педаль", "pedal_off": "выкл",
        "hint_keyboard": "Буквы с клавиатуры компьютера играют ноты: Shift — чёрные клавиши, пробел — педаль.",
        "hint_iphone": "Нет звука на iPhone? Выключи беззвучный режим.",
        "pills_label": "Коротко",
        "pill1": "61 клавиша · C2–C7", "pill_midi": "MIDI → буквы", "pill2": "Без установки", "pill3": "Записи настоящего рояля",
        "sheet_title": "Ноты буквами",
        "sheet_lead": "Вставь ноты, записанные буквами, как в программе, и тренируйся: следующая клавиша подсвечивается.",
        "sheet_soon": "Раздел загружается… Ему нужен JavaScript.",
        "midi_title": "MIDI",
        "midi_lead": "Открой файл MIDI, послушай партии и получи буквы для 61 клавиши.",
        "midi_soon": "Раздел загружается… Ему нужен JavaScript.",
        "demos_title": "Демо",
        "demos_lead": "Несколько старинных мелодий: послушать, потренироваться или показать буквами.",
        "demos_soon": "Раздел загружается… Ему нужен JavaScript.",
        "about_title": "PDF и фото нот — только в программе для Windows",
        "about_text": "Распознавание нот по PDF и фотографиям работает только в программе для Windows, и оно пока экспериментальное. В браузере его нет: здесь пианино, буквенные ноты и MIDI.",
        "btn_download": "Скачать для Windows", "btn_guide": "Руководство",
        "attribution_html": (
            f'Записи рояля: <a href="{SALAMANDER}">Salamander Grand Piano V3</a> · Alexander Holm · '
            f'<a href="{LICENSE}">CC BY 3.0</a>. MP3-версии: <a href="{MP3_SOURCE}">darosh/samples-piano-mp3</a>. '
            "Файлы не изменены. Это не означает одобрения автора."
        ),
        "privacy": "Страница работает в браузере: ноты и файлы никуда не отправляются, аналитики и cookie нет.",
        "footer_label": "Ссылки",
        "foot_issue": "Сообщить о проблеме", "foot_home": "О программе",
        "noscript": "Для пианино нужен JavaScript. Включи его в настройках браузера.",
    },
    "de": {
        "title": "Virtual Piano Arranger — Klavier im Browser",
        "description": "Klavier mit 61 Tasten direkt im Browser: Spielen Sie mit Maus, Finger oder den Buchstaben der Tastatur. Ohne Installation, es wird nichts gesendet.",
        "skip": "Zum Klavier",
        "menu_label": "Abschnitte der Seite",
        "m_play": "Spielen", "m_sheet": "Noten", "m_midi": "MIDI", "m_demos": "Demo", "m_about": "Über die App",
        "tag": "Virtual Piano Arranger · Web-Version",
        "h1_html": "Klavier spielen – <em>direkt im Browser</em>",
        "lead": "Mit Maus, Finger oder den Buchstaben der Tastatur. Ohne Installation und ohne Anmeldung.",
        "play_title": "Klavier",
        "piano_label": "Klavier mit 61 Tasten, C2–C7",
        "sound_initial": "Klang wird geladen …",
        "retry": "Erneut versuchen",
        "scroll_left": "Klavier nach links scrollen",
        "scroll_right": "Klavier nach rechts scrollen",
        "g_labels": "Beschriftung", "opt_letters": "Buchstaben", "opt_notes": "Noten", "opt_none": "Ohne Beschriftung",
        "g_layout": "Buchstabenbelegung",
        "g_tune": "Tonart", "tune_down": "Tonart einen Halbton tiefer", "tune_up": "Tonart einen Halbton höher",
        "g_volume": "Lautstärke",
        "g_sound": "Klang",
        "g_hit": "Anschlag", "hit_soft": "Weich", "hit_normal": "Normal", "hit_bright": "Kräftig",
        "g_reverb": "Nachhall", "rv_off": "Trocken", "rv_room": "Raum", "rv_hall": "Saal",
        "g_amount": "Anteil",
        "g_pedal": "Pedal", "pedal_off": "aus",
        "hint_keyboard": "Die Buchstaben der Computertastatur spielen Noten: Shift – schwarze Tasten, Leertaste – Pedal.",
        "hint_iphone": "Kein Ton auf dem iPhone? Schalten Sie den Stumm-Modus aus.",
        "pills_label": "Kurz gesagt",
        "pill1": "61 Tasten · C2–C7", "pill_midi": "MIDI → Buchstaben", "pill2": "Ohne Installation", "pill3": "Aufnahmen eines echten Flügels",
        "sheet_title": "Noten als Buchstaben",
        "sheet_lead": "Fügen Sie Noten in Buchstabenschrift ein, wie in der App, und üben Sie: Die nächste Taste leuchtet auf.",
        "sheet_soon": "Der Bereich wird geladen … Er braucht JavaScript.",
        "midi_title": "MIDI",
        "midi_lead": "Öffnen Sie eine MIDI-Datei, hören Sie die Stimmen an und erhalten Sie Buchstaben für 61 Tasten.",
        "midi_soon": "Der Bereich wird geladen … Er braucht JavaScript.",
        "demos_title": "Demo",
        "demos_lead": "Einige alte Melodien: anhören, üben oder als Buchstaben anzeigen.",
        "demos_soon": "Der Bereich wird geladen … Er braucht JavaScript.",
        "about_title": "PDF und Notenfotos – nur in der Windows-Anwendung",
        "about_text": "Die Erkennung von Noten aus PDF und Fotos gibt es nur in der Windows-Anwendung, und sie ist noch experimentell. Im Browser fehlt sie: Hier gibt es Klavier, Buchstabennoten und MIDI.",
        "btn_download": "Herunterladen für Windows", "btn_guide": "Anleitung",
        "attribution_html": (
            f'Klavieraufnahmen: <a href="{SALAMANDER}">Salamander Grand Piano V3</a> · Alexander Holm · '
            f'<a href="{LICENSE}">CC BY 3.0</a>. MP3-Fassungen: <a href="{MP3_SOURCE}">darosh/samples-piano-mp3</a>. '
            "Die Dateien sind unverändert. Das bedeutet keine Billigung durch den Urheber."
        ),
        "privacy": "Die Seite läuft im Browser: Noten und Dateien werden nirgendwohin gesendet, es gibt weder Analyse noch Cookies.",
        "footer_label": "Links",
        "foot_issue": "Problem melden", "foot_home": "Über die Anwendung",
        "noscript": "Das Klavier braucht JavaScript. Aktivieren Sie es in den Browser-Einstellungen.",
    },
    "en": {
        "title": "Virtual Piano Arranger — piano in your browser",
        "description": "A 61-key piano right in your browser: play with the mouse, your finger or the letters on your keyboard. No installation, nothing is sent anywhere.",
        "skip": "Skip to the piano",
        "menu_label": "Page sections",
        "m_play": "Play", "m_sheet": "Notes", "m_midi": "MIDI", "m_demos": "Demos", "m_about": "About the app",
        "tag": "Virtual Piano Arranger · web version",
        "h1_html": "Play the piano <em>right in your browser</em>",
        "lead": "With the mouse, your finger or the letters on your keyboard. No installation, no sign-up.",
        "play_title": "Piano",
        "piano_label": "61-key piano, C2–C7",
        "sound_initial": "Loading sound…",
        "retry": "Retry",
        "scroll_left": "Scroll the piano left",
        "scroll_right": "Scroll the piano right",
        "g_labels": "Labels", "opt_letters": "Letters", "opt_notes": "Notes", "opt_none": "No labels",
        "g_layout": "Letter layout",
        "g_tune": "Tonality", "tune_down": "Tonality down one semitone", "tune_up": "Tonality up one semitone",
        "g_volume": "Volume",
        "g_sound": "Sound",
        "g_hit": "Touch", "hit_soft": "Soft", "hit_normal": "Normal", "hit_bright": "Bright",
        "g_reverb": "Reverb", "rv_off": "Dry", "rv_room": "Room", "rv_hall": "Hall",
        "g_amount": "Amount",
        "g_pedal": "Pedal", "pedal_off": "off",
        "hint_keyboard": "Letters on your computer keyboard play notes: Shift for black keys, Space for the pedal.",
        "hint_iphone": "No sound on iPhone? Turn off silent mode.",
        "pills_label": "At a glance",
        "pill1": "61 keys · C2–C7", "pill_midi": "MIDI → letters", "pill2": "No installation", "pill3": "Recordings of a real grand piano",
        "sheet_title": "Letter notes",
        "sheet_lead": "Paste notes written as letters, like in the app, and practice: the next key lights up.",
        "sheet_soon": "Loading this section… It needs JavaScript.",
        "midi_title": "MIDI",
        "midi_lead": "Open a MIDI file, listen to its parts and get letters for 61 keys.",
        "midi_soon": "Loading this section… It needs JavaScript.",
        "demos_title": "Demos",
        "demos_lead": "A few old melodies: listen, practice or show the letters.",
        "demos_soon": "Loading this section… It needs JavaScript.",
        "about_title": "PDF and photos of sheet music: Windows app only",
        "about_text": "Reading notes from PDF files and photos works only in the Windows app, and it is still experimental. The browser version does not have it: here you get the piano, letter notes and MIDI.",
        "btn_download": "Download for Windows", "btn_guide": "User guide",
        "attribution_html": (
            f'Piano recordings: <a href="{SALAMANDER}">Salamander Grand Piano V3</a> · Alexander Holm · '
            f'<a href="{LICENSE}">CC BY 3.0</a>. MP3 versions: <a href="{MP3_SOURCE}">darosh/samples-piano-mp3</a>. '
            "The files are unmodified. This does not imply endorsement by the author."
        ),
        "privacy": "The page runs in your browser: notes and files are never sent anywhere, and there is no analytics or cookies.",
        "footer_label": "Links",
        "foot_issue": "Report a problem", "foot_home": "About the application",
        "noscript": "The piano needs JavaScript. Please enable it in your browser settings.",
    },
}

def render(template, values):
    def substitute(match):
        key = match.group(1)
        if key not in values:
            raise KeyError(f"play template uses unknown key: {key}")
        value = values[key]
        return value if key.endswith("_html") else escape(value, quote=True)

    return re.sub(r"\{\{(\w+)\}\}", substitute, template)


def main():
    template = (ROOT / "tools/play_template.html").read_text(encoding="utf-8")
    cfg, release = load()
    for lang in LANGS:
        values = dict(TEXT[lang])
        values.update(
            lang=lang,
            kit_head_html=head_assets(cfg),
            kit_nav_html=nav_html(cfg, release, lang, "play"),
            kit_footer_html=footer_html(release, lang),
            home_href=landing(lang),
            release_url=release["release_url"],
            source_url=release["source_url"],
            feedback_url=release["feedback_url"],
        )
        html = render(template, values)
        # LF line endings on every platform so the output is identical everywhere.
        (ROOT / f"play-{lang}.html").write_bytes(html.replace("\r\n", "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
