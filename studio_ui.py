"""Approved WebEngine shell connected to the existing document handlers.

The hidden Qt controls are a temporary adapter to MainWindow, not a second
browser/UI or parser. Their removal belongs to the planned gradual split.
"""
import json
import re
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot, QSettings,QTimer
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWidgets import (QWidget, QComboBox, QSpinBox, QSlider, QCheckBox,
                              QTextEdit, QLabel, QPushButton, QProgressBar, QMessageBox, QInputDialog)
import main as legacy
from arrangement import arrange, playback_plan, select_pitches, score_clock,playback_time_available
from music_time import rational
from music_time import grouped_events
from omr_quality import result_warnings
from practice import practice_score, fit_registers, MODES
from letter_practice import parse_letters,text_events,render_letters
from text_import import read_notation, EncodingChoiceNeeded, LEGACY_ENCODINGS
from midi_import import read_midi,select_parts
from midi_dialog import choose_midi_parts
from rhythm_view import rhythm_hints,fraction_label,beat_label,display_fraction,timing_tolerance
from docs.design.preview_dark import PreviewWindow, PreviewBridge, LAYOUTS
from offline_piano import PianoBridge
from studio_dialogs import StudioDialogTheme

LANGUAGES = {"ru":"Русский", "en":"English", "de":"Deutsch"}
VIEW_DEFAULTS = {"fontSize":24, "keyLabels":"ru", "piano":True, "follow":True,
                 "volume":65, "speed":100, "layer":8, "reverbPreset":"room",
                 "reverbAmount":20, "reducedMotion":False, "linkLanguageLayout":True,"rhythmHints":True}


