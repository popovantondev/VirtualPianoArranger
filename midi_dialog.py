"""Local MIDI part choice; no devices or synthesizer selection."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QListWidget,QListWidgetItem,QDialogButtonBox,QCheckBox,QPushButton,QHBoxLayout,QStyledItemDelegate,QStyle,QStyleOptionViewItem
from midi_preview import preview_plan
from studio_dialogs import suppress_focus_frames


class PartDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        option=QStyleOptionViewItem(option)
        option.state&=~QStyle.State_HasFocus
        super().paint(painter,option,index)


class MidiPartsDialog(QDialog):
    def __init__(self,score,language,parent=None,preview=None):
        super().__init__(parent)
        self.focus_style=suppress_focus_frames(self)
        self.score,self.language,self.preview=score,language,preview
        words={
            'Русский':('Партии MIDI','Выберите одну или несколько партий. Они будут звучать пианино.','Открыть выбранные','Отмена','ударные не поддерживаются'),
            'English':('MIDI parts','Select one or more parts. They will use the piano sound.','Open selected','Cancel','percussion unsupported'),
            'Deutsch':('MIDI-Stimmen','Eine oder mehrere Stimmen wählen. Sie verwenden den Klavierklang.','Auswahl öffnen','Abbrechen','Schlagzeug nicht unterstützt')
        }[language]
        self.setWindowTitle(words[0]);self.setWindowFlag(Qt.FramelessWindowHint);self.setModal(True)
        self.setStyleSheet('QDialog{background:#24262b;color:#eadfc9;border:1px solid #b39766} QLabel,QCheckBox{color:#eadfc9} QCheckBox::indicator{width:16px;height:16px;border:1px solid #b39766;border-radius:3px;background:#14171b} QCheckBox::indicator:checked{background:#b39766} QListWidget{background:#14171b;color:#eadfc9;border:1px solid #625441;padding:4px} QListWidget::item{padding:8px} QListWidget::item:selected{background:#59482e} QPushButton{color:#e8e3da;background:#34363d;border:1px solid #746040;border-radius:6px;padding:8px 16px} QPushButton:default{color:#241b0d;background:#e2bd7e}')
        layout=QVBoxLayout(self);layout.setContentsMargins(24,24,24,24);layout.setSpacing(16)
        heading=QLabel(words[0]);heading.setStyleSheet('font-size:20px;font-weight:bold;color:#f1d4a6');layout.addWidget(heading)
        label=QLabel(words[1]);label.setWordWrap(True);layout.addWidget(label)
        self.parts=QListWidget();self.parts.setObjectName('midi-parts');layout.addWidget(self.parts,1)
        self.parts.setItemDelegate(PartDelegate(self))
        counts={p['id']:[] for p in score['parts']}
        for note in score['notes']:counts[note['part_id']].append(note['pitch'])
        for part in score['parts']:
            pitches=counts[part['id']]
            stats=f"{len(pitches)} {'нот' if language=='Русский' else 'notes' if language=='English' else 'Noten'}"
            if pitches:stats+=f" · MIDI {min(pitches)}–{max(pitches)}"
            item=QListWidgetItem(part['name']+'\n'+stats+(' · '+words[4] if part.get('percussion') else ''))
            item.setData(Qt.UserRole,part['id']);item.setFlags(item.flags()|Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked if part.get('percussion') or not pitches else Qt.Checked)
            if part.get('percussion') or not pitches:item.setFlags(item.flags()&~Qt.ItemIsEnabled)
            self.parts.addItem(item)
        self.approximate=QCheckBox({
            'Русский':'Разрешить приблизительное воспроизведение прочитанных нот',
            'English':'Allow approximate playback of imported notes',
            'Deutsch':'Ungefähre Wiedergabe eingelesener Noten erlauben'}[language])
        self.approximate.setObjectName('midi-approximate-consent')
        self.approximate.setVisible(not score['exact']);layout.addWidget(self.approximate)
        if not score['exact']:
            warning=QLabel({
                'Русский':'Есть неоднозначности MIDI. Без этой галочки воспроизведение останется выключенным. Пропущенные ноты не восстанавливаются; изменение высоты и исходные инструменты не воспроизводятся.',
                'English':'MIDI contains uncertainties. Playback stays disabled without consent. Omitted notes are not restored; pitch bends and original instruments are not reproduced.',
                'Deutsch':'MIDI enthält Unsicherheiten. Ohne Zustimmung bleibt die Wiedergabe aus. Ausgelassene Noten werden nicht ergänzt; Pitch-Bend und Originalinstrumente werden nicht wiedergegeben.'}[language])
            warning.setWordWrap(True);layout.addWidget(warning)
            self.approximate.setToolTip('\n'.join(score['warnings']))
        audition=QHBoxLayout();layout.addLayout(audition)
        titles={'Русский':('Слушать партию','Слушать выбранные','Стоп','Первые 30 секунд звучания · пианино'),
                'English':('Listen to part','Listen to selected','Stop','First 30 seconds of notes · piano'),
                'Deutsch':('Stimme anhören','Auswahl anhören','Stopp','Erste 30 Sekunden mit Noten · Klavier')}[language]
        self.listen_part=QPushButton(titles[0]);self.listen_part.setObjectName('midi-listen-part')
        self.listen_selected=QPushButton(titles[1]);self.listen_selected.setObjectName('midi-listen-selected')
        self.stop_preview=QPushButton(titles[2]);self.stop_preview.setObjectName('midi-preview-stop')
        for button in (self.listen_part,self.listen_selected,self.stop_preview):audition.addWidget(button);button.setEnabled(preview is not None)
        self.preview_status=QLabel(titles[3]);self.preview_status.setWordWrap(True);layout.addWidget(self.preview_status)
        self.listen_part.clicked.connect(lambda:self.audition(True));self.listen_selected.clicked.connect(lambda:self.audition(False))
        self.stop_preview.clicked.connect(self.stop_audition)
        self.parts.currentItemChanged.connect(lambda *_:self.stop_audition())
        self.parts.itemChanged.connect(lambda *_:self.stop_audition())
        self.approximate.toggled.connect(lambda *_:self.stop_audition())
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);layout.addWidget(buttons)
        self.open_button=buttons.button(QDialogButtonBox.Ok);self.open_button.setText(words[2]);self.open_button.setDefault(True)
        buttons.button(QDialogButtonBox.Cancel).setText(words[3])
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject)
        self.parts.itemChanged.connect(lambda:self.open_button.setEnabled(bool(self.selected())))
        self.open_button.setEnabled(bool(self.selected()))
        available=self.screen().availableGeometry()
        self.resize(min(920,available.width()-64),min(760,available.height()-80))
        self.parts.setCurrentRow(next((i for i in range(self.parts.count()) if self.parts.item(i).flags()&Qt.ItemIsEnabled),-1))
    def selected(self):
        return [self.parts.item(i).data(Qt.UserRole) for i in range(self.parts.count()) if self.parts.item(i).checkState()==Qt.Checked]

    def stop_audition(self):
        if self.preview:self.preview(None,lambda _message:None)

    def audition(self,single):
        if self.preview is None:return
        item=self.parts.currentItem()
        ids=[item.data(Qt.UserRole)] if single and item and item.flags()&Qt.ItemIsEnabled else [] if single else self.selected()
        try:
            plan=preview_plan(self.score,ids,self.approximate.isChecked())
        except ValueError:
            self.preview_status.setText({'Русский':'Выберите партию; при неоднозначностях разрешите приблизительное воспроизведение.',
                    'English':'Select a part; allow approximate playback for uncertain MIDI.',
                    'Deutsch':'Stimme wählen; bei Unsicherheiten ungefähre Wiedergabe erlauben.'}[self.language]);return
        self.preview_status.setText({'Русский':'Прослушивание · до 30 секунд · исходная высота · пианино',
                'English':'Audition · up to 30 seconds · original pitches · piano',
                'Deutsch':'Vorschau · bis 30 Sekunden · Originaltonhöhe · Klavier'}[self.language]+(f" · вне сэмплера: {plan['outside']}" if plan['outside'] else ''))
        self.preview(plan,lambda message:self.preview_status.setText(message) if message and self.isVisible() else None)

    def done(self,result):
        self.stop_audition();super().done(result)


def choose_midi_parts(score,language,parent):
    preview=getattr(parent,'preview_midi',None)
    dialog=MidiPartsDialog(score,language,parent,preview)
    return {'ids':dialog.selected(),'approximate':dialog.approximate.isChecked()} if dialog.exec()==QDialog.Accepted else None
