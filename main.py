
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from music_time import read_musicxml, grouped_events, merge_scores, rational
from arrangement import simplify_notes, select_pitches, arrange, playback_plan

from PySide6.QtCore import Qt, QSettings, QSize
from PySide6.QtGui import QFont
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QSlider, QSpinBox, QTextEdit,
    QVBoxLayout, QWidget, QGroupBox, QProgressBar
)
from virtual_piano_panel import VirtualPianoPanel
from offline_piano import OfflinePianoPanel
from project_io import read_project, write_project, atomic_write_text
from recognition import HomrWorker, runtime_executable

APP_NAME = "Virtual Piano Arranger"
ORG_NAME = "LocalTools"

PHYSICAL_WHITE_KEYS = [
    "1","2","3","4","5","6","7","8","9","0",
    "Q","W","E","R","T","Y","U","I","O","P",
    "A","S","D","F","G","H","J","K","L",
    "Z","X","C","V","B","N","M"
]

RU_BASE = {
    "1":"1","2":"2","3":"3","4":"4","5":"5","6":"6","7":"7","8":"8","9":"9","0":"0",
    "Q":"й","W":"ц","E":"у","R":"к","T":"е","Y":"н","U":"г","I":"ш","O":"щ","P":"з",
    "A":"ф","S":"ы","D":"в","F":"а","G":"п","H":"р","J":"о","K":"л","L":"д",
    "Z":"я","X":"ч","C":"с","V":"м","B":"и","N":"т","M":"ь"
}
EN_BASE = {k:k.lower() for k in PHYSICAL_WHITE_KEYS}
DE_BASE = EN_BASE.copy()
DE_BASE["Y"] = "z"
DE_BASE["Z"] = "y"

RU_SHIFT_DIGITS = {"1":"!","2":'"',"3":"№","4":";","5":"%","6":":","7":"?","8":"*","9":"(","0":")"}
EN_SHIFT_DIGITS = {"1":"!","2":"@","3":"#","4":"$","5":"%","6":"^","7":"&","8":"*","9":"(","0":")"}
DE_SHIFT_DIGITS = {"1":"!","2":'"',"3":"§","4":"$","5":"%","6":"&","7":"/","8":"(","9":")","0":"="}

LAYOUTS = {
    "Русская": (RU_BASE, RU_SHIFT_DIGITS),
    "English": (EN_BASE, EN_SHIFT_DIGITS),
    "Deutsch": (DE_BASE, DE_SHIFT_DIGITS),
}

I18N = {
    "Русский": {
        "open_score":"Открыть PDF/картинку","recognize":"Распознать","open_xml":"Открыть MusicXML","open_xml_multi":"Объединить MusicXML",
        "open_project":"Открыть проект","save_project":"Сохранить проект","export_txt":"Экспорт TXT",
        "physical":"Физическая раскладка","display":"Раскладка транскрипции","ui_lang":"Язык приложения",
        "comfort":"Точность ↔ удобство","chords":"Полнота аккордов ↔ лёгкая партия",
        "merge":"Объединять почти одновременные ноты","transpose":"Играть","site_transpose":"Virtual Piano",
        "auto_transpose":"Подобрать удобно","auto_transpose_done":"Подобрано: играть {play:+d}; Virtual Piano {site:+d}. Вне диапазона: {outside}.",
        "always":"Поверх остальных окон","compact":"Игровой режим","spacing":"Пробелы между событиями",
        "output":"Транскрипция","ready":"Готово","recognizing":"Распознаю ноты…",
        "xml_loaded":"MusicXML прочитан","no_homr":"Не найден HOMR. Ожидался .venv-omr\\Scripts\\homr.exe рядом с main.py.",
        "pdf_page":"Страница PDF","pdf_render_failed":"Не удалось подготовить страницу PDF для распознавания.",
        "recognition_failed":"Распознавание завершилось с ошибкой.",
        "saved":"Проект сохранён.","loaded":"Проект загружен."
    },
    "English": {
        "open_score":"Open PDF/image","recognize":"Recognize","open_xml":"Open MusicXML","open_xml_multi":"Merge MusicXML",
        "open_project":"Open project","save_project":"Save project","export_txt":"Export TXT",
        "physical":"Physical keyboard layout","display":"Transcription layout","ui_lang":"App language",
        "comfort":"Accuracy ↔ comfort","chords":"Chord fullness ↔ easy part",
        "merge":"Merge near-simultaneous notes","transpose":"Play","site_transpose":"Virtual Piano",
        "auto_transpose":"Find easiest key","auto_transpose_done":"Selected: play {play:+d}; Virtual Piano {site:+d}. Out of range: {outside}.",
        "always":"Always on top","compact":"Play mode","spacing":"Spaces between events",
        "output":"Transcription","ready":"Ready","recognizing":"Recognizing score…",
        "xml_loaded":"MusicXML loaded","no_homr":"HOMR not found. Expected .venv-omr\\Scripts\\homr.exe next to main.py.",
        "pdf_page":"PDF page","pdf_render_failed":"Could not prepare the PDF page for recognition.",
        "recognition_failed":"Recognition failed.","saved":"Project saved.","loaded":"Project loaded."
    },
    "Deutsch": {
        "open_score":"PDF/Bild öffnen","recognize":"Erkennen","open_xml":"MusicXML öffnen","open_xml_multi":"MusicXML zusammenführen",
        "open_project":"Projekt öffnen","save_project":"Projekt speichern","export_txt":"TXT exportieren",
        "physical":"Physische Tastaturbelegung","display":"Transkriptionsbelegung","ui_lang":"App-Sprache",
        "comfort":"Genauigkeit ↔ Spielkomfort","chords":"Akkordfülle ↔ leichte Partie",
        "merge":"Fast gleichzeitige Noten zusammenfassen","transpose":"Spielen","site_transpose":"Virtual Piano",
        "auto_transpose":"Bequeme Tonart finden","auto_transpose_done":"Gewählt: spielen {play:+d}; Virtual Piano {site:+d}. Außerhalb des Bereichs: {outside}.",
        "always":"Immer im Vordergrund","compact":"Spielmodus","spacing":"Leerzeichen zwischen Ereignissen",
        "output":"Transkription","ready":"Bereit","recognizing":"Noten werden erkannt…",
        "xml_loaded":"MusicXML geladen","no_homr":"HOMR nicht gefunden. Erwartet: .venv-omr\\Scripts\\homr.exe neben main.py.",
        "pdf_page":"PDF-Seite","pdf_render_failed":"Die PDF-Seite konnte nicht für die Erkennung vorbereitet werden.",
        "recognition_failed":"Erkennung fehlgeschlagen.","saved":"Projekt gespeichert.","loaded":"Projekt geladen."
    }
}