class DocumentController(legacy.MainWindow):
    updated = Signal()
    dirtyChanged = Signal(bool)

    def __init__(self, shell, settings):
        self.shell, self.initial_settings = shell, settings
        self.revision = 0
        self.installing_recognition = False
        self.pending_sources=[];self.recognition_index=0;self.recognition_total=0
        self._recognition_authorized=None
        self.practice_mode="normal";self.piano_shift=0;self.link_piano_shift=True
        self._text_source=None;self._text_tokens=[];self._text_error=None
        super().__init__()
        self.setParent(shell, Qt.Widget)
        self.hide()

    def _build_ui(self):
        # Only state-bearing legacy widgets; no website, piano panel or old UI.
        parent=QWidget(self); self.setCentralWidget(parent)
        for name, choices in (("ui_lang",LANGUAGES.values()),("physical_layout",LAYOUTS.values()),("display_layout",LAYOUTS.values())):
            box=QComboBox(parent);box.addItems(list(choices));setattr(self,name,box)
            box.currentTextChanged.connect(self.mark_dirty)
        self.ui_lang.currentTextChanged.connect(self.apply_language)
        for name,default in (("comfort_slider",50),("chord_slider",40)):
            widget=QSlider(Qt.Horizontal,parent);widget.setRange(0,100);widget.setValue(default);setattr(self,name,widget)
        self.transpose_spin=QSpinBox(parent);self.transpose_spin.setRange(-12,12)
        self.pdf_page_spin=QSpinBox(parent);self.pdf_page_spin.setRange(1,1);self.pdf_page_spin.setEnabled(False)
        for name in ("merge_check","spacing_check","always_check","compact_check"):
            setattr(self,name,QCheckBox(parent))
        self.merge_check.setChecked(True)
        for name in ("chord_value","site_transpose_value","status"):
            setattr(self,name,QLabel(parent))
        self.text_conflict=QWidget(parent);self.text_conflict.hide()
        self.output=QTextEdit(parent);self.output.textChanged.connect(self.on_text_edited)
        self.progress=QProgressBar(parent);self.progress.hide()
        self.recognize_btn=QPushButton(parent)
        self.chord_slider.valueChanged.connect(self.on_chords)
        self.transpose_spin.valueChanged.connect(self.on_transpose)
        self.display_layout.currentTextChanged.connect(self.recompute)
        self.spacing_check.toggled.connect(self.recompute)

    def _load_settings(self):
        self.settings=self.initial_settings
        super()._load_settings()

    def apply_language(self):
        self.setWindowTitle(legacy.APP_NAME)

    def mark_dirty(self,*args):
        super().mark_dirty(*args)
        self.dirtyChanged.emit(self._dirty)

    def mark_clean(self):
        super().mark_clean();self.dirtyChanged.emit(False)

    def practice_model(self,mode=None,shift=None,fullness=None):
        return practice_score(self.musical_score,mode or self.practice_mode,self.transpose_spin.value() if shift is None else shift,
                              100-self.chord_slider.value() if fullness is None else fullness)

    def display_model(self,mode=None,shift=None,fullness=None):
        model=self.practice_model(mode,shift,fullness)
        return {**model,'notes':fit_registers(model['notes'],self.transpose_spin.value() if shift is None else shift)} if model else None

    def practice_events(self,mode=None,shift=None,fullness=None):
        if self._text_source is not None:
            if self._text_error:return []
            return text_events(self._text_tokens,mode or self.practice_mode,
                               self.transpose_spin.value() if shift is None else shift,100-self.chord_slider.value() if fullness is None else fullness)
        model=self.display_model(mode,shift,fullness)
        return grouped_events(model) if model is not None else self.events

    def render_practice(self):
        if self._text_source is not None:return self.render_text_practice(self.transpose_spin.value(),100-self.chord_slider.value(),self.display_layout.currentText(),self.practice_mode)
        return legacy.render_events(self.practice_events(),self.transpose_spin.value(),self.display_layout.currentText(),self.spacing_check.isChecked(),self.chord_slider.value() if self.practice_mode=="normal" else 0,range_labels=True)[0]

    @staticmethod
    def letter_labels(layout):
        return {p:legacy.render_key(v['key'],v['shift'],layout) for p,v in legacy.VP_MAP.items()}

    def set_text_source(self,source):
        self._text_source=source;self._text_tokens=[];self._text_error=None
        if source is not None:
            try:self._text_tokens=parse_letters(source['text'],self.letter_labels(source['layout']))
            except ValueError as error:self._text_error=str(error)

    def render_text_practice(self,shift,fullness,layout,mode):
        source=self._text_source
        if self._text_error or (mode=='off' and shift==0 and layout==source['layout']):return source['text']
        events=text_events(self._text_tokens,mode,shift,fullness)
        return render_letters(source['text'],self._text_tokens,events,self.letter_labels(layout),shift)

    def recompute(self):
        if self._restoring or (not self.events and self._text_source is None):return
        self.stop_local_playback()
        try:text=self.render_practice()
        except ValueError:return  # Preview reports unsupported/range errors; keep owner's text.
        previous=self._generated_text;self._generated_text=text
        if self._manual_text is None:self.set_output_text(text)
        elif text!=previous and text!=self._manual_text:self.text_conflict.show()
        self.mark_dirty()

    def offline_plan(self):
        shift=self.transpose_spin.value()
        model=self.display_model()
        plan=playback_plan(model,shift,self.chord_slider.value() if self.practice_mode=="normal" else 0)
        offset=-shift if self.link_piano_shift else self.piano_shift
        display_by_id={n['id']:n['pitch']+shift for n in model['notes']} if model else {}
        source_by_id={n['id']:n['pitch'] for n in self.musical_score['notes']} if self.musical_score else {}
        if self.practice_mode=='off' and self.musical_score and all('midi_channel' in p for p in self.musical_score['parts']):
            from midi_preview import original_plan
            plan=original_plan(self.musical_score)
            for note in plan['notes']:note['midi']+=shift
        for note in plan["notes"]:
            display=display_by_id.get(note['id'],note['midi'])
            if 36<=display<=96:note['displayMidi']=display
            else:note['audioOnly']=True
            note["midi"]=source_by_id.get(note['id'],note['midi']-shift)+shift+offset
        if any(not 21<=n["midi"]<=108 for n in plan["notes"]):
            return {**plan,"notes":[],"error":"range"}
        return plan

    def collect_state(self):
        return {**super().collect_state(),"practice_mode":self.practice_mode,"piano_shift":self.piano_shift,"link_piano_shift":self.link_piano_shift,"text_source":self._text_source}

    def stop_local_playback(self):
        if hasattr(self.shell,"page"):
            self.shell.page.runJavaScript("window.vpaPiano && vpaPiano.panic()")

    def confirm_discard(self):
        if self.installing_recognition and self._recognition_authorized==(self.revision,self.output.toPlainText()):
            return True
        if self.installing_recognition and not self.events and self._manual_text is None:
            return True
        return super().confirm_discard()

    def install_events(self,*args,**kwargs):
        source=self._text_source;self.set_text_source(None)
        result=super().install_events(*args,**kwargs)
        if not result:self.set_text_source(source)
        if result:
            self.revision+=1
            if not self.installing_recognition:
                self.pending_sources=[];self._recognition_authorized=None
                self.recognition_stage="";self.recognition_error=""
        return result

    def open_project(self,path=None):
        result=super().open_project(path)
        if result:
            data=self._loaded_project_data
            self.set_text_source(data.get('text_source'))
            self.practice_mode=data.get("practice_mode","normal")
            self.link_piano_shift=data.get("link_piano_shift",True)
            self.piano_shift=-self.transpose_spin.value() if self.link_piano_shift else data.get("piano_shift",0)
            self._generated_text=self.render_practice()
            if not data.get("transcription_is_manual",False) and data.get("transcription")==data.get("generated_transcription"):
                self._manual_text=None;self.set_output_text(self._generated_text)
            self.mark_clean();self.revision+=1;self.recognition_stage="";self.recognition_error=""
            self.pending_sources=[];self._recognition_authorized=None
        return result

    def open_any(self):
        paths,_=legacy.QFileDialog.getOpenFileNames(self.shell,self.t("open_score"),"","Supported files (*.vpa.json *.mid *.midi *.musicxml *.xml *.txt *.pdf *.png *.jpg *.jpeg *.webp);;All files (*)")
        if not paths:return
        paths=list(dict.fromkeys(paths))
        if len(paths)>50:
            message={"Русский":"Выберите не больше 50 страниц.","English":"Select at most 50 pages.","Deutsch":"Höchstens 50 Seiten wählen."}
            QMessageBox.information(self.shell,legacy.APP_NAME,message[self.ui_lang.currentText()]);return
        suffixes={Path(p).suffix.lower() for p in paths}
        if len(paths)==1 and paths[0].lower().endswith(".vpa.json"):return self.open_project(paths[0])
        if len(paths)==1 and suffixes=={".txt"}:return self.open_text(paths[0])
        if len(paths)==1 and suffixes<= {".mid",".midi"}:return self.open_midi(paths[0])
        if suffixes<= {".xml",".musicxml"}:return self.open_xml(paths)
        if suffixes<= {".pdf",".png",".jpg",".jpeg",".webp"}:return self.open_score(paths)
        message={"Русский":"Выберите один проект/TXT/PDF/MIDI либо страницы одного типа: изображения или MusicXML.","English":"Choose one project/TXT/PDF/MIDI, or pages of one type: images or MusicXML.","Deutsch":"Ein Projekt/TXT/PDF/MIDI oder Seiten eines Typs wählen: Bilder oder MusicXML."}
        QMessageBox.information(self.shell,legacy.APP_NAME,message[self.ui_lang.currentText()])

    def open_midi(self,path):
        if self.busy:return
        try:
            original=read_midi(path)
            ids=choose_midi_parts(original,self.ui_lang.currentText(),self.shell)
            if ids is None:return
            choice=ids if isinstance(ids,dict) else {'ids':ids,'approximate':False}
            score=select_parts(original,choice['ids'],choice['approximate'])
            if not self.install_events(grouped_events(score),path,score):return
            self.musicxml_path=None;self.score_path=str(path);self.practice_mode='off'
            self.recompute()
            self.status.setText({'Русский':'MIDI загружен · звук пианино','English':'MIDI loaded · piano sound','Deutsch':'MIDI geladen · Klavierklang'}[self.ui_lang.currentText()])
            self.show_timing_warnings(score)
            self.updated.emit()
        except (ValueError,OSError) as error:
            QMessageBox.critical(self.shell,legacy.APP_NAME,{'Русский':'Не удалось открыть MIDI','English':'Could not open MIDI','Deutsch':'MIDI konnte nicht geöffnet werden'}[self.ui_lang.currentText()]+'\n'+str(error))

    def open_score(self,paths=None):
        if paths is None:paths,_=legacy.QFileDialog.getOpenFileNames(self,self.t("open_score"),"","Scores (*.png *.jpg *.jpeg *.webp *.pdf)")
        if not paths:return
        paths=list(dict.fromkeys(paths))
        suffixes=[Path(p).suffix.lower() for p in paths]
        if len(paths)>50 or any(s not in (".png",".jpg",".jpeg",".webp",".pdf") for s in suffixes) or (".pdf" in suffixes and len(paths)!=1):
            message={"Русский":"Выберите до 50 изображений или один PDF.","English":"Select up to 50 images or one PDF.","Deutsch":"Bis zu 50 Bilder oder eine PDF wählen."}
            QMessageBox.information(self,legacy.APP_NAME,message[self.ui_lang.currentText()]);return
        if not self.confirm_discard():return
        # Numeric filenames follow page order, not 1, 10, 2. The queue is visible.
        paths.sort(key=lambda p:tuple((1,int(x)) if x.isdigit() else (0,x.casefold()) for x in re.split(r"(\d+)",Path(p).name)))
        self.pending_sources=paths
        self._recognition_authorized=(self.revision,self.output.toPlainText())
        self.configure_pdf_pages(paths[0]);self.recognition_stage="";self.recognition_error=""
        self.recognize()

    def prepare_pdf_pages(self,path):
        document=legacy.QPdfDocument(self)
        try:
            if document.load(path)!=legacy.QPdfDocument.Error.None_ or not 1<=document.pageCount()<=50:
                raise RuntimeError("PDF must contain between 1 and 50 readable pages")
            self._recognition_render=tempfile.TemporaryDirectory(prefix="vpa-pdf-")
            inputs=[]
            for index in range(document.pageCount()):
                points=document.pagePointSize(index)
                if points.width()<=0 or points.height()<=0:raise RuntimeError("PDF page has no usable size")
                size=legacy.QSize(2400,round(2400*points.height()/points.width()))
                if not 1<=size.height()<=12000:raise RuntimeError("PDF page exceeds the rendering limit")
                image=document.render(index,size)
                # PDF backgrounds may be transparent. The child decodes PNG
                # as grayscale, so flatten alpha on WHITE before exporting.
                from pdf_raster import opaque_score_page
                image=opaque_score_page(image)
                target=Path(self._recognition_render.name)/f"page-{index+1:04d}.png"
                if image.isNull() or not image.save(str(target),"PNG"):raise RuntimeError("PDF page could not be rendered")
                inputs.append(str(target))
            return inputs
        finally:document.close();document.deleteLater()

    def recognize(self):
        if self.busy:return
        paths=self.pending_sources or ([self.score_path] if self.score_path and Path(self.score_path).suffix.lower() in (".png",".jpg",".jpeg",".webp",".pdf") else [])
        if not paths:return
        if not self.homr_exe().exists():
            QMessageBox.critical(self,legacy.APP_NAME,self.t("no_homr"));return
        if self._recognition_authorized!=(self.revision,self.output.toPlainText()):
            if not self.confirm_discard():return
            self._recognition_authorized=(self.revision,self.output.toPlainText())
        self.pending_sources=list(paths)
        try:
            inputs=self.prepare_pdf_pages(paths[0]) if Path(paths[0]).suffix.lower()==".pdf" else paths
            self.recognition_index=0;self.recognition_total=len(inputs)
            self.start_recognition(inputs)
        except Exception as error:
            render=getattr(self,"_recognition_render",None)
            if render:render.cleanup();self._recognition_render=None
            self.recognition_failed(str(error))

    def recognition_page(self,index,total):
        self.recognition_index=index;self.recognition_total=total;self.updated.emit()

    def open_text(self,path=None):
        if path is None:path,_=legacy.QFileDialog.getOpenFileName(self,self.t("open_score"),"","Letter notation (*.txt)")
        if not path:return
        try:
            try:text=read_notation(path)
            except EncodingChoiceNeeded:
                prompt={"Русский":"UTF-8 не определён. Выберите кодировку файла (Windows / старый Mac):", "English":"Not UTF-8. Choose the file encoding (Windows / older Mac):", "Deutsch":"Kein UTF-8. Dateikodierung wählen (Windows / älterer Mac):"}
                encoding,ok=QInputDialog.getItem(self.shell,legacy.APP_NAME,prompt[self.ui_lang.currentText()],list(LEGACY_ENCODINGS),0,False)
                if not ok:return
                text=read_notation(path,encoding)
        except (OSError,ValueError) as error:
            QMessageBox.critical(self,legacy.APP_NAME,str(error));return
        if not self.confirm_discard():return
        self.stop_local_playback();self.events=[];self.musical_score=None
        # Cyrillic is unambiguous; Latin Y/Z require the explicitly selected
        # source layout (the display selector), not an encoding-based guess.
        layout='Русская' if re.search('[А-Яа-яЁё]',text) else self.display_layout.currentText()
        self.set_text_source({'text':text,'layout':layout});self.practice_mode='off'
        self._restoring=True
        try:self.display_layout.setCurrentText(layout)
        finally:self._restoring=False
        self.score_path=path;self.musicxml_path=None;self.project_path=None;self.pending_sources=[]
        self._recognition_authorized=None;self._generated_text="";self._manual_text=text
        self.text_conflict.hide();self.set_output_text(text);self.revision+=1
        self.recognition_stage="";self.recognition_error="";self.configure_pdf_pages(path)
        message={"Русский":"TXT: буквы без длительностей. Проигрывание партитуры недоступно; можно играть вручную.","English":"TXT: letters without timing. Score playback unavailable; manual playing is available.","Deutsch":"TXT: Buchstaben ohne Zeitdaten. Keine Partiturwiedergabe; manuelles Spielen ist möglich."}
        self.status.setText(message[self.ui_lang.currentText()]);self.mark_dirty()

    def open_xml(self,paths=None):
        if paths is None:
            path,_=legacy.QFileDialog.getOpenFileName(self,self.t("open_xml"),"","MusicXML (*.musicxml *.xml)")
            paths=[path] if path else []
        if not paths:return
        if len(paths)>1:
            paths=sorted(paths,key=lambda p:tuple((1,int(x)) if x.isdigit() else (0,x.casefold()) for x in re.split(r"(\d+)",Path(p).name)))
            try:
                model=legacy.merge_scores([legacy.read_musicxml(p) for p in paths])
                if self.install_events(grouped_events(model),";".join(paths),model):self.show_timing_warnings(model)
            except Exception as error:QMessageBox.critical(self.shell,legacy.APP_NAME,str(error))
            return
        path=paths[0]
        if Path(path).suffix.lower()==".mxl":
            message={"Русский":"Сжатый MXL пока не поддерживается. Выберите MusicXML/XML.","English":"Compressed MXL is not supported yet. Choose MusicXML/XML.","Deutsch":"Komprimiertes MXL wird noch nicht unterstützt. MusicXML/XML wählen."}
            QMessageBox.information(self,legacy.APP_NAME,message[self.ui_lang.currentText()]);return
        self.load_musicxml(path)

    def recognition_done(self,path,log):
        self.recognition_batch_done([path],log)

    def recognition_batch_done(self,paths,log):
        self.installing_recognition=True
        try:
            scores=[legacy.read_musicxml(path) for path in paths]
            for page,(path,score) in enumerate(zip(paths,scores),1):
                score["warnings"].extend(result_warnings(path,page,self.ui_lang.currentText()))
            model=scores[0] if len(scores)==1 else legacy.merge_scores(scores)
            model["warnings"].append("Recognition is unverified: check pitches, rhythm, ties and tempo against the source.")
            events=grouped_events(model)
            if not events:raise ValueError("No notes were recognised")
            if not self.install_events(events,None,model):
                self.recognition_stage="cancelled";return
            self.score_path=self.pending_sources[0] if self.pending_sources else self.score_path
            self.musicxml_path=None;self.recognition_stage="done"
            self.progress.hide();self.recognize_btn.setEnabled(True)
            self.status.setText(self.t("xml_loaded")+f": {len(events)} · {len(paths)}")
            self.show_timing_warnings(model)
        except Exception as error:self.recognition_failed(str(error))
        finally:self.installing_recognition=False;self.updated.emit()

    def recognition_failed(self,*args):
        super().recognition_failed(*args);self.updated.emit()

    def set_always_on_top(self,*_args):
        pass  # Never reveal this hidden compatibility controller.

    @property
    def busy(self):
        return bool(getattr(self,"_recognition_pending",False) or (self.worker and self.worker.isRunning()))


class StudioBridge(PreviewBridge):
    documentChanged = Signal(str)
    documentDirty = Signal(bool)

    def __init__(self,parent,settings):
        self.controller=DocumentController(parent,settings)
        self.settings=settings
        self.view_preferences=dict(VIEW_DEFAULTS)
        try:
            saved=json.loads(settings.value("studio-view","{}"))
            self._validate_view(saved);self.view_preferences.update(saved)
        except (ValueError,TypeError):pass
        PianoBridge.__init__(self,legacy.VP_MAP,self.controller.offline_score,parent)
        self.plan_provider=self.controller.offline_plan
        self.controller.updated.connect(self.notify)
        self.controller.dirtyChanged.connect(self.documentDirty)

    @staticmethod
    def _validate_view(data):
        if not isinstance(data,dict) or set(data)-set(VIEW_DEFAULTS):raise ValueError("Invalid view")
        for name,values in {"keyLabels":("ru","en","de","none"),"layer":(3,8,13),"reverbPreset":("off","room","hall")}.items():
            if name in data and data[name] not in values:raise ValueError("Invalid view")
        for name,limits in {"fontSize":(16,40),"volume":(0,100),"speed":(50,200),"reverbAmount":(0,100)}.items():
            if name in data and (type(data[name]) is not int or not limits[0]<=data[name]<=limits[1]):raise ValueError("Invalid view")
        for name in ("piano","follow","reducedMotion","linkLanguageLayout","rhythmHints"):
            if name in data and type(data[name]) is not bool:raise ValueError("Invalid view")

    def result(self,shift,fullness,layout,mode=None):
        if type(shift) is not int or not -12<=shift<=12 or type(fullness) is not int or not 0<=fullness<=100 or layout not in LAYOUTS:
            return {"error":"invalid"}
        c=self.controller;mode=mode or c.practice_mode
        if mode not in MODES:return {"error":"invalid"}
        if mode=="off":fullness=100
        score=c.display_model(mode,shift,fullness);tokens=[];selected=outside=shift_keys=conflicts=0
        reduction=100-fullness if mode=='normal' else 0
        plan=playback_plan(score,shift,reduction)
        if mode=='off' and score and all('midi_channel' in p for p in score['parts']):
            from midi_preview import original_plan
            plan=original_plan(score)
        by_attack={};by_rhythm={};originals_by_attack={}
        if score is not None:
            selection=arrange(score,shift,reduction);selected=len(selection["notes"]);outside=len(selection["outside"])
            for note in score['notes']:
                original_group=originals_by_attack.setdefault((note['measure'],float(rational(note['onset']))),{})
                p=note['pitch']+shift;original_group[p]=max(original_group.get(p,-1),note.get('original_pitch',note['pitch']))
            if playback_time_available(score):
                at=score_clock(score)
                # Even an omitted/out-of-range attack has its original time.
                for note in score["notes"]:
                    onset=rational(note["onset"])
                    by_attack[(note["measure"],float(onset))]=at(onset)
                    key=(note["measure"],float(onset))
                    by_rhythm[key]=(onset,max(rational(note['duration']),by_rhythm.get(key,(onset,0))[1]))
        events=(text_events(c._text_tokens,mode,shift,fullness) if c._text_source is not None else c.practice_events(mode,shift,fullness))
        for event in events:
            pitches,rejected=select_pitches(event["notes"],shift,reduction)
            chars=[legacy.render_key(legacy.VP_MAP[p]["key"],legacy.VP_MAP[p]["shift"],LAYOUTS[layout]) for p in pitches]
            conflicts+=len({legacy.VP_MAP[p]['shift'] for p in pitches})>1
            label=legacy.range_label(rejected) if not chars and rejected else "?" if not chars else chars[0] if len(chars)==1 else "["+"".join(chars)+"]"
            originals=originals_by_attack.get((event['measure'],event['time']),{})
            token={"label":label,"pitches":pitches,"originalPitches":[originals.get(p,p-shift) for p in pitches],"measure":event["measure"],"start":by_attack.get((event["measure"],event["time"]))}
            if score is not None and score['exact']:
                onset,duration=by_rhythm[(event['measure'],event['time'])]
                measure=score['measures'][event['measure']-1]
                tolerance=timing_tolerance(score)
                token.update(onset=float(onset),beat=beat_label(onset-rational(measure['onset'])+1,tolerance),duration=fraction_label(display_fraction(duration,tolerance)))
            tokens.append(token)
            shift_keys+=sum(legacy.VP_MAP[p]["shift"] for p in pitches)
            if score is None:selected+=len(pitches);outside+=len(rejected)
        try:text=(c.render_text_practice(shift,fullness,LAYOUTS[layout],mode) if c._text_source is not None else legacy.render_events(events,shift,LAYOUTS[layout],c.spacing_check.isChecked(),reduction,range_labels=True)[0])
        except ValueError as error:return {'error':'range','detail':str(error)}
        return {"text":text,"tokens":tokens,"shift":shift,"fullness":fullness,"layout":layout,
                "rhythm":rhythm_hints(score,score_clock(score) if score and playback_time_available(score) else None),
                "spacing":c.spacing_check.isChecked(),
                "duration":plan["duration"],"playable":bool(plan["notes"]) and "error" not in plan,
                "approximatePlayback":plan.get('approximate',False),
                "practiceMode":mode,"pianoShift":-shift if c.link_piano_shift else c.piano_shift,"linkPianoShift":c.link_piano_shift,
                "original":len(c.musical_score["notes"]) if c.musical_score else sum(len(e['notes']) for e in (c._text_tokens if c._text_source is not None else c.events)),
                "registerMoves":sum(n.get('original_pitch',n['pitch'])!=n['pitch'] for n in score['notes']) if score else 0,
                "untimedText":c._text_source is not None,
                "selected":selected,"outside":outside,"shiftKeys":shift_keys,"modifierConflicts":conflicts}

    @Slot(result=str)
    def document(self):
        c=self.controller
        result=self.result(c.transpose_spin.value(),100-c.chord_slider.value(),next(k for k,v in LAYOUTS.items() if v==c.display_layout.currentText()))
        path=c.project_path or c.musicxml_path or c.score_path
        result.update(visibleText=c.output.toPlainText(),manual=c._manual_text is not None,dirty=c._dirty,
            language=next(k for k,v in LANGUAGES.items() if v==c.ui_lang.currentText()),
            physical=next(k for k,v in LAYOUTS.items() if v==c.physical_layout.currentText()),
            name=Path(path.split(";")[0]).name if path else "",revision=c.revision,
            measures=len({e["measure"] for e in c.events}),status=c.status.text(),warnings=c.status.toolTip(),
            busy=c.busy,recognitionStage=getattr(c,"recognition_stage",""),recognitionError=getattr(c,"recognition_error",""),
            source=bool(c.pending_sources or (c.score_path and Path(c.score_path).suffix.lower() in (".png",".jpg",".jpeg",".webp",".pdf"))),
            sources=[Path(p).name for p in c.pending_sources],recognitionPage=c.recognition_index,recognitionTotal=c.recognition_total,
            pdfMax=c.pdf_page_spin.maximum(),pdfPage=c.pdf_page_spin.value(),
            view=self.view_preferences)
        return json.dumps(result,ensure_ascii=False)

    @Slot()
    def notify(self):
        data=self.document();self.documentChanged.emit(data)
        name=json.loads(data)["name"] or legacy.APP_NAME
        self.parent().setWindowTitle(name+(" *" if self.controller._dirty else "")+" — VPA")

    @Slot(str,result=bool)
    def setText(self,text):
        if len(text)<=2000000 and not self.controller.busy and text!=self.controller.output.toPlainText():
            self.controller.set_output_text(text);self.controller.on_text_edited()
        return self.controller._manual_text is not None

    @Slot(str,str)
    def documentLanguage(self,language,physical):
        if language in LANGUAGES:self.controller.ui_lang.setCurrentText(LANGUAGES[language])
        if physical in LAYOUTS:self.controller.physical_layout.setCurrentText(LAYOUTS[physical])

    @Slot(str,result=str)
    def setView(self,raw):
        try:
            if len(raw)>2048:raise ValueError("Invalid view")
            data=json.loads(raw);self._validate_view(data)
            self.view_preferences.update(data)
            self.settings.setValue("studio-view",json.dumps(self.view_preferences))
            return "{}"
        except (ValueError,TypeError):return '{"error":"invalid"}'

    @Slot(int,int,str,bool,result=str)
    def applyDocument(self,shift,fullness,layout,replace):
        c=self.controller;result=self.result(shift,fullness,layout)
        if c._text_error:return json.dumps({'error':'notation','detail':c._text_error})
        if c.busy:return '{"error":"recognizing"}'
        if "error" in result:return json.dumps(result)
        if c._manual_text is not None and not replace:return '{"error":"manual"}'
        c._restoring=True
        try:
            c.transpose_spin.setValue(shift);c.chord_slider.setValue(100-fullness);c.display_layout.setCurrentText(LAYOUTS[layout])
            c._manual_text=None
            if c.link_piano_shift:c.piano_shift=-shift
        finally:c._restoring=False
        if c.events:c.recompute()
        else:
            c._generated_text=result["text"];c.set_output_text(result["text"]);c.mark_dirty()
        self.notify()
        return json.dumps(result,ensure_ascii=False)

    @Slot(int,int,str,str,result=str)
    def previewPractice(self,shift,fullness,layout,mode):
        if self.controller._text_error:return json.dumps({'error':'notation','detail':self.controller._text_error})
        return json.dumps(self.result(shift,fullness,layout,mode),ensure_ascii=False)

    @Slot(int,str,str,result=str)
    def bestPractice(self,fullness,layout,mode):
        if type(fullness) is not int or not 0<=fullness<=100 or layout not in LAYOUTS or mode not in MODES:return '{"error":"invalid"}'
        if self.controller._text_error:return json.dumps({'error':'notation','detail':self.controller._text_error})
        if self.controller.musical_score is not None or mode=='musical':
            choices=[]
            for value in range(-12,13):
                rating,outside=legacy.score_transposition(self.controller.practice_events(mode,value,fullness),value,100-fullness if mode=='normal' else 0,self.controller.comfort_slider.value())
                model=self.controller.display_model(mode,value,fullness)
                if model:rating+=100*sum(n.get('original_pitch',n['pitch'])>=60 and n.get('original_pitch',n['pitch'])!=n['pitch'] for n in model['notes'])
                choices.append((rating,outside,abs(value),value))
            shift=min(choices)[-1]
            return json.dumps(self.result(shift,fullness,layout,mode),ensure_ascii=False)
        shift,_,_=legacy.find_best_transposition(self.controller.practice_events("off" if mode in ("keyboard","balanced") else mode),100-fullness,self.controller.comfort_slider.value())
        return json.dumps(self.result(shift,fullness,layout,mode),ensure_ascii=False)

    @Slot(int,int,str,str,bool,result=str)
    def applyPractice(self,shift,fullness,layout,mode,replace):
        c=self.controller
        if c._text_error:return json.dumps({'error':'notation','detail':c._text_error})
        if mode not in MODES or "error" in self.result(shift,fullness,layout,mode):return '{"error":"invalid"}'
        if c.busy:return '{"error":"recognizing"}'
        if c._manual_text is not None and not replace:return '{"error":"manual"}'
        c.practice_mode=mode
        if mode=="off":fullness=100
        return self.applyDocument(shift,fullness,layout,replace)

    @Slot(int,bool,result=str)
    def pianoOptions(self,shift,link):
        c=self.controller
        if c.busy or type(link) is not bool or type(shift) is not int or not -12<=shift<=12:return '{"error":"invalid"}'
        c.link_piano_shift=link;c.piano_shift=-c.transpose_spin.value() if link else shift
        c.mark_dirty();self.notify();return self.document()

    @Slot(str,str,int,result=str)
    def documentAction(self,action,text,page):
        c=self.controller
        if action=="cancel":
            c.cancel_recognition();self.notify();return self.document()
        if c.busy:return '{"error":"recognizing"}'
        if action!="close" and (self.parent().recorder.current.active or self.parent().recorder.phase=="exporting"):
            return '{"error":"recording"}'
        self.setText(text)
        if action=="close":
            self.parent().close_synced=True;self.windowActionRequested.emit("close");return "{}"
        handlers={"open":c.open_any,"xml":c.open_xml,"merge":c.open_xml_multi,"source":c.open_score,"project":c.open_project,
                  "save":c.save_project,"txt":c.export_txt,"text":c.open_text,"recognize":c.recognize}
        if action not in handlers:return '{"error":"invalid"}'
        c.pdf_page_spin.setValue(max(1,min(c.pdf_page_spin.maximum(),page)))
        handlers[action]()
        if action=="recognize" and c.worker:
            c.worker.finished.connect(self.notify,Qt.QueuedConnection)
        self.notify()
        return self.document()

    @Slot(int,str,result=str)
    def best(self,fullness,layout):
        if type(fullness) is not int or not 0<=fullness<=100 or layout not in LAYOUTS:return '{"error":"invalid"}'
        shift,_,_=legacy.find_best_transposition(self.controller.events,100-fullness,self.controller.comfort_slider.value())
        return json.dumps(self.result(shift,fullness,layout),ensure_ascii=False)