NOTE_TO_PC = {"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}

def note_name(midi):
    names = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
    return f"{names[midi%12]}{midi//12-1}"

def build_virtual_piano_map():
    mapping = {}
    wi = 0
    for midi in range(36, 97):  # C2..C7 = 61 notes
        pc = midi % 12
        if pc in (0,2,4,5,7,9,11):
            mapping[midi] = {"key":PHYSICAL_WHITE_KEYS[wi], "shift":False}
            wi += 1
        else:
            mapping[midi] = {"key":PHYSICAL_WHITE_KEYS[wi-1], "shift":True}
    return mapping

VP_MAP = build_virtual_piano_map()

def render_key(physical_key, shift, layout_name):
    base, shift_digits = LAYOUTS[layout_name]
    if not shift:
        return base[physical_key]
    if physical_key.isdigit():
        return shift_digits[physical_key]
    return base[physical_key].upper()

def pitch_to_midi(note_el):
    pitch = note_el.find("./pitch")
    if pitch is None:
        return None
    step = pitch.findtext("step")
    octave = pitch.findtext("octave")
    if step is None or octave is None:
        return None
    alter = int(float(pitch.findtext("alter") or 0))
    return (int(octave) + 1) * 12 + NOTE_TO_PC[step] + alter

def parse_musicxml(path):
    """Compatibility API for letter rendering; playback uses individual notes."""
    return grouped_events(read_musicxml(path))

def transpose_event_notes(notes, semitones):
    return [n + semitones for n in notes]


def key_position(midi):
    """Approximate left-to-right position on the 61-key Virtual Piano."""
    info = VP_MAP.get(midi)
    if info is None:
        return None
    return PHYSICAL_WHITE_KEYS.index(info["key"]) + (0.35 if info["shift"] else 0.0)

def score_transposition(events, semitones, chord_value, comfort):
    """
    A transparent playability score; smaller is better.

    Leaving the 61-key range dominates every other preference.  Once all notes
    fit, the score lightly prefers fewer black-key modifiers, narrower chords,
    and smaller jumps between successive events.  It never silently removes a
    note beyond the user's current chord-simplification setting.
    """
    score = 0.0
    outside = 0
    previous_center = None
    for event in events:
        notes = simplify_notes(transpose_event_notes(event["notes"], semitones), chord_value)
        modifiers={m%12 in (1,3,6,8,10) for m in notes if 36<=m<=96}
        if len(modifiers)>1:
            score += 1000  # Prefer a key where the chord is playable on a PC.
        positions = []
        for midi in notes:
            pos = key_position(midi)
            if pos is None:
                outside += 1
                score += 100000
                continue
            positions.append(pos)
            if VP_MAP[midi]["shift"]:
                score += 0.25
        if not positions:
            continue
        if len(positions) > 2:
            score += (len(positions) - 2) * (4 + comfort / 20)
        score += (max(positions) - min(positions)) * (0.1 + comfort / 400)
        center = sum(positions) / len(positions)
        if previous_center is not None:
            score += max(0, abs(center - previous_center) - 7) * (0.15 + comfort / 500)
        previous_center = center
    return score, outside

def find_best_transposition(events, chord_value, comfort):
    """Return the best semitone shift and diagnostics for the current settings."""
    candidates = []
    for semitones in range(-12, 13):
        score, outside = score_transposition(events, semitones, chord_value, comfort)
        # Prefer staying closer to the source when two variants are equivalent.
        candidates.append((score, outside, abs(semitones), semitones))
    best = min(candidates)
    return best[3], best[1], best[0]

def range_label(pitches):
    names=('C','C♯','D','D♯','E','F','F♯','G','G♯','A','A♯','B')
    return '⟨'+' '.join(('↓' if p<36 else '↑')+names[p%12]+str(p//12-1) for p in pitches)+'⟩'


def render_events(events, semitones, layout, spacing, chord_value, range_labels=False):
    by_measure = {}
    warnings = []
    for ev in events:
        notes, rejected = select_pitches(ev["notes"], semitones, chord_value)
        warnings.extend((ev["measure"], p) for p in rejected)
        chars = []
        for midi in notes:
            info = VP_MAP.get(midi)
            if info is None:
                warnings.append((ev["measure"], midi))
                continue
            chars.append(render_key(info["key"], info["shift"], layout))
        if not chars:
            token = range_label(rejected) if range_labels and rejected else "?"
        elif len(chars) == 1:
            token = chars[0]
        else:
            token = "[" + "".join(chars) + "]"
        by_measure.setdefault(ev["measure"], []).append(token)

    lines = []
    for measure in sorted(by_measure):
        sep = " " if spacing else ""
        lines.append(sep.join(by_measure[measure]))
    return "\n".join(lines), warnings

SAFETY_COPY = {
    "Русский": {"unsaved":"Есть несохранённые изменения. Сохранить перед продолжением?", "save_choice":"Сохранить", "discard_choice":"Не сохранять", "cancel_choice":"Отмена", "text_conflict":"Новый вариант готов. Ручные правки сохранены и не меняют ноты проигрывания.", "keep_text":"Оставить правки", "replace_text":"Заменить новым вариантом", "project_error":"Не удалось открыть проект. Текущая работа сохранена в окне.", "write_error":"Не удалось сохранить файл. Изменения остались несохранёнными."},
    "English": {"unsaved":"You have unsaved changes. Save before continuing?", "save_choice":"Save", "discard_choice":"Discard", "cancel_choice":"Cancel", "text_conflict":"A new version is available. Manual edits are preserved and do not change playback notes.", "keep_text":"Keep edits", "replace_text":"Replace with generated text", "project_error":"Could not open the project. Your current work remains in the window.", "write_error":"Could not save the file. Changes remain unsaved."},
    "Deutsch": {"unsaved":"Es gibt ungespeicherte Änderungen. Vor dem Fortfahren speichern?", "save_choice":"Speichern", "discard_choice":"Nicht speichern", "cancel_choice":"Abbrechen", "text_conflict":"Neue Fassung verfügbar. Manuelle Korrekturen bleiben erhalten und ändern die gespielten Noten nicht.", "keep_text":"Korrekturen behalten", "replace_text":"Durch neue Fassung ersetzen", "project_error":"Projekt konnte nicht geöffnet werden. Ihre Arbeit bleibt im Fenster erhalten.", "write_error":"Datei konnte nicht gespeichert werden. Änderungen bleiben ungespeichert."}
}
for _language, _copy in SAFETY_COPY.items():
    I18N[_language].update(_copy)

for _language, _missing, _cancelled in (
    ("Русский", "Комплектный модуль распознавания отсутствует. Нужна папка runtimes/recognition рядом с программой.", "Распознавание отменено. Можно повторить."),
    ("English", "Recognition runtime is missing. The runtimes/recognition folder must accompany the application.", "Recognition cancelled. You can retry."),
    ("Deutsch", "Das Erkennungsmodul fehlt. Der Ordner runtimes/recognition muss bei der Anwendung liegen.", "Erkennung abgebrochen. Sie können erneut starten."),
):
    I18N[_language].update(no_homr=_missing, recognition_cancelled=_cancelled)

for _language, _unavailable, _warnings in (
    ("Русский", "Точное проигрывание недоступно: повторно импортируйте MusicXML или проверьте предупреждения.", "Предупреждений импорта: {count}"),
    ("English", "Exact playback unavailable: reimport MusicXML or review import warnings.", "Import warnings: {count}"),
    ("Deutsch", "Exakte Wiedergabe nicht verfügbar: MusicXML neu importieren oder Warnungen prüfen.", "Importwarnungen: {count}"),
):
    I18N[_language].update(timing_unavailable=_unavailable, timing_warnings=_warnings)

for _language, _merge, _chords, _comfort in (
    ("Русский", "Объединение близких атак пока не реализовано; точные начала нот сохраняются.", "Отбор по высоте: бас и верхняя нота, не распознавание мелодии. Значения до 10 сохраняют все ноты; 100 — две высоты.", "Учитывается при нажатии «Подобрать удобно»; самостоятельно ноты не меняет."),
    ("English", "Near attacks are not merged yet; exact note onsets are retained.", "Pitch-rank selection: bass and top note, not melody detection. Values up to 10 retain all notes; 100 retains two pitches.", "Used by Find easiest key; moving this slider alone does not change notes."),
    ("Deutsch", "Nahe Anschläge werden noch nicht zusammengefasst; exakte Notenanfänge bleiben erhalten.", "Auswahl nach Tonhöhe: Bass und oberste Note, keine Melodieerkennung. Bis 10 alle Noten; 100 zwei Tonhöhen.", "Wirkt bei Bequeme Tonart finden; allein verändert der Regler keine Noten."),
):
    I18N[_language].update(merge_hint=_merge, chords_hint=_chords, comfort_hint=_comfort)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.score_path = None
        self.musicxml_path = None
        self.project_path = None
        self.events = []
        self.musical_score = None
        self.worker = None
        self.project_data = {"version":8}
        self._restoring = True
        self._dirty = False
        self._generated_text = ""
        self._manual_text = None
        self._build_ui()
        self._load_settings()
        self.apply_language()
        self._restoring = False
        self.recompute()

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        top = QHBoxLayout()
        self.open_score_btn = QPushButton()
        self.recognize_btn = QPushButton()
        self.open_xml_btn = QPushButton()
        self.open_xml_multi_btn = QPushButton()
        self.open_project_btn = QPushButton()
        self.save_project_btn = QPushButton()
        self.export_btn = QPushButton()
        for b in [self.open_score_btn,self.recognize_btn,self.open_xml_btn,self.open_xml_multi_btn,self.open_project_btn,self.save_project_btn,self.export_btn]:
            top.addWidget(b)
        outer.addLayout(top)

        row = QHBoxLayout()
        self.ui_lang = QComboBox(); self.ui_lang.addItems(["Русский","English","Deutsch"])
        self.physical_layout = QComboBox(); self.physical_layout.addItems(["Русская","English","Deutsch"])
        self.display_layout = QComboBox(); self.display_layout.addItems(["Русская","English","Deutsch"])
        self.ui_lang_label=QLabel(); self.physical_label=QLabel(); self.display_label=QLabel()
        for lab, box in [(self.ui_lang_label,self.ui_lang),(self.physical_label,self.physical_layout),(self.display_label,self.display_layout)]:
            col=QVBoxLayout(); col.addWidget(lab); col.addWidget(box); row.addLayout(col)
        outer.addLayout(row)

        controls=QGroupBox(); cl=QVBoxLayout(controls)
        self.comfort_label=QLabel()
        cr=QHBoxLayout(); self.comfort_slider=QSlider(Qt.Horizontal); self.comfort_slider.setRange(0,100); self.comfort_slider.setValue(50)
        self.comfort_value=QLabel("50"); cr.addWidget(self.comfort_slider); cr.addWidget(self.comfort_value)
        cl.addWidget(self.comfort_label); cl.addLayout(cr)

        presets=QHBoxLayout()
        for value,text in [(0,"Точно"),(25,"25"),(50,"Баланс"),(75,"75"),(100,"Легко")]:
            b=QPushButton(text); b.clicked.connect(lambda _,v=value:self.comfort_slider.setValue(v)); presets.addWidget(b)
        cl.addLayout(presets)

        self.chords_label=QLabel()
        rr=QHBoxLayout(); self.chord_slider=QSlider(Qt.Horizontal); self.chord_slider.setRange(0,100); self.chord_slider.setValue(40)
        self.chord_value=QLabel("40"); rr.addWidget(self.chord_slider); rr.addWidget(self.chord_value)
        cl.addWidget(self.chords_label); cl.addLayout(rr)

        tr=QHBoxLayout()
        self.transpose_label=QLabel(); self.transpose_spin=QSpinBox(); self.transpose_spin.setRange(-12,12)
        self.auto_transpose_btn=QPushButton()
        self.pdf_page_label=QLabel(); self.pdf_page_spin=QSpinBox(); self.pdf_page_spin.setRange(1,1); self.pdf_page_spin.setEnabled(False)
        self.site_transpose_label=QLabel(); self.site_transpose_value=QLabel("0")
        tr.addWidget(self.transpose_label); tr.addWidget(self.transpose_spin); tr.addWidget(self.auto_transpose_btn); tr.addSpacing(20)
        tr.addWidget(self.site_transpose_label); tr.addWidget(self.site_transpose_value); tr.addStretch()
        tr.addWidget(self.pdf_page_label); tr.addWidget(self.pdf_page_spin)
        cl.addLayout(tr)

        checks=QHBoxLayout()
        self.merge_check=QCheckBox(); self.merge_check.setChecked(True); self.merge_check.setEnabled(False)
        self.spacing_check=QCheckBox()
        self.always_check=QCheckBox()
        self.compact_check=QCheckBox()
        for c in [self.merge_check,self.spacing_check,self.always_check,self.compact_check]:
            checks.addWidget(c)
        cl.addLayout(checks)
        outer.addWidget(controls)

        self.output_label=QLabel(); outer.addWidget(self.output_label)
        self.output=QTextEdit(); self.output.setFont(QFont("Consolas",17)); outer.addWidget(self.output,1)
        self.text_conflict = QWidget()
        conflict_layout = QHBoxLayout(self.text_conflict)
        self.conflict_label = QLabel(); self.conflict_label.setWordWrap(True)
        self.keep_text_btn = QPushButton(); self.replace_text_btn = QPushButton()
        conflict_layout.addWidget(self.conflict_label, 1)
        conflict_layout.addWidget(self.keep_text_btn); conflict_layout.addWidget(self.replace_text_btn)
        outer.addWidget(self.text_conflict); self.text_conflict.hide()
        self.keep_text_btn.clicked.connect(self.text_conflict.hide)
        self.replace_text_btn.clicked.connect(self.replace_generated_text)
        self.output.textChanged.connect(self.on_text_edited)

        self.offline_panel = OfflinePianoPanel(VP_MAP, self.offline_score)
        # Assigned after construction to preserve the panel's existing API.
        if hasattr(self.offline_panel, "bridge"):
            self.offline_panel.bridge.plan_provider = self.offline_plan
        outer.addWidget(self.offline_panel)
        self.piano_panel = VirtualPianoPanel()
        outer.addWidget(self.piano_panel)

        self.progress=QProgressBar(); self.progress.setRange(0,1); self.progress.setValue(0); self.progress.hide()
        outer.addWidget(self.progress)
        self.status=QLabel(); self.status.setWordWrap(True); outer.addWidget(self.status)

        self.open_score_btn.clicked.connect(self.open_score)
        self.recognize_btn.clicked.connect(self.recognize)
        self.open_xml_btn.clicked.connect(self.open_xml)
        self.open_xml_multi_btn.clicked.connect(self.open_xml_multi)
        self.open_project_btn.clicked.connect(self.open_project)
        self.save_project_btn.clicked.connect(self.save_project)
        self.export_btn.clicked.connect(self.export_txt)
        self.ui_lang.currentTextChanged.connect(self.apply_language)
        self.display_layout.currentTextChanged.connect(self.recompute)
        self.spacing_check.toggled.connect(self.recompute)
        self.chord_slider.valueChanged.connect(self.on_chords)
        self.comfort_slider.valueChanged.connect(lambda v:self.comfort_value.setText(str(v)))
        self.transpose_spin.valueChanged.connect(self.on_transpose)
        self.auto_transpose_btn.clicked.connect(self.auto_transpose)
        self.always_check.toggled.connect(self.set_always_on_top)
        self.compact_check.toggled.connect(self.set_compact_mode)
        for box in (self.ui_lang, self.physical_layout, self.display_layout):
            box.currentTextChanged.connect(self.mark_dirty)
        self.comfort_slider.valueChanged.connect(self.mark_dirty)
        self.chord_slider.valueChanged.connect(self.mark_dirty)
        self.transpose_spin.valueChanged.connect(self.mark_dirty)
        self.spacing_check.toggled.connect(self.mark_dirty)
        self.merge_check.toggled.connect(self.mark_dirty)

        self.resize(1050,700)

    def t(self,k):
        return I18N[self.ui_lang.currentText() or "Русский"][k]

    def apply_language(self):
        self.setWindowTitle(APP_NAME + (" *" if self._dirty else ""))
        self.conflict_label.setText(self.t("text_conflict"))
        self.keep_text_btn.setText(self.t("keep_text"))
        self.replace_text_btn.setText(self.t("replace_text"))
        self.piano_panel.set_language(self.ui_lang.currentText())
        self.offline_panel.set_language(self.ui_lang.currentText())
        self.merge_check.setToolTip(self.t("merge_hint"))
        self.chord_slider.setToolTip(self.t("chords_hint"))
        self.comfort_slider.setToolTip(self.t("comfort_hint"))
        for widget,key in [
            (self.open_score_btn,"open_score"),(self.recognize_btn,"recognize"),(self.open_xml_btn,"open_xml"),(self.open_xml_multi_btn,"open_xml_multi"),
            (self.open_project_btn,"open_project"),(self.save_project_btn,"save_project"),(self.export_btn,"export_txt"),
            (self.ui_lang_label,"ui_lang"),(self.physical_label,"physical"),(self.display_label,"display"),
            (self.comfort_label,"comfort"),(self.chords_label,"chords"),(self.transpose_label,"transpose"),
            (self.site_transpose_label,"site_transpose"),(self.auto_transpose_btn,"auto_transpose"),(self.merge_check,"merge"),(self.spacing_check,"spacing"),
            (self.always_check,"always"),(self.compact_check,"compact"),(self.output_label,"output"),(self.pdf_page_label,"pdf_page")
        ]:
            widget.setText(self.t(key))
        if not self.status.text():
            self.status.setText(self.t("ready"))

    def mark_dirty(self, *_args):
        if not self._restoring:
            self._dirty = True
            self.setWindowTitle(APP_NAME + " *")

    def mark_clean(self):
        self._dirty = False
        self.setWindowTitle(APP_NAME)

    def set_output_text(self, text):
        was_blocked = self.output.blockSignals(True)
        try:
            self.output.setPlainText(text)
        finally:
            self.output.blockSignals(was_blocked)

    def on_text_edited(self):
        if self._restoring:
            return
        text = self.output.toPlainText()
        self._manual_text = text if text != self._generated_text else None
        if self._manual_text is None:
            self.text_conflict.hide()
        self.mark_dirty()

    def replace_generated_text(self):
        self._manual_text = None
        self.set_output_text(self._generated_text)
        self.text_conflict.hide()
        self.mark_dirty()

    def confirm_discard(self):
        if not self._dirty:
            return True
        dialog = QMessageBox(self)
        dialog.setWindowTitle(APP_NAME); dialog.setText(self.t("unsaved"))
        save = dialog.addButton(self.t("save_choice"), QMessageBox.AcceptRole)
        discard = dialog.addButton(self.t("discard_choice"), QMessageBox.DestructiveRole)
        cancel = dialog.addButton(self.t("cancel_choice"), QMessageBox.RejectRole)
        dialog.setDefaultButton(cancel); dialog.setEscapeButton(cancel)
        dialog.exec()
        if dialog.clickedButton() is save:
            return self.save_project()
        return dialog.clickedButton() is discard

    def install_events(self, events, path, score=None):
        if not self.confirm_discard():
            return False
        self.stop_local_playback()
        self.events = events; self.musicxml_path = path
        self.project_path = None
        self.musical_score = score
        self._manual_text = None; self._generated_text = ""
        self.text_conflict.hide(); self.set_output_text("")
        self.recompute(); self.mark_dirty()
        return True

    def offline_score(self):
        # Tempo-aware transport is stage 9; this adapter still uses quarter beats.
        if self.musical_score is None or not self.musical_score["exact"]:
            self.status.setText(self.t("timing_unavailable"))
            return []
        selected = arrange(self.musical_score, self.transpose_spin.value(), self.chord_slider.value())
        return [{"time": float(rational(n["onset"])), "duration": float(rational(n["duration"])),
                 "notes": [n["pitch"]]} for n in selected["notes"]]

    def offline_plan(self):
        return playback_plan(self.musical_score, self.transpose_spin.value(), self.chord_slider.value())

    def stop_local_playback(self):
        if hasattr(self.offline_panel, "panic"):
            self.offline_panel.panic()

    def homr_exe(self):
        app_dir = (Path(sys.executable) if getattr(sys, "frozen", False)
                   else Path(__file__)).resolve().parent
        return runtime_executable(app_dir)

    def open_score(self):
        path,_=QFileDialog.getOpenFileName(self,self.t("open_score"),"","Scores (*.png *.jpg *.jpeg *.webp *.pdf);;All files (*)")
        if not path:return False
        if not self.confirm_discard():return False
        self.score_path=path
        self.configure_pdf_pages(path)
        self.status.setText(Path(path).name)
        self.mark_dirty()
        return True

    def configure_pdf_pages(self, path):
        """Enable the page chooser only when the selected score is a PDF."""
        if Path(path).suffix.lower() != ".pdf":
            self.pdf_page_spin.setRange(1, 1)
            self.pdf_page_spin.setEnabled(False)
            return
        document = QPdfDocument(self)
        error = document.load(path)
        pages = document.pageCount() if error == QPdfDocument.Error.None_ else 0
        document.close()
        document.deleteLater()
        self.pdf_page_spin.setRange(1, max(1, pages))
        self.pdf_page_spin.setValue(1)
        self.pdf_page_spin.setEnabled(pages > 0)

    def prepare_pdf_page(self, path):
        """Render the chosen PDF page to a high-resolution temporary PNG for HOMR."""
        document = QPdfDocument(self)
        try:
            if document.load(path) != QPdfDocument.Error.None_:
                raise RuntimeError("PDF could not be opened")
            page_index = self.pdf_page_spin.value() - 1
            if page_index < 0 or page_index >= document.pageCount():
                raise RuntimeError("Selected PDF page does not exist")
            page_size = document.pagePointSize(page_index)
            if page_size.width() <= 0 or page_size.height() <= 0:
                raise RuntimeError("PDF page has no usable size")
            width = 2400
            size = QSize(width, max(1, round(width * page_size.height() / page_size.width())))
            if size.height() > 12000:
                raise RuntimeError("PDF page exceeds the rendering limit")
            image = document.render(page_index, size)
            from pdf_raster import opaque_score_page
            image = opaque_score_page(image)
            if image.isNull():
                raise RuntimeError("PDF page could not be rendered")
        finally:
            document.close()
            document.deleteLater()
        self._recognition_render = tempfile.TemporaryDirectory(prefix="vpa-pdf-")
        output = Path(self._recognition_render.name) / "page.png"
        if not image.save(str(output), "PNG"):
            raise RuntimeError("Rendered PDF image could not be saved")
        return str(output)

    def recognize(self):
        if getattr(self,"_recognition_pending",False) or (self.worker and self.worker.isRunning()):return
        if not self.score_path:
            self.open_score()
            if not self.score_path:return
        homr=self.homr_exe()
        if not homr.exists():
            QMessageBox.critical(self,APP_NAME,self.t("no_homr"))
            return
        recognition_path = self.score_path
        if Path(self.score_path).suffix.lower()==".pdf":
            try:
                recognition_path = self.prepare_pdf_page(self.score_path)
            except Exception as e:
                render=getattr(self,"_recognition_render",None)
                if render:render.cleanup();self._recognition_render=None
                QMessageBox.critical(self,APP_NAME,self.t("pdf_render_failed")+"\n\n"+str(e))
                return
        self.start_recognition(recognition_path)

    def start_recognition(self, recognition_path):
        homr=self.homr_exe()
        if not homr.exists():
            QMessageBox.critical(self,APP_NAME,self.t("no_homr"));return
        self.recognize_btn.setEnabled(False)
        self.progress.setRange(0,0); self.progress.show()
        self.status.setText(self.t("recognizing"))
        self.worker=HomrWorker(str(homr),recognition_path)
        self._recognition_pending=True
        self.recognition_stage="preparing"
        self.recognition_error=""
        self.worker.stage.connect(self.recognition_progress)
        self.worker.done.connect(self.recognition_done)
        if hasattr(self,"recognition_batch_done"):
            self.worker.batchDone.connect(self.recognition_batch_done)
        if hasattr(self,"recognition_page"):
            self.worker.page.connect(self.recognition_page)
        self.worker.failed.connect(self.recognition_failed)
        self.worker.cancelled.connect(self.recognition_cancelled)
        self.worker.finished.connect(self.recognition_finished)
        self.worker.start()

    def recognition_progress(self,stage):
        if getattr(self,"recognition_stage","")=="cancelling" and stage in ("preparing","starting","processing","reading"):return
        self.recognition_stage=stage
        if hasattr(self,"updated"):self.updated.emit()

    def cancel_recognition(self):
        if self.worker and self.worker.isRunning():
            self.recognition_progress("cancelling")
            self.worker.cancel()

    def recognition_cancelled(self):
        self.recognition_stage="cancelled"
        self.progress.hide();self.recognize_btn.setEnabled(True)
        self.status.setText(self.t("recognition_cancelled"))

    def recognition_finished(self):
        self.worker.cleanup()
        render=getattr(self,"_recognition_render",None)
        if render:render.cleanup();self._recognition_render=None
        self._recognition_pending=False
        if hasattr(self,"updated"):self.updated.emit()

    def recognition_done(self,xml_path,log):
        self.progress.hide(); self.recognize_btn.setEnabled(True)
        if self.load_musicxml(xml_path):
            self.recognition_stage="done"
            # The generated XML is job-owned and is removed after installation.
            # Keep the original source as the document identity instead.
            self.musicxml_path=None
            self.status.setText(f"{self.t('xml_loaded')}: {Path(xml_path).name}")
        else:self.recognition_stage="failed"

    def recognition_failed(self,msg):
        self.recognition_stage="failed"
        self.recognition_error=msg[-2000:]
        self.progress.hide(); self.recognize_btn.setEnabled(True)
        QMessageBox.critical(self,APP_NAME,self.t("recognition_failed")+"\n\n"+msg[-2000:])
        self.status.setText(self.t("recognition_failed"))

    def open_xml(self):
        path,_=QFileDialog.getOpenFileName(self,self.t("open_xml"),"","MusicXML (*.musicxml *.xml *.mxl)")
        if path:
            if path.lower().endswith(".mxl"):
                QMessageBox.information(self,APP_NAME,"v0.3: compressed .mxl пока не поддерживается; используй .musicxml/.xml.")
                return
            self.load_musicxml(path)

    def load_musicxml(self,path):
        try:
            score=read_musicxml(path)
            events=grouped_events(score)
            if not self.install_events(events, path, score):return False
            self.status.setText(f"{self.t('xml_loaded')}: {len(self.events)} событий, {Path(path).name}")
            self.show_timing_warnings(score)
            return True
        except Exception as e:
            QMessageBox.critical(self,APP_NAME,f"MusicXML error:\n{e}")
            return False

    def open_xml_multi(self):
        paths,_=QFileDialog.getOpenFileNames(self,self.t("open_xml_multi"),"","MusicXML (*.musicxml *.xml)")
        if not paths:
            return
        try:
            score=merge_scores([read_musicxml(path) for path in paths])
            combined=grouped_events(score)
            measure_offset=len(score["measures"])
            if not combined:
                raise ValueError("В выбранных файлах нет нот")
            if not self.install_events(combined, ";".join(paths), score):return
            self.status.setText(f"{self.t('xml_loaded')}: объединено {len(paths)} страниц, {measure_offset} тактов")
            self.show_timing_warnings(score)
        except Exception as e:
            QMessageBox.critical(self,APP_NAME,f"MusicXML error:\n{e}")

    def show_timing_warnings(self, score):
        if score["warnings"]:
            self.status.setText(self.status.text() + " · " + self.t("timing_warnings").format(count=len(score["warnings"])))
            self.status.setToolTip("\n".join(score["warnings"]))
        else:
            self.status.setToolTip("")
        if score.get('midi_approximate_playback') and not score['exact']:
            self.status.setText(self.status.text()+' · '+{'Русский':'Приблизительное MIDI-воспроизведение','English':'Approximate MIDI playback','Deutsch':'Ungefähre MIDI-Wiedergabe'}[self.ui_lang.currentText()])
        elif not score["exact"]:
            self.status.setText(self.status.text() + " · " + self.t("timing_unavailable"))

    def recompute(self):
        if self._restoring or not self.events:
            return
        self.stop_local_playback()
        text,warnings=render_events(
            self.events,self.transpose_spin.value(),
            self.display_layout.currentText() or "Русская",
            self.spacing_check.isChecked(),
            self.chord_slider.value()
        )
        previous = self._generated_text
        self._generated_text = text
        if self._manual_text is None:
            self.set_output_text(text)
        elif text != previous and text != self._manual_text:
            self.text_conflict.show()
        self.mark_dirty()
        if warnings:
            self.status.setText(f"⚠ За диапазоном 61 клавиши: {len(warnings)} нот. Попробуй транспозицию.")
        else:
            self.status.setText(f"{len(self.events)} событий • {len(set(e['measure'] for e in self.events))} тактов")

    def on_chords(self,v):
        self.chord_value.setText(str(v)); self.recompute()

    def on_transpose(self,v):
        self.site_transpose_value.setText(f"{-v:+d}" if v else "0"); self.recompute()

    def auto_transpose(self):
        if not self.events:
            return
        shift, outside, _ = find_best_transposition(
            self.events, self.chord_slider.value(), self.comfort_slider.value()
        )
        self.transpose_spin.setValue(shift)
        self.status.setText(self.t("auto_transpose_done").format(play=shift, site=-shift, outside=outside))

    def set_always_on_top(self,enabled):
        flags=self.windowFlags()
        self.setWindowFlags(flags | Qt.WindowStaysOnTopHint if enabled else flags & ~Qt.WindowStaysOnTopHint)
        self.show()

    def set_compact_mode(self,enabled):
        self.output.setFont(QFont("Consolas",22 if enabled else 17))
        if enabled:self.resize(max(650,self.width()),380)

    def collect_state(self):
        return {
            "version":9 if self.musical_score is not None else 8,
            **({"schema_version":9,"musical_score":self.musical_score} if self.musical_score is not None else {}),
            "score_path":self.score_path,"musicxml_path":self.musicxml_path,
            "events":self.events,"ui_language":self.ui_lang.currentText(),
            "physical_layout":self.physical_layout.currentText(),"display_layout":self.display_layout.currentText(),
            "comfort":self.comfort_slider.value(),"chord_simplification":self.chord_slider.value(),
            "merge_near_notes":self.merge_check.isChecked(),"spacing":self.spacing_check.isChecked(),
            "transpose_play":self.transpose_spin.value(),"transpose_virtual_piano":-self.transpose_spin.value(),
            "transcription":self.output.toPlainText(),
            "generated_transcription":self._generated_text,
            "transcription_is_manual":self._manual_text is not None
        }

    def save_project(self):
        path,_=QFileDialog.getSaveFileName(self,self.t("save_project"),"","VPA project (*.vpa.json)")
        if not path:return False
        if not path.endswith(".vpa.json"):path+=".vpa.json"
        try:
            write_project(path, self.collect_state())
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, APP_NAME, self.t("write_error") + "\n\n" + str(error))
            return False
        self.mark_clean()
        self.project_path = path
        self.status.setText(self.t("saved"))
        return True

    def open_project(self,path=None):
        if type(path) is bool:path=None  # Legacy QPushButton.clicked passes checked.
        if path is None:path,_=QFileDialog.getOpenFileName(self,self.t("open_project"),"","VPA project (*.vpa.json)")
        if not path:return
        try:
            d = read_project(path)
            # Prepare text before committing any of the current window state.
            generated = render_events(d["events"], d.get("transpose_play",0), d.get("display_layout","Русская"),
                                      d.get("spacing",False), d.get("chord_simplification",40))[0] if d["events"] else ""
        except (OSError, ValueError, TypeError, KeyError) as error:
            QMessageBox.critical(self, APP_NAME, self.t("project_error") + "\n\n" + str(error))
            return False
        if not self.confirm_discard():return False
        self.stop_local_playback()
        self._restoring = True
        try:
            self.score_path=d.get("score_path"); self.musicxml_path=d.get("musicxml_path"); self.events=d["events"]
            self.musical_score=d.get("musical_score")
            self.ui_lang.setCurrentText(d.get("ui_language","Русский"))
            self.physical_layout.setCurrentText(d.get("physical_layout","Русская"))
            self.display_layout.setCurrentText(d.get("display_layout","Русская"))
            self.comfort_slider.setValue(d.get("comfort",50)); self.chord_slider.setValue(d.get("chord_simplification",40))
            self.merge_check.setChecked(d.get("merge_near_notes",True)); self.spacing_check.setChecked(d.get("spacing",False))
            self.transpose_spin.setValue(d.get("transpose_play",0))
            self._generated_text = generated
            text = d.get("transcription", generated)
            self._manual_text = text if d.get("transcription_is_manual", False) or text != generated else None
            self.set_output_text(text); self.text_conflict.hide()
        finally:
            self._restoring = False
        self.mark_clean()
        self.project_path = path
        self.status.setText(self.t("loaded"))
        if self.musical_score is None and self.events:
            self.status.setText(self.status.text() + " · " + self.t("timing_unavailable"))
        elif self.musical_score is not None:
            self.show_timing_warnings(self.musical_score)
        self._loaded_project_data=d
        return True

    def export_txt(self):
        path,_=QFileDialog.getSaveFileName(self,self.t("export_txt"),"","Text (*.txt)")
        if not path:return
        if not path.lower().endswith(".txt"):path+=".txt"
        try:
            atomic_write_text(path, self.output.toPlainText())
        except OSError as error:
            QMessageBox.critical(self, APP_NAME, self.t("write_error") + "\n\n" + str(error))
            return False
        self.status.setText(path)

    def _load_settings(self):
        geom=self.settings.value("geometry",b"")
        if geom:self.restoreGeometry(geom)
        self.ui_lang.setCurrentText(self.settings.value("ui_language","Русский"))
        self.physical_layout.setCurrentText(self.settings.value("physical_layout","Русская"))
        self.display_layout.setCurrentText(self.settings.value("display_layout","Русская"))
        self.comfort_slider.setValue(int(self.settings.value("comfort",50)))
        self.chord_slider.setValue(int(self.settings.value("chords",40)))
        self.spacing_check.setChecked(str(self.settings.value("spacing","false")).lower()=="true")
        self.always_check.setChecked(str(self.settings.value("always","false")).lower()=="true")

    def closeEvent(self,event):
        if getattr(self,"_recognition_pending",False) or (self.worker and self.worker.isRunning()):
            self.cancel_recognition();event.ignore();return
        if not self.confirm_discard():
            event.ignore()
            return
        self.piano_panel.shutdown()
        self.offline_panel.shutdown()
        self.settings.setValue("geometry",self.saveGeometry())
        self.settings.setValue("ui_language",self.ui_lang.currentText())
        self.settings.setValue("physical_layout",self.physical_layout.currentText())
        self.settings.setValue("display_layout",self.display_layout.currentText())
        self.settings.setValue("comfort",self.comfort_slider.value())
        self.settings.setValue("chords",self.chord_slider.value())
        self.settings.setValue("spacing",self.spacing_check.isChecked())
        self.settings.setValue("always",self.always_check.isChecked())
        self.settings.sync()
        event.accept()
        QApplication.instance().quit()

if __name__=="__main__":
    if sys.platform=="win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("popovantondev.VPA")
    app=QApplication(sys.argv)
    from PySide6.QtGui import QIcon
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent/"assets"/"icons"/"vpa.ico")))
    app.setQuitOnLastWindowClosed(True)
    app.setOrganizationName(ORG_NAME); app.setApplicationName(APP_NAME)
    if "--legacy-ui" in sys.argv or "--self-test" in sys.argv:
        w=MainWindow()
    else:
        from studio_ui import StudioWindow
        if "--studio-self-test" in sys.argv:
            if "--test-report" not in sys.argv or sys.argv.index("--test-report")+1>=len(sys.argv):
                sys.exit(2)
            report=Path(sys.argv[sys.argv.index("--test-report")+1]).resolve()
            w=StudioWindow(QSettings(str(report.parent/"settings.ini"),QSettings.IniFormat))
        else:w=StudioWindow()
    if "--self-test" in sys.argv:
        assert w.windowTitle() == APP_NAME
        assert w.open_xml_btn.text()
        sys.exit(0)
    w.show()
    if "--studio-self-test" in sys.argv:
        from packaging_smoke import StudioSmoke
        w.packaging_smoke=StudioSmoke(w,report)
    sys.exit(app.exec())