class StudioWindow(PreviewWindow):
    native_audio_controls=True
    def preview_midi(self,plan,callback):
        self._midi_preview_generation=getattr(self,'_midi_preview_generation',0)+1
        generation=self._midi_preview_generation
        attribute=QWebEngineSettings.PlaybackRequiresUserGesture
        if plan is None:
            self.page.runJavaScript('window.vpaPiano && vpaPiano.panic()')
            previous=getattr(self,'_midi_preview_gesture',None)
            if previous is not None:self.page.settings().setAttribute(attribute,previous);self._midi_preview_gesture=None
            return
        if self.recorder.current.active or self.recorder.phase in ('starting','finishing','exporting'):
            callback('Завершите запись перед прослушиванием MIDI.');return
        if getattr(self,'_midi_preview_gesture',None) is None:
            self._midi_preview_gesture=self.page.settings().testAttribute(attribute)
        # Native Listen button is explicit audio consent, outside Chromium's
        # DOM user-gesture bookkeeping. Restore the setting on stop/dialog exit.
        self.page.settings().setAttribute(attribute,False)
        self.page.runJavaScript('window.vpaMidiPreviewError="";vpaPiano.playPreview('+json.dumps(plan,allow_nan=False)+').catch(e=>window.vpaMidiPreviewError=e.message);true')
        def checked(raw):
            if generation!=self._midi_preview_generation:return
            state=json.loads(raw or '{}')
            if state.get('error') or state.get('context')!='running':callback(state.get('error') or 'Не удалось запустить звук предпрослушивания.')
        def poll():
            if self.closed or generation!=self._midi_preview_generation:return
            try:self.page.runJavaScript('JSON.stringify({error:window.vpaMidiPreviewError,context:vpaPiano.state().context})',checked)
            except RuntimeError:return # owning page was disposed during close
        QTimer.singleShot(500,self,poll)

    def __init__(self,settings=None,recording_folder=None):
        self.close_synced=False
        super().__init__(settings or QSettings(legacy.ORG_NAME,legacy.APP_NAME),recording_folder,StudioBridge)
        self.dialog_theme = StudioDialogTheme(self)
        self.setWindowTitle(legacy.APP_NAME+" · Midnight Studio")

    def closeEvent(self,event):
        if self.closed:
            super().closeEvent(event);return
        c=self.bridge.controller
        if c.busy:
            QMessageBox.information(self,legacy.APP_NAME,c.t("recognizing"));event.ignore();return
        if not self.close_synced:
            event.ignore();self.page.runJavaScript("window.vpaRecording && vpaRecording.requestClose()");return
        if not c.confirm_discard():
            self.close_synced=False;event.ignore();return
        super().closeEvent(event)
        if not self.closed:self.close_synced=False;self.bridge.notify()
        else:
            for key,value in (("ui_language",c.ui_lang.currentText()),("physical_layout",c.physical_layout.currentText()),
                              ("display_layout",c.display_layout.currentText()),("comfort",c.comfort_slider.value()),
                              ("chords",c.chord_slider.value()),("spacing",c.spacing_check.isChecked())):
                self.settings.setValue(key,value)
