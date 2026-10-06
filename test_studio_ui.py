"""Production UI adapter: temporary projects and existing MusicXML fixtures."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_design_preview as preview_tests
from test_design_preview import Settings, ROOT
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from studio_ui import StudioWindow
import main as legacy
from project_io import read_project, write_project
from test_arrangement import score
from music_time import grouped_events


class StudioTests(unittest.TestCase):
    wait=preview_tests.PreviewTests.wait
    evaluate=preview_tests.PreviewTests.evaluate
    action=preview_tests.PreviewTests.action

    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="vpa-studio-test-")
        self.root=Path(self.temp.name)
        self.settings=Settings()
        self.window=StudioWindow(self.settings,self.root/"current")
        loaded=[]
        self.window.page.loadFinished.connect(loaded.append)
        self.errors=[]
        self.window.page.javaScriptConsoleMessage=lambda _level,msg,_line,_source:self.errors.append(msg)
        self.window.resize(1366,768);self.window.show()
        self.wait(lambda:bool(loaded))
        self.wait(lambda:self.evaluate('Boolean(window.vpaDocument && vpaDocument.active && vpaPreview.state().ready)'))
        self.controller=self.window.bridge.controller

    def tearDown(self):
        self.controller._dirty=False
        self.window.recorder.current.saved=True
        self.window.close_synced=True;self.window.close();self.app.processEvents()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.temp.cleanup()

    def document_action(self,name):
        self.evaluate('vpaDocument.action('+json.dumps(name)+');true')

    def load_xml(self):
        path=ROOT/"page-1.musicxml"
        with patch.object(legacy.QFileDialog,"getOpenFileName",return_value=(str(path),"")):
            self.document_action("xml")
            self.wait(lambda:bool(self.controller.events))
            self.wait(lambda:self.evaluate('vpaPreview.state().applied.text.length>0'))
        return path

    def edit(self,text):
        self.evaluate('document.getElementById("notation").value='+json.dumps(text)+';document.getElementById("notation").dispatchEvent(new Event("input",{bubbles:true}));true')
        self.wait(lambda:self.controller.output.toPlainText()==text)

    def native_click(self,selector):
        # Offscreen Chromium commits hit-test geometry after a tab/modal reflow.
        QTest.qWait(120)
        rect=json.loads(self.evaluate('JSON.stringify(document.querySelector('+json.dumps(selector)+').getBoundingClientRect().toJSON())'))
        target=self.window.view.focusProxy() or self.window.view
        QTest.mouseClick(target,Qt.LeftButton,Qt.NoModifier,QPoint(int(rect["x"]+rect["width"]/2),int(rect["y"]+rect["height"]/2)))
        QTest.qWait(120)

    def test_fullness_in_accompaniment_modes_and_visible_synced_pause_control(self):
        c=self.controller
        source=score([(48,0,1),(60,0,1),(64,0,1),(67,0,1),(52,2,1),(64,2,1),(67,2,1)])
        c.musical_score=copy.deepcopy(source);c.events=grouped_events(source)
        c.revision+=1;c.recompute();self.window.bridge.notify()
        self.wait(lambda:self.evaluate('vpaPreview.state().applied.tokens.length===2'))
        self.evaluate('document.getElementById("notation-settings").open=true;true')
        self.wait(lambda:self.evaluate('!document.getElementById("notation-overlay").hidden'))
        for mode in ('normal','keyboard','balanced','musical','single','upper','off'):
            self.evaluate(f'document.getElementById("practice-mode").value="{mode}";document.getElementById("practice-mode").dispatchEvent(new Event("change"));true')
            self.wait(lambda:self.evaluate('vpaPreview.state().proposal.practiceMode==='+json.dumps(mode)))
            self.assertEqual(self.evaluate('document.getElementById("fullness").disabled'),mode in ('off','single','upper'))
            if mode in ('keyboard','balanced','musical'):
                self.evaluate('document.getElementById("fullness").value=0;document.getElementById("fullness").dispatchEvent(new Event("input"));true')
                self.wait(lambda:self.evaluate('vpaPreview.state().proposal.fullness===0'))
                self.assertEqual(self.evaluate('vpaPreview.state().proposal.selected'),2)
                full=self.window.bridge.result(0,100,'ru',mode)
                low=json.loads(self.window.bridge.applyPractice(0,0,'ru',mode,True))
                self.assertGreater(full['selected'],low['selected'])
                self.assertEqual(c.output.toPlainText(),low['text'])
                plan=c.offline_plan();self.assertEqual(len(plan['notes']),2)
                self.assertEqual([n['midi'] for n in plan['notes']],[67,67])
                self.assertEqual([t['originalPitches'] for t in low['tokens']],[[67],[67]])
                path=self.root/(mode+'.vpa.json');write_project(path,c.collect_state())
                with patch.object(c,'confirm_discard',return_value=True):self.assertTrue(c.open_project(str(path)))
                self.assertEqual(c.offline_plan(),plan);self.assertEqual(c.output.toPlainText(),low['text'])
                self.assertEqual(c.musical_score,source)
        self.evaluate('document.getElementById("notation-settings").open=true;true')
        self.wait(lambda:self.evaluate('!document.getElementById("notation-overlay").hidden'))
        self.assertTrue(self.evaluate('document.getElementById("notation-rests").getClientRects().length>0'))
        self.assertEqual(self.evaluate('document.querySelector(".notation-rest-toggle span").textContent'),'Показывать паузы')
        self.native_click('#notation-rests')
        self.wait(lambda:json.loads(self.settings.value('studio-view'))['rhythmHints'] is False)
        self.assertFalse(self.evaluate('document.getElementById("rhythm-hints").checked'))
        self.assertFalse(self.evaluate('document.getElementById("reading").classList.contains("rhythm-hints")'))
        self.evaluate('document.getElementById("rhythm-hints").checked=true;document.getElementById("rhythm-hints").dispatchEvent(new Event("change"));true')
        self.wait(lambda:json.loads(self.settings.value('studio-view'))['rhythmHints'] is True)
        self.assertTrue(self.evaluate('document.getElementById("notation-rests").checked'))
        self.assertTrue(self.evaluate('(()=>{const panel=document.querySelector("#notation-overlay .notation-controls"),r=panel.getBoundingClientRect();return r.top>=0 && r.bottom<=innerHeight && panel.scrollHeight<=panel.clientHeight+1;})()'))
        self.assertFalse(self.errors,self.errors)

    def test_real_import_merge_and_languages(self):
        self.assertFalse(self.controller.events)
        self.assertFalse(self.evaluate('vpaPreview.state().applied.playable'))
        self.assertEqual(len(self.window.findChildren(type(self.window.view))),1,"no hidden legacy browsers")
        self.load_xml()
        self.assertEqual(len(self.controller.events),158)
        self.assertEqual(self.evaluate('vpaPreview.state().applied.text'),self.controller._generated_text)
        self.assertEqual(self.evaluate('document.getElementById("reading-text").textContent'),self.controller._generated_text)
        self.assertTrue(self.evaluate('vpaPreview.state().applied.playable'))
        self.controller.mark_clean()
        with patch.object(legacy.QFileDialog,"getOpenFileNames",return_value=([str(ROOT/"page-1.musicxml"),str(ROOT/"page-2.musicxml")],"")):
            self.document_action("merge")
            self.wait(lambda:len(self.controller.events)==299)
            self.wait(lambda:self.evaluate('vpaPreview.state().applied.tokens.length===299'))
        self.assertEqual(len(self.controller.musical_score["measures"]),46)
        for lang,label in (("ru","Открыть файл…"),("en","Open file…"),("de","Datei öffnen…")):
            self.evaluate('document.querySelector("[data-lang='+lang+']").click();vpaDocument.dialog("open");true')
            self.assertEqual(self.evaluate('document.querySelector("[data-document-action=open]").textContent'),label)
            self.assertEqual(self.evaluate('document.querySelectorAll("#file-open-actions button:not([hidden])").length'),1)
            self.assertTrue(self.evaluate('document.querySelector(".app").inert'))
            self.document_action("dismiss")
        self.assertFalse(self.window.interceptor.blocked)
        self.assertFalse(self.errors,self.errors)

    def test_midi_parts_cancel_import_rhythm_and_roundtrip(self):
        from test_midi_import import smf
        from midi_import import read_midi
        from midi_dialog import MidiPartsDialog
        path=self.root/'parts.mid'
        path.write_bytes(smf([[(480,b'\x90\x3c\x40'),(480,b'\x80\x3c\0')],[(480,b'\x91\x40\x64'),(480,b'\x81\x40\0')]]))
        original=read_midi(path);dialog=MidiPartsDialog(original,'Русский')
        self.assertEqual(len(dialog.selected()),2)
        dialog.parts.item(0).setCheckState(Qt.Unchecked)
        self.assertEqual(len(dialog.selected()),1)
        dialog.parts.item(1).setCheckState(Qt.Unchecked)
        self.assertFalse(dialog.open_button.isEnabled());dialog.close()
        with patch('studio_ui.choose_midi_parts',return_value=None):self.controller.open_midi(path)
        self.assertFalse(self.controller.events)
        with patch('studio_ui.choose_midi_parts',return_value=[original['parts'][0]['id']]):self.controller.open_midi(path)
        self.wait(lambda:self.evaluate('vpaPreview.state().applied.tokens.length===1'))
        self.assertEqual(len(self.controller.musical_score['notes']),1)
        self.assertTrue(self.evaluate('document.querySelectorAll(".notation-rest").length>0'))
        self.assertFalse(self.evaluate('Boolean(document.querySelector(".notation-token[data-rhythm],.measure-mark"))'))
        self.assertEqual(self.evaluate('document.getElementById("reading-text").textContent'),self.controller._generated_text)
        saved=self.root/'midi.vpa.json';write_project(saved,self.controller.collect_state())
        self.assertEqual(read_project(saved)['musical_score']['notes'],self.controller.musical_score['notes'])
        if os.environ.get('VPA_NEW_EVIDENCE'):
            self.window.resize(1366,1000);self.evaluate('document.getElementById("reading").scrollTop=0;true')
            QTest.qWait(300);self.window.grab().save(str(Path(os.environ['VPA_NEW_EVIDENCE'])/'rhythm-midi.png'))
        self.assertFalse(self.errors,self.errors)

    def test_midi_rest_symbols_no_tick_clutter_or_playback_changes(self):
        from test_midi_import import smf
        from midi_import import read_midi
        path=self.root/'articulation.mid'
        path.write_bytes(smf([[(0,b'\x90\x3c\x40'),(479,b'\x80\x3c\0'),
                              (1,b'\x90\x3e\x40'),(239,b'\x80\x3e\0'),
                              (241,b'\x90\x40\x40'),(480,b'\x80\x40\0')]],fmt=0))
        score=read_midi(path)
        with patch('studio_ui.choose_midi_parts',return_value=[p['id'] for p in score['parts']]):self.controller.open_midi(path)
        self.wait(lambda:self.evaluate('vpaPreview.state().applied.tokens.length===3'))
        original=copy.deepcopy(self.controller.musical_score);plan=self.controller.offline_plan()
        self.assertEqual(self.evaluate('document.querySelectorAll(".notation-rest").length'),1)
        self.assertEqual(self.evaluate('document.querySelectorAll(".notation-rest svg").length'),1)
        self.assertFalse(self.evaluate('Boolean(document.querySelector(".notation-token[data-rhythm],.measure-mark"))'))
        self.assertEqual(self.evaluate('vpaPreview.state().applied.rhythm[0].rests[0].duration'),'1/2')
        self.assertTrue(self.evaluate('document.querySelector(".notation-rest").getAttribute("aria-label").includes("Пауза")'))
        self.assertEqual(self.evaluate('document.getElementById("reading-text").textContent'),self.controller._generated_text)
        self.assertFalse(self.evaluate('document.getElementById("reading-text").textContent.includes("480")'))
        self.assertEqual(self.controller.musical_score,original)
        self.assertEqual(self.controller.offline_plan(),plan)
        self.evaluate('document.getElementById("rhythm-hints").checked=false;document.getElementById("rhythm-hints").dispatchEvent(new Event("change"));true')
        self.assertEqual(self.evaluate('getComputedStyle(document.querySelector(".notation-rest")).display'),'none')
        if os.environ.get('VPA_NEW_EVIDENCE'):
            self.window.resize(1366,1000)
            self.evaluate('document.getElementById("rhythm-hints").checked=true;document.getElementById("rhythm-hints").dispatchEvent(new Event("change"));true')
            self.evaluate('document.getElementById("reading").scrollTop=0;true')
            QTest.qWait(300);self.window.grab().save(str(Path(os.environ['VPA_NEW_EVIDENCE'])/'rest-symbols.png'))
            # Native window grabs can lag the WebEngine compositor; inspect the
            # actual DOM vector separately without a font or GPU dependency.
            from PySide6.QtCore import QByteArray,QRectF
            from PySide6.QtGui import QImage,QPainter,QColor
            from PySide6.QtSvg import QSvgRenderer
            svg=self.evaluate('document.querySelector(".notation-rest svg").outerHTML')
            svg=svg.replace('<svg ','<svg xmlns="http://www.w3.org/2000/svg" fill="#c5a16c" color="#c5a16c" ',1)
            renderer=QSvgRenderer(QByteArray(svg.encode()));self.assertTrue(renderer.isValid())
            image=QImage(100,120,QImage.Format_ARGB32);image.fill(QColor('#181a1f'))
            painter=QPainter(image);renderer.render(painter,QRectF(20,12,60,96));painter.end()
            image.save(str(Path(os.environ['VPA_NEW_EVIDENCE'])/'rest-vector.png'))
        self.assertFalse(self.errors,self.errors)

    def test_clean_centered_rows_pause_clock_and_manual_follow(self):
        source=score([(60,0,1),(64,2,1),(67,2,1),(62,9,1),(65,9,1),(69,9,1)],
                     [{'onset':[0,1],'bpm':[120,1]},{'onset':[2,1],'bpm':[60,1]}])
        source['duration']=[12,1]
        source['measures']=[{'number':i+1,'onset':[i*4,1],'duration':[4,1]} for i in range(3)]
        for note in source['notes']:note['measure']=note['onset'][0]//4+1
        c=self.controller;c.musical_score=copy.deepcopy(source);c.events=grouped_events(source);c.practice_mode='off'
        c.revision+=1;c.recompute();self.window.bridge.notify()
        self.wait(lambda:self.evaluate('vpaPreview.state().applied.tokens.length===3'))
        plan=c.offline_plan()
        self.assertEqual(self.evaluate('document.querySelectorAll(".notation-row").length'),3)
        self.assertFalse(self.evaluate('Boolean(document.querySelector(".measure-mark,[data-rhythm]"))'))
        self.assertEqual(self.evaluate('document.querySelector("[data-t=rhythmHints]").textContent'),'Показывать паузы')
        self.assertEqual(self.evaluate('document.querySelector("#reading-text").textContent'),c._generated_text)
        self.assertEqual(self.evaluate('vpaPreview.state().applied.rhythm[1].rests[0].start'),3)
        self.assertEqual(self.evaluate('vpaPreview.state().applied.rhythm[1].rests[0].end'),7,'rest clock respects the tempo change')
        for width,height,size in ((1366,768,24),(960,680,40),(1920,1080,16)):
            self.window.resize(width,height);self.wait(lambda:self.evaluate('innerWidth==='+str(width)))
            self.evaluate(f'document.getElementById("font-size").value={size};document.getElementById("font-size").dispatchEvent(new Event("input"));true')
            geometry=json.loads(self.evaluate('''JSON.stringify((()=>{
              const pane=document.getElementById('reading'),p=pane.getBoundingClientRect(),centre=p.left+pane.clientWidth/2;
              const offsets=[...document.querySelectorAll('.notation-row')].map(row=>{
                const children=[...row.children].filter(x=>x.getClientRects().length),rects=children.map(x=>x.getBoundingClientRect());
                return Math.abs((Math.min(...rects.map(r=>r.left))+Math.max(...rects.map(r=>r.right)))/2-centre);
              });return {offsets,overflow:pane.scrollWidth>pane.clientWidth+1,atomic:[...document.querySelectorAll('.notation-token')].every(x=>getComputedStyle(x).whiteSpace==='nowrap')};
            })())'''))
            self.assertTrue(all(n<2 for n in geometry['offsets']),geometry)
            self.assertFalse(geometry['overflow'],geometry);self.assertTrue(geometry['atomic'])
        self.window.resize(1366,768)
        self.wait(lambda:self.evaluate('innerWidth===1366'))
        QTest.qWait(250)
        self.evaluate('document.getElementById("tempo").value=50;document.getElementById("tempo").dispatchEvent(new Event("change"));true')
        self.native_click('#transport-toggle')
        self.wait(lambda:self.evaluate('vpaPiano.state().playing'),5)
        self.wait(lambda:self.evaluate('document.querySelector(".notation-rest.current")!==null'),5)
        self.assertEqual(self.evaluate('document.querySelectorAll(".notation-token.current").length'),0)
        self.native_click('#transport-toggle');self.wait(lambda:self.evaluate('vpaPiano.state().paused'))
        QTest.qWait(120);self.assertEqual(self.evaluate('document.querySelectorAll(".notation-rest.current").length'),1)
        self.assertTrue(self.evaluate('(()=>{const span=document.querySelector(".notation-rest.current"),before=span.getBoundingClientRect();span.classList.remove("current");const after=span.getBoundingClientRect();span.classList.add("current");return before.width===after.width && before.height===after.height;})()'),'highlight never changes layout')
        self.evaluate('document.getElementById("rhythm-hints").checked=false;document.getElementById("rhythm-hints").dispatchEvent(new Event("change"));true')
        self.assertEqual(self.evaluate('document.querySelectorAll(".notation-rest.current").length'),0)
        self.assertEqual(self.evaluate('getComputedStyle(document.querySelector(".rest-only")).display'),'none')
        self.evaluate('document.getElementById("rhythm-hints").checked=true;document.getElementById("rhythm-hints").dispatchEvent(new Event("change"));document.getElementById("stop").click();true')
        self.wait(lambda:not self.evaluate('vpaPiano.state().playing || vpaPiano.state().paused'))
        self.assertEqual(self.evaluate('document.querySelectorAll(".notation-rest.current").length'),0)
        self.action('follow-reset')
        self.evaluate('vpaPiano.press(60,"rest-first");vpaPiano.releaseManual();true')
        self.assertEqual(self.evaluate('vpaPreview.state().cursor'),1)
        self.evaluate('vpaPiano.press(64,"rest-next1");vpaPiano.press(67,"rest-next2");vpaPiano.releaseManual();true')
        self.assertEqual(self.evaluate('vpaPreview.state().cursor'),2,'the rest never requires a key')
        self.assertEqual(c.musical_score,source);self.assertEqual(c.offline_plan(),plan)
        self.assertFalse(self.errors,self.errors)

    def test_clean_editor_position_wrap_and_no_guessed_text_rests(self):
        self.load_xml()
        self.evaluate('document.getElementById("follow").checked=false;document.getElementById("follow").dispatchEvent(new Event("change"));document.getElementById("reading").scrollTop=330;true')
        top=self.evaluate('document.getElementById("reading").scrollTop');cursor=self.evaluate('vpaPreview.state().cursor')
        for _ in range(3):
            self.action('edit');self.assertEqual(self.evaluate('getComputedStyle(document.getElementById("notation")).textAlign'),'center')
            self.assertGreater(self.evaluate('document.getElementById("notation").selectionStart'),0)
            self.action('edit');self.assertAlmostEqual(self.evaluate('document.getElementById("reading").scrollTop'),top,delta=1)
            self.assertEqual(self.evaluate('vpaPreview.state().cursor'),cursor)
        self.action('edit')
        text='\n'.join(['[йцукен] а в г д е з и к л м н о п р с т у ф х ц ч ш щ ы']*30)
        self.edit(text)
        self.evaluate('document.getElementById("notation").setSelectionRange(350,356);document.getElementById("notation").scrollTop=240;true')
        self.action('edit')
        self.assertFalse(self.evaluate('Boolean(document.querySelector(".notation-rest,.measure-mark,[data-rhythm]"))'))
        self.assertEqual(self.evaluate('document.getElementById("reading-text").textContent'),text)
        self.assertGreater(self.evaluate('document.getElementById("reading").scrollTop'),0)
        self.action('edit')
        self.assertEqual(self.evaluate('document.getElementById("notation").selectionStart'),350)
        self.assertEqual(self.evaluate('document.getElementById("notation").selectionEnd'),356)
        self.action('edit')
        previous=self.evaluate('document.getElementById("reading").scrollTop')
        self.action('edit')
        self.evaluate('document.getElementById("notation").setSelectionRange(0,0);document.getElementById("notation").scrollTop=0;true')
        self.action('edit')
        self.assertLess(self.evaluate('document.getElementById("reading").scrollTop'),previous,'explicit editor navigation must not be discarded')
        self.window.resize(960,680);self.wait(lambda:self.evaluate('innerWidth===960'))
        self.evaluate('document.getElementById("font-size").value=40;document.getElementById("font-size").dispatchEvent(new Event("input"));true')
        self.assertTrue(self.evaluate('[...document.querySelectorAll(".notation-token")].filter(x=>x.textContent.startsWith("[")).every(x=>x.getClientRects().length===1 && getComputedStyle(x).whiteSpace==="nowrap")'))
        self.assertTrue(self.evaluate('(()=>{const nodes=[...document.querySelector(".notation-row").children];return Math.max(...nodes.map(x=>x.getBoundingClientRect().top))-Math.min(...nodes.map(x=>x.getBoundingClientRect().top))>10;})()'),'long rows actually wrap between tokens')
        self.assertFalse(self.evaluate('document.getElementById("reading").scrollWidth>document.getElementById("reading").clientWidth+1'))
        self.assertFalse(self.errors,self.errors)

    @unittest.skipUnless(os.environ.get('VPA_EXPERIENCE_MIDI'),'owner MIDI opt-in')
    def test_experience_clean_notation_readonly(self):
        from midi_import import read_midi
        path=Path(os.environ['VPA_EXPERIENCE_MIDI']);original=read_midi(path)
        with patch('studio_ui.choose_midi_parts',return_value=[p['id'] for p in original['parts'] if not p.get('percussion')]):self.controller.open_midi(path)
        self.wait(lambda:self.evaluate('vpaPreview.state().applied.tokens.length>0'))
        before=copy.deepcopy(self.controller.musical_score);plan=self.controller.offline_plan()
        self.assertEqual(self.evaluate('document.querySelectorAll(".notation-row").length'),113)
        self.assertEqual(self.evaluate('document.querySelectorAll(".notation-rest,[data-rhythm],.measure-mark").length'),0)
        self.assertEqual(self.evaluate('document.getElementById("reading-text").textContent'),self.controller._generated_text)
        self.action('edit');self.action('edit')
        self.assertEqual(self.controller.musical_score,before);self.assertEqual(self.controller.offline_plan(),plan)
        self.assertEqual(self.controller.musical_score['notes'],original['notes'])
        self.assertFalse(self.errors,self.errors)

    def test_midi_approximate_consent_plan_and_project(self):
        from test_midi_import import smf
        from midi_import import read_midi
        from midi_dialog import MidiPartsDialog
        path=self.root/'uncertain.mid'
        path.write_bytes(smf([[(0,b'\x90\x3c\x40'),(0,b'\xe0\x01\x40'),(480,b'\x80\x3c\0')]],fmt=0))
        source=read_midi(path);ids=[p['id'] for p in source['parts']]
        dialog=MidiPartsDialog(source,'Русский')
        self.assertFalse(dialog.approximate.isChecked());self.assertIn('1 нот',dialog.parts.item(0).text());dialog.close()
        with patch('studio_ui.choose_midi_parts',return_value={'ids':ids,'approximate':True}):self.controller.open_midi(path)
        self.wait(lambda:self.evaluate('Boolean(vpaPreview.state().applied.approximatePlayback)'))
        self.assertFalse(self.controller.musical_score['exact'])
        self.assertTrue(self.controller.offline_plan()['approximate'])
        self.assertTrue(self.evaluate('vpaPreview.state().applied.playable'))
        self.assertIn('Приблизительное',self.evaluate('document.querySelector(".editor-foot span:last-child").textContent'))
        saved=self.root/'approximate.vpa.json';write_project(saved,self.controller.collect_state())
        self.assertTrue(read_project(saved)['musical_score']['midi_approximate_playback'])
        self.assertFalse(self.errors,self.errors)

    def test_midi_original_bass_and_explicit_keyboard_adaptation(self):
        from test_midi_import import smf
        from midi_import import read_midi
        path=self.root/'low-bass.mid'
        path.write_bytes(smf([[(480,b'\x90\x1d\x64'),(480,b'\x80\x1d\0')],[(480,b'\x91\x3c\x64'),(0,b'\x91\x3d\x64'),(480,b'\x81\x3c\0'),(0,b'\x81\x3d\0')]]))
        source=read_midi(path)
        with patch('studio_ui.choose_midi_parts',return_value=[p['id'] for p in source['parts']]):self.controller.open_midi(path)
        self.wait(lambda:self.evaluate('!document.getElementById("keyboard-help").hidden'))
        before=copy.deepcopy(self.controller.musical_score)
        plan=self.controller.offline_plan()
        bass=next(n for n in plan['notes'] if n['midi']==29)
        self.assertEqual(bass['displayMidi'],41);self.assertEqual(bass['start'],0.5)
        self.assertEqual(len(plan['notes']),3)
        self.assertNotIn('error',json.loads(self.window.bridge.plan()))
        from midi_import import select_parts
        bass_source=select_parts(source,[source['parts'][0]['id']])
        saved=self.controller.musical_score
        self.controller.musical_score=bass_source
        self.assertTrue(self.window.bridge.result(0,100,'ru','off')['playable'])
        self.controller.musical_score=saved
        self.evaluate('document.querySelector("#keyboard-help button").click();true')
        self.wait(lambda:self.evaluate('vpaPreview.state().proposal?.practiceMode==="musical"'))
        proposal=self.evaluate('JSON.stringify(vpaPreview.state().proposal)')
        result=json.loads(proposal)
        self.assertEqual(result['outside'],0);self.assertEqual(result['modifierConflicts'],0)
        self.assertNotIn('?',result['text'])
        self.assertEqual(self.controller.practice_mode,'off')
        self.assertEqual(self.controller.musical_score,before)
        self.evaluate('vpaPreview.apply();true')
        self.wait(lambda:self.controller.practice_mode=='musical')
        self.assertEqual(self.controller.musical_score,before)
        self.assertFalse(self.errors,self.errors)

    def test_register_display_preserves_octaves_in_playback_and_manual_follow(self):
        from practice import MODES
        source=score([(24,0,1),(84,0,1),(28,1,1),(94,1,1)])
        for n in source['notes']:n['voice']='bass' if n['pitch']<60 else 'melody'
        c=self.controller;c.musical_score=copy.deepcopy(source);c.events=grouped_events(source)
        original={n['id']:n['pitch'] for n in source['notes']}
        for mode in MODES:
            for shift in (-9,0,7,12):
                result=self.window.bridge.result(shift,100,'ru',mode)
                self.assertEqual(result['outside'],0,(mode,shift))
                self.assertNotIn('?',result['text'])
                c.practice_mode=mode;c.transpose_spin.setValue(shift)
                plan=c.offline_plan()
                for n in plan['notes']:self.assertEqual(n['midi'],original[n['id']],(mode,shift,n))
        c.practice_mode='keyboard';c.transpose_spin.setValue(7);c.revision+=1;c.recompute();self.window.bridge.notify()
        c.link_piano_shift=False;c.piano_shift=2
        for n in c.offline_plan()['notes']:self.assertEqual(n['midi'],original[n['id']]+9)
        c.link_piano_shift=True;c.piano_shift=-7
        self.wait(lambda:self.evaluate('vpaPreview.state().applied.shift===7'))
        self.action('follow-reset')
        self.evaluate('vpaPiano.press(79,"octave-melody");true')
        self.wait(lambda:self.evaluate('vpaPiano.state().manualPitches.includes(84)'))
        self.evaluate('vpaPiano.press(43,"octave-bass");true')
        self.wait(lambda:self.evaluate('vpaPiano.state().manualPitches.includes(24)'))
        self.evaluate('vpaPiano.releaseManual();true')
        self.assertEqual(c.musical_score,source)
        self.evaluate('const summary=document.querySelector("#notation-settings summary");summary.focus();summary.dispatchEvent(new KeyboardEvent("keydown",{code:"KeyA",key:"a",bubbles:true}));true')
        self.assertEqual(self.evaluate('getComputedStyle(document.querySelector("#notation-settings summary")).outlineStyle'),'none')
        if os.environ.get('VPA_REG_EVIDENCE'):
            self.window.grab().save(str(Path(os.environ['VPA_REG_EVIDENCE'])/'summary-no-frame.png'))
        wide=score([(24,0,1),(100,1,1)])
        for n in wide['notes']:n['voice']='wide'
        c.musical_score=wide
        unresolved=self.window.bridge.result(0,100,'ru','off')
        self.assertNotIn('?',unresolved['text'])
        self.assertIn('↓C1',unresolved['text']);self.assertIn('↑E7',unresolved['text'])
        self.assertFalse(self.errors,self.errors)

    def test_native_midi_audition_emits_pcm_before_import_and_cancel_stops(self):
        from test_midi_import import smf
        from midi_import import read_midi
        from midi_dialog import MidiPartsDialog
        path=self.root/'audition.mid'
        path.write_bytes(smf([[(0,b'\x90\x1e\x64'),(9600,b'\x80\x1e\0')],[(0,b'\x91\x40\x40'),(9600,b'\x81\x40\0')]]))
        source=read_midi(path);before=copy.deepcopy(self.controller.collect_state())
        dialog=MidiPartsDialog(source,'Русский',self.window,self.window.preview_midi)
        dialog.show();QTest.qWait(100)
        self.evaluate('(()=>{const play=vpaPiano.playPreview;vpaPiano.playPreview=p=>{window.receivedMidiPreview=p;return play(p)};return true})()')
        self.evaluate('window.midiAnalyser=vpaPiano.audioOutput().context.createAnalyser();midiAnalyser.fftSize=4096;vpaPiano.audioOutput().output.connect(midiAnalyser);true')
        QTest.mouseClick(dialog.listen_part,Qt.LeftButton)
        try:self.wait(lambda:self.evaluate('vpaPiano.state().preview && vpaPiano.state().playing && vpaPiano.state().context==="running"'))
        except AssertionError:
            self.fail(str((dialog.preview_status.text(),self.evaluate('JSON.stringify({state:vpaPiano.state(),error:window.vpaMidiPreviewError})'))))
        self.wait(lambda:self.evaluate('(()=>{const b=new Float32Array(4096);midiAnalyser.getFloatTimeDomainData(b);return b.some(v=>Math.abs(v)>.00001)})()'))
        self.assertEqual(json.loads(self.evaluate('JSON.stringify(receivedMidiPreview.notes.map(n=>n.midi))')),[30])
        self.assertEqual(self.controller.collect_state(),before)
        QTest.mouseClick(dialog.stop_preview,Qt.LeftButton)
        self.wait(lambda:not self.evaluate('vpaPiano.state().playing'))
        QTest.mouseClick(dialog.listen_selected,Qt.LeftButton)
        self.wait(lambda:self.evaluate('vpaPiano.state().preview && vpaPiano.state().playing'))
        self.assertEqual(json.loads(self.evaluate('JSON.stringify(receivedMidiPreview.notes.map(n=>n.midi))')),[30,64])
        dialog.reject();self.wait(lambda:not self.evaluate('vpaPiano.state().playing'))
        self.assertEqual(self.controller.collect_state(),before)
        self.assertFalse(self.errors,self.errors)

    def test_chrome_no_selection_or_pointer_focus_outline_editor_still_editable(self):
        selectors=['#keys','.key','#sustain','.piano-collapse','footer','#reading']
        for selector in selectors:
            self.assertEqual(self.evaluate(f'getComputedStyle(document.querySelector({json.dumps(selector)})).userSelect'),'none')
        self.native_click('#sustain');self.evaluate('document.getElementById("sustain").focus();true')
        self.assertEqual(self.evaluate('getComputedStyle(document.getElementById("sustain")).outlineStyle'),'none')
        self.native_click('.key')
        self.assertEqual(self.evaluate('getComputedStyle(document.getElementById("keys")).outlineStyle'),'none')
        self.assertFalse(self.evaluate('document.querySelector("footer").dispatchEvent(new Event("selectstart",{bubbles:true,cancelable:true}))'))
        self.action('edit')
        self.assertEqual(self.evaluate('getComputedStyle(document.getElementById("notation")).userSelect'),'text')
        self.assertTrue(self.evaluate('document.getElementById("notation").dispatchEvent(new Event("selectstart",{bubbles:true,cancelable:true}))'))
        self.assertFalse(self.errors,self.errors)

    def test_square_chords_and_automatic_distant_continuation(self):
        c=self.controller
        source=score([(60,0,1),(64,0,1)]+[(pitch,i,1) for i,pitch in enumerate(range(61,69),1)])
        source['duration']=[9,1];source['measures'][0]['duration']=[9,1]
        c.musical_score=source;c.events=grouped_events(source);c.practice_mode='off';c.revision+=1;c.recompute();self.window.bridge.notify()
        self.wait(lambda:self.evaluate('vpaPreview.state().applied.tokens.length===9'))
        self.assertTrue(self.window.bridge.result(0,100,'ru','off')['tokens'][0]['label'].startswith('['))
        self.action('follow-reset')
        self.native_click('[data-action="follow-reset"]')
        self.evaluate('vpaPiano.press(67,"distant-a");vpaPiano.releaseManual();true')
        self.assertEqual(self.evaluate('vpaPreview.state().cursor'),0)
        self.evaluate('vpaPiano.press(68,"distant-b");vpaPiano.releaseManual();true')
        self.assertEqual(self.evaluate('vpaPreview.state().cursor'),9)
        self.assertFalse(self.errors,self.errors)

    def test_manual_empty_save_reopen_txt_and_conflict(self):
        self.load_xml()
        self.edit("МОИ ПРАВКИ\n")
        project=self.root/"manual.vpa.json"
        self.evaluate('document.getElementById("physical-layout").value="de";document.getElementById("physical-layout").dispatchEvent(new Event("change"));true')
        with patch.object(legacy.QFileDialog,"getSaveFileName",return_value=(str(project),"")):
            self.document_action("save")
            self.wait(project.exists)
        self.assertEqual(read_project(project)["transcription"],"МОИ ПРАВКИ\n")
        self.assertEqual(read_project(project)["physical_layout"],"Deutsch")
        self.assertEqual(json.loads(self.window.bridge.applyDocument(2,50,"en",False))["error"],"manual")
        self.assertEqual(self.controller.output.toPlainText(),"МОИ ПРАВКИ\n")
        self.edit("")
        target=self.root/"empty.txt"
        with patch.object(legacy.QFileDialog,"getSaveFileName",return_value=(str(target),"")):
            self.document_action("txt");self.wait(target.exists)
        self.assertEqual(target.read_text(),"")
        with patch.object(legacy.QFileDialog,"getSaveFileName",return_value=(str(project),"")):
            self.document_action("save");self.wait(lambda:not self.controller._dirty)
        self.assertTrue(read_project(project)["transcription_is_manual"])
        with patch.object(legacy.QFileDialog,"getOpenFileName",return_value=(str(project),"")):
            self.document_action("project")
            self.wait(lambda:self.controller.revision==2)
            self.wait(lambda:self.evaluate('vpaPreview.state().edited && document.getElementById("notation").value===""'))
        self.assertIsNotNone(self.controller.musical_score)
        self.assertEqual(self.evaluate('document.getElementById("physical-layout").value'),"de")
        self.assertEqual(self.controller._manual_text,"")

    def test_invalid_project_failed_save_and_cancel_preserve_document(self):
        self.load_xml();self.edit("owner text")
        original=copy.deepcopy(self.controller.collect_state())
        damaged=self.root/"bad.vpa.json";damaged.write_text("not json",encoding="utf-8")
        with patch.object(legacy.QFileDialog,"getOpenFileName",return_value=(str(damaged),"")),patch.object(legacy.QMessageBox,"critical"):
            self.document_action("project")
            QTest.qWait(100);self.app.processEvents()
        self.assertEqual(self.controller.collect_state(),original)
        existing=self.root/"kept.vpa.json";existing.write_bytes(b"previous file")
        with patch.object(legacy.QFileDialog,"getSaveFileName",return_value=(str(existing),"")),patch.object(legacy,"write_project",side_effect=OSError("write failed")),patch.object(legacy.QMessageBox,"critical"):
            self.document_action("save");QTest.qWait(100);self.app.processEvents()
        self.assertTrue(self.controller._dirty);self.assertEqual(existing.read_bytes(),b"previous file")
        with patch.object(legacy.QFileDialog,"getOpenFileName",return_value=(str(ROOT/"page-2.musicxml"),"")),patch.object(self.controller,"confirm_discard",return_value=False):
            self.document_action("xml");QTest.qWait(100);self.app.processEvents()
        self.assertEqual(self.controller.collect_state(),original)
        with patch.object(self.controller,"confirm_discard",return_value=False):
            self.window.close()
            QTest.qWait(150);self.app.processEvents()
        self.assertFalse(self.window.closed)
        self.assertEqual(self.controller._manual_text,"owner text")

    def test_legacy_v8_no_invented_timing_and_view_preferences(self):
        target=self.root/"legacy.vpa.json"
        data={"version":8,"events":[{"measure":1,"time":0,"duration":1,"notes":[60]}],"transcription":"custom","transcription_is_manual":True,"ui_language":"Deutsch","display_layout":"English"}
        write_project(target,data)
        with patch.object(legacy.QFileDialog,"getOpenFileName",return_value=(str(target),"")):
            self.document_action("project")
            self.wait(lambda:self.controller.revision==1)
            self.wait(lambda:self.evaluate('document.documentElement.lang==="de"'))
        self.assertFalse(self.evaluate('vpaPreview.state().applied.playable'))
        self.assertTrue(self.evaluate('document.getElementById("transport-toggle").disabled'))
        self.assertEqual(self.controller._manual_text,"custom")
        self.assertEqual(self.window.bridge.setView('{"fontSize":40,"keyLabels":"none","piano":false}'),"{}")
        self.assertEqual(json.loads(self.settings.value("studio-view"))["fontSize"],40)
        self.assertIn("error",self.window.bridge.setView('{"fontSize":200}'))

    def test_language_switch_keeps_playback_and_releases_manual_keys(self):
        self.load_xml()
        self.native_click('#transport-toggle')
        self.wait(lambda:self.evaluate('vpaPiano.state().playing'))
        self.native_click('[data-lang=de]')
        self.assertTrue(self.evaluate('vpaPiano.state().playing'))
        QTest.qWait(300)
        self.assertGreater(self.evaluate('vpaPiano.state().scorePosition'),.2)
        self.evaluate('document.getElementById("stop").click();vpaPiano.setSustain(true);document.getElementById("keys").focus();true')
        target=self.window.view.focusProxy() or self.window.view
        QTest.keyPress(target,Qt.Key_T)
        self.wait(lambda:self.evaluate('vpaPiano.state().held>0'))
        self.native_click('[data-lang=en]')
        self.assertEqual(self.evaluate('vpaPiano.state().held'),0)
        self.assertTrue(self.evaluate('vpaPiano.state().sustain'))
        QTest.keyRelease(target,Qt.Key_T)
        self.evaluate('vpaPiano.panic();true')
        midi=next(p for p,info in legacy.VP_MAP.items() if info["key"]=="Y" and not info["shift"])
        self.native_click('[data-lang=de]')
        self.assertEqual(self.evaluate('document.querySelector(".key[data-midi=\\"'+str(midi)+'\\"] span").textContent'),"z")

    def test_real_pedals_linked_and_separate_language_layout(self):
        self.load_xml();self.edit("Мой текст\n")
        music=copy.deepcopy(self.controller.musical_score)
        generated=self.controller._generated_text
        display=self.controller.display_layout.currentText()
        self.evaluate('document.documentElement.classList.add("reduce-motion");true')
        for lang in ("en","de","ru"):
            selector='[data-lang='+lang+']'
            before=self.evaluate('JSON.stringify(document.querySelector('+json.dumps(selector)+').getBoundingClientRect().toJSON())')
            self.native_click(selector)
            self.wait(lambda:self.controller.physical_layout.currentText()=={"ru":"Русская","en":"English","de":"Deutsch"}[lang])
            self.assertEqual(self.evaluate('document.getElementById("physical-layout").value'),lang)
            self.assertEqual(self.evaluate('document.getElementById("key-labels").value'),lang)
            self.assertEqual(self.evaluate('document.getElementById("interface-language").value'),lang)
            self.assertEqual(self.evaluate('document.querySelectorAll("[data-lang][aria-pressed=true]").length'),1)
            self.assertEqual(self.evaluate('getComputedStyle(document.querySelector('+json.dumps(selector)+'),"::before").transform'),"none")
            self.assertIn("brightness(0.85)",self.evaluate('getComputedStyle(document.querySelector('+json.dumps(selector)+'),"::before").filter'))
            asset={"ru":"language-pedal-left.svg","en":"language-pedal.svg","de":"language-pedal-right.svg"}[lang]
            self.assertIn(asset,self.evaluate('getComputedStyle(document.querySelector('+json.dumps(selector)+'),"::before").backgroundImage'))
            self.assertEqual(self.evaluate('JSON.stringify(document.querySelector('+json.dumps(selector)+').getBoundingClientRect().toJSON())'),before)
        self.assertEqual(self.controller.output.toPlainText(),"Мой текст\n")
        self.assertEqual(self.controller._generated_text,generated)
        self.assertEqual(self.controller.musical_score,music)
        self.assertEqual(self.controller.display_layout.currentText(),display)
        self.action("settings")
        self.native_click('[data-tab=view]')
        self.assertTrue(self.evaluate('document.getElementById("physical-layout").disabled'))
        self.native_click('#link-language-layout')
        self.assertFalse(self.evaluate('document.getElementById("physical-layout").disabled'))
        self.evaluate('document.getElementById("interface-language").value="de";document.getElementById("interface-language").dispatchEvent(new Event("change"));true')
        self.wait(lambda:self.controller.ui_lang.currentText()=="Deutsch")
        self.assertEqual(self.controller.physical_layout.currentText(),"Русская")
        self.evaluate('document.getElementById("physical-layout").value="en";document.getElementById("physical-layout").dispatchEvent(new Event("change"));true')
        self.wait(lambda:self.controller.physical_layout.currentText()=="English")
        self.assertEqual(self.controller.ui_lang.currentText(),"Deutsch")
        self.assertEqual(self.evaluate('document.getElementById("key-labels").value'),"en")
        self.evaluate('document.getElementById("key-labels").value="none";document.getElementById("key-labels").dispatchEvent(new Event("change"));true')
        self.native_click('#link-language-layout')
        self.wait(lambda:self.controller.physical_layout.currentText()=="Deutsch")
        self.assertEqual(self.evaluate('document.getElementById("key-labels").value'),"none")
        self.assertTrue(self.evaluate('document.getElementById("link-language-layout").checked'))
        self.native_click('#link-language-layout')
        self.evaluate('document.getElementById("physical-layout").value="en";document.getElementById("physical-layout").dispatchEvent(new Event("change"));true')
        self.wait(lambda:self.controller.physical_layout.currentText()=="English")
        self.assertFalse(self.window.bridge.view_preferences["linkLanguageLayout"])
        self.assertIn("error",self.window.bridge.setView('{"linkLanguageLayout":1}'))
        project=self.root/"languages.vpa.json"
        with patch.object(legacy.QFileDialog,"getSaveFileName",return_value=(str(project),"")):
            self.document_action("save");self.wait(project.exists)
        saved=read_project(project)
        self.assertEqual(saved["ui_language"],"Deutsch")
        self.assertEqual(saved["physical_layout"],"English")
        self.assertEqual(saved["transcription"],"Мой текст\n")
        self.controller._dirty=False;self.window.close_synced=True;self.window.close()
        self.app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.window=StudioWindow(self.settings,self.root/"new-recording")
        loaded=[]
        self.window.page.loadFinished.connect(loaded.append)
        self.controller=self.window.bridge.controller
        self.window.resize(1366,768);self.window.show()
        self.wait(lambda:bool(loaded))
        self.wait(lambda:self.evaluate('Boolean(window.vpaDocument && vpaDocument.active && vpaPreview.state().ready)'))
        self.assertFalse(self.evaluate('document.getElementById("link-language-layout").checked'))
        with patch.object(legacy.QFileDialog,"getOpenFileName",return_value=(str(project),"")):
            self.document_action("project")
            self.wait(lambda:self.evaluate('vpaPreview.state().edited'))
        self.assertEqual(self.evaluate('document.getElementById("physical-layout").value'),"en")
        self.assertEqual(self.evaluate('document.documentElement.lang'),"de")
        if os.environ.get("VPA_LANGUAGE_EVIDENCE"):
            variant="pianist" if os.environ["VPA_LANGUAGE_EVIDENCE"]=="pianist" else "real"
            QTest.qWait(200)
            self.window.grab().save(str(ROOT/"docs/feasibility/design-live"/f"language-pedals-{variant}.png"))
            self.action("settings");self.native_click('[data-tab=view]');QTest.qWait(200)
            name="language-layout-settings-pianist.png" if variant=="pianist" else "language-layout-settings.png"
            self.window.grab().save(str(ROOT/"docs/feasibility/design-live"/name))
            self.action("settings")
        self.window.resize(960,680)
        self.wait(lambda:self.evaluate('innerWidth===960'))
        self.assertEqual(self.evaluate('document.querySelectorAll(".key").length'),61)
        self.assertTrue(self.evaluate('document.querySelector(".brand").getBoundingClientRect().right<=document.querySelector(".top-actions").getBoundingClientRect().left'))
        self.assertTrue(self.evaluate('document.querySelector(".window-close").getBoundingClientRect().right<=innerWidth'))
        self.assertFalse(self.errors,self.errors)

    def test_all_attack_times_spacing_and_empty_manual_apply(self):
        source=score([(60,0,1),(25,2,1),(64,4,1)],
                     [{"onset":[0,1],"bpm":[120,1]},{"onset":[1,1],"bpm":[60,1]}])
        self.assertTrue(self.controller.install_events(grouped_events(source),"example.musicxml",source))
        self.window.bridge.notify()
        self.wait(lambda:self.evaluate('vpaPreview.state().tokenCount===3'))
        result=json.loads(self.window.bridge.document())
        self.assertEqual([t["start"] for t in result["tokens"]],[0,1.5,3.5])
        self.assertEqual(result["tokens"][1]["label"],"?")
        self.assertEqual(self.evaluate('document.getElementById("reading-text").textContent'),result["text"])
        self.controller.spacing_check.setChecked(True)
        self.controller.revision+=1;self.window.bridge.notify()
        self.wait(lambda:self.evaluate('vpaPreview.state().applied.spacing===true'))
        self.assertEqual(self.evaluate('document.getElementById("reading-text").textContent'),self.controller._generated_text)
        self.edit("changed");self.edit(self.controller._generated_text)
        self.wait(lambda:not self.evaluate('vpaPreview.state().edited'))
        self.controller.events=[];self.controller.musical_score=None
        self.controller._generated_text="";self.controller._manual_text="empty score edits"
        self.controller.set_output_text("empty score edits")
        self.window.bridge.applyDocument(0,100,"ru",True)
        self.assertEqual(self.controller.output.toPlainText(),"")
        self.assertIsNone(self.controller._manual_text)

    def test_feedback_skip_follow_focus_and_stable_dialog(self):
        self.edit("(6г) (0г) щ г")
        self.wait(lambda:self.evaluate('document.querySelectorAll(".notation-token").length===4'))
        def hit(char,token):
            self.evaluate('vpaPiano.press(Number([...document.querySelectorAll(".key")].find(k=>k.querySelector("span").textContent==='+json.dumps(char)+').dataset.midi),'+json.dumps(token)+');true')
        current=lambda:self.evaluate('[...document.querySelectorAll(".notation-token")].findIndex(t=>t.classList.contains("current"))')
        hit("г","g1");self.assertEqual(current(),0)
        hit("6","six");self.assertEqual(current(),1)
        hit("щ","skip");self.assertEqual(current(),3)
        self.evaluate('vpaPiano.releaseManual();true')
        hit("г","g2");self.assertEqual(current(),-1)
        self.native_click('.notation-token')
        self.assertEqual(current(),0,'clicking a token allows explicit seeking')
        self.evaluate('vpaPiano.setSustain(true);vpaPiano.focusLost();vpaPiano.focusLost();true')
        self.assertFalse(self.evaluate('vpaPiano.state().sustain'))
        self.evaluate('vpaPiano.focusRestored();true')
        self.assertTrue(self.evaluate('vpaPiano.state().sustain'))
        self.assertEqual(self.evaluate('document.querySelectorAll(".key.active").length'),0)
        self.evaluate('vpaPiano.focusLost();vpaPiano.panic();vpaPiano.focusRestored();true')
        self.assertFalse(self.evaluate('vpaPiano.state().sustain'))
        self.evaluate('vpaDocument.dialog("open");window.savedLabel=document.querySelector("#file-open-actions .gold-label");true')
        for _ in range(5):self.evaluate('vpaDocument.render();true')
        self.assertTrue(self.evaluate('savedLabel===document.querySelector("#file-open-actions .gold-label")'))
        self.assertFalse(self.evaluate('document.getElementById("file-overlay").hidden'))
        self.assertEqual(self.evaluate('getComputedStyle(document.getElementById("file-overlay")).backdropFilter'),"none")
        self.assertGreaterEqual(self.evaluate('parseFloat(getComputedStyle(document.getElementById("file-title")).marginBottom)'),18)
        self.assertTrue(self.evaluate('[...document.querySelectorAll(".language-pedals button")].every(b=>getComputedStyle(b,"::before").transform==="none")'))

    def test_practice_linked_pitch_both_paths_and_project(self):
        self.load_xml();c=self.controller;bridge=self.window.bridge
        original=copy.deepcopy(c.musical_score)
        result=json.loads(bridge.applyPractice(4,100,"ru","upper",True))
        self.assertEqual(result["pianoShift"],-4)
        self.assertTrue(all(len(t["pitches"])==1 for t in result["tokens"]))
        self.assertLess(result["selected"],result["original"])
        self.assertEqual(c.musical_score,original)
        plan=c.offline_plan()
        self.assertTrue(all(n["midi"]==n["displayMidi"]-4 for n in plan["notes"]))
        self.assertTrue(json.loads(bridge.plan())["notes"])
        self.wait(lambda:self.evaluate('vpaPiano.state().pianoShift===-4'))
        QTest.qWait(200)
        self.native_click('.key[data-midi="64"]')
        self.evaluate('vpaPiano.press(64,"test-pitch");true')
        self.wait(lambda:self.evaluate('vpaPiano.state().manualPitches.includes(60)'))
        self.native_click('#transport-toggle')
        self.wait(lambda:self.evaluate('vpaPiano.state().playing'))
        self.wait(lambda:self.evaluate('vpaPreview.state().cursor>0'),5)
        self.evaluate('vpaPiano.panic();true')
        bridge.pianoOptions(2,False)
        self.assertTrue(all(n["midi"]==n["displayMidi"]+2 for n in c.offline_plan()["notes"]))
        self.wait(lambda:self.evaluate('vpaPiano.state().pianoShift===2'))
        QTest.qWait(200)
        self.evaluate('vpaPiano.press(64,"independent");true')
        self.wait(lambda:self.evaluate('vpaPiano.state().manualPitches.includes(66)'))
        self.assertTrue(self.evaluate('document.getElementById("notation-settings").closest(".letter-panel")!==null'))
        self.assertFalse(self.evaluate('document.getElementById("settings").contains(document.getElementById("transpose"))'))
        target=self.root/"practice.vpa.json"
        with patch.object(legacy.QFileDialog,"getSaveFileName",return_value=(str(target),"")):c.save_project()
        data=read_project(target);self.assertEqual(data["practice_mode"],"upper");self.assertEqual(data["piano_shift"],2)
        with patch.object(legacy.QFileDialog,"getOpenFileName",return_value=(str(target),"")):c.open_project()
        self.assertEqual(c.practice_mode,"upper");self.assertEqual(c.piano_shift,2);self.assertFalse(c.link_piano_shift)
        self.assertIsNone(c._manual_text)
        self.edit("keep")
        self.assertIn("manual",bridge.applyPractice(0,100,"ru","normal",False))
        self.assertEqual(c.practice_mode,"upper");self.assertEqual(c._manual_text,"keep")

    def test_pdf_selected_page_isolated_render_and_errors(self):
        from PySide6.QtGui import QPdfWriter,QPainter,QImage
        pdf=self.root/"score.pdf"
        writer=QPdfWriter(str(pdf));painter=QPainter(writer)
        painter.drawText(100,100,"page one")
        writer.newPage();painter.drawText(100,100,"page two")
        painter.end();del painter,writer
        original=pdf.read_bytes();c=self.controller
        c.configure_pdf_pages(str(pdf));self.assertEqual(c.pdf_page_spin.maximum(),2)
        c.pdf_page_spin.setValue(2)
        rendered=Path(c.prepare_pdf_page(str(pdf)))
        self.assertEqual(QImage(str(rendered)).width(),2400)
        self.assertNotEqual(rendered.parent,pdf.parent)
        self.assertEqual(pdf.read_bytes(),original)
        c._recognition_render.cleanup();c._recognition_render=None
        c.pdf_page_spin.setRange(1,3);c.pdf_page_spin.setValue(3)
        with self.assertRaisesRegex(RuntimeError,"does not exist"):c.prepare_pdf_page(str(pdf))
        bad=self.root/"bad.pdf";bad.write_text("not a PDF")
        with self.assertRaisesRegex(RuntimeError,"could not be opened"):c.prepare_pdf_page(str(bad))

    def test_unified_open_auto_detects_and_preserves_cancelled_document(self):
        c=self.controller
        def choose(paths):
            with patch.object(legacy.QFileDialog,"getOpenFileNames",return_value=(list(map(str,paths)),"")) as chooser,patch.object(c,"confirm_discard",return_value=True):
                self.native_click('[data-action=open]')
                self.wait(lambda:chooser.called)
                QTest.qWait(100)
            self.wait(lambda:self.evaluate('document.getElementById("notation").value')==c.output.toPlainText())
        choose([ROOT/"page-2.musicxml",ROOT/"page-1.musicxml"])
        self.wait(lambda:len(c.events)==299)
        self.assertEqual(len(c.musical_score["measures"]),46)
        c.mark_clean();before=copy.deepcopy(c.collect_state())
        choose([]);self.assertEqual(c.collect_state(),before)
        with patch.object(QMessageBox,"information") as message:
            choose([ROOT/"page-1.musicxml",self.root/"letters.txt"])
            self.assertTrue(message.called)
        self.assertEqual(c.collect_state(),before)
        text=self.root/"letters.txt";text.write_bytes("я (6г)\rо".encode("utf-16"))
        choose([text]);self.wait(lambda:c._manual_text=="я (6г)\nо")
        self.assertIsNone(c.musical_score)
        project=self.root/"letters.vpa.json"
        with patch.object(legacy.QFileDialog,"getSaveFileName",return_value=(str(project),"")):c.save_project()
        choose([project]);self.wait(lambda:c.project_path==str(project))
        self.assertEqual(c._manual_text,"я (6г)\nо")

    def test_simplification_off_restores_all_notes_after_save_and_reopen(self):
        self.load_xml();c=self.controller;b=self.window.bridge
        original=copy.deepcopy(c.musical_score)
        reduced=json.loads(b.applyPractice(0,0,"ru","single",True))
        self.assertLess(reduced["selected"],reduced["original"])
        restored=json.loads(b.applyPractice(0,0,"ru","off",True))
        self.assertEqual(restored["fullness"],100)
        self.assertEqual(restored["selected"],restored["original"])
        self.assertEqual(c.chord_slider.value(),0)
        self.assertEqual(c.musical_score,original)
        self.assertEqual(len(c.offline_plan()["notes"]),restored["original"])
        target=self.root/"restored.vpa.json"
        with patch.object(legacy.QFileDialog,"getSaveFileName",return_value=(str(target),"")):c.save_project()
        self.assertEqual(read_project(target)["practice_mode"],"off")
        c.open_project(str(target));self.assertEqual(c.practice_mode,"off")
        self.assertEqual(c.musical_score,original)
        self.edit("keep my text")
        self.assertIn("manual",b.applyPractice(0,100,"ru","single",False))
        self.assertEqual(c.practice_mode,"off")
        self.assertEqual(c._manual_text,"keep my text")

    def test_pdf_auto_open_recognises_every_page_not_selected_page(self):
        import sys
        from PySide6.QtGui import QPdfWriter,QPainter,QImage
        pdf=self.root/"two-pages.pdf"
        writer=QPdfWriter(str(pdf));painter=QPainter(writer)
        painter.drawText(100,100,"one");writer.newPage();painter.drawText(100,100,"two")
        painter.end();del painter,writer
        original=pdf.read_bytes();c=self.controller
        c.pdf_page_spin.setValue(1)
        inputs=[]
        def command(_exe,image):
            rendered=QImage(str(image))
            self.assertFalse(rendered.hasAlphaChannel())
            self.assertEqual(rendered.pixelColor(2200,2200).name(),'#ffffff')
            inputs.append((image.name,rendered.width()))
            return [sys.executable,"-u","-c","import shutil,sys;shutil.copyfile(sys.argv[1],sys.argv[2]);print('Writing XML')",str(ROOT/"page-1.musicxml"),str(image.with_suffix(".musicxml"))]
        with patch.object(c,"homr_exe",return_value=Path(sys.executable)),patch("recognition.homr_command",command),patch.object(c,"show_timing_warnings"),patch.object(legacy.QFileDialog,"getOpenFileNames",return_value=([str(pdf)],"")):
            self.document_action("open")
            self.wait(lambda:not c.busy and c.recognition_stage=="done")
        self.assertEqual(len(inputs),2)
        self.assertTrue(all(width==2400 for _,width in inputs))
        self.assertEqual(c.recognition_total,2)
        self.assertEqual(pdf.read_bytes(),original)
        self.assertIsNone(c._recognition_render);self.assertIsNone(c.worker._directory)
        self.assertTrue(any("unverified" in w for w in c.musical_score["warnings"]))
        before=copy.deepcopy(c.musical_score)
        damaged=self.root/"bad.pdf";damaged.write_text("not a PDF")
        with patch.object(c,"homr_exe",return_value=Path(sys.executable)),patch.object(c,"confirm_discard",return_value=True),patch.object(QMessageBox,"critical"):
            c.open_score([str(damaged)])
        self.assertEqual(c.musical_score,before)
        self.assertFalse(c.busy);self.assertIsNone(c._recognition_render)

    def test_recognition_progress_cancel_retry_and_result(self):
        import sys
        source=self.root/"source.png";source.write_text("wait")
        c=self.controller;c.score_path=str(source)
        command=lambda _exe,image:[sys.executable,"-u",str(ROOT/"tests/fixtures/mock_homr.py"),str(image)]
        with patch.object(c,"homr_exe",return_value=Path(sys.executable)),patch("recognition.homr_command",command):
            self.evaluate('vpaDocument.dialog("open");true')
            self.document_action("recognize")
            self.wait(lambda:c.busy and getattr(c,"recognition_stage","")=="processing")
            self.wait(lambda:self.evaluate('!document.querySelector("[data-document-action=cancel]").hidden'))
            self.assertFalse(self.evaluate('document.getElementById("recognition-progress").hidden'))
            geometry=json.loads(self.evaluate('''JSON.stringify((()=>{
                const p=document.getElementById('recognition-progress'),m=p.closest('.modal'),status=document.getElementById('file-error');
                const a=p.getBoundingClientRect(),b=m.getBoundingClientRect(),s=status.getBoundingClientRect();
                return {height:a.height,left:a.left-b.left,right:b.right-a.right,below:a.top>=s.bottom,appearance:getComputedStyle(p).webkitAppearance};
            })())'''))
            self.assertEqual(geometry['height'],12)
            self.assertLessEqual(abs(geometry['left']),2,geometry)
            self.assertLessEqual(abs(geometry['right']),2,geometry)
            self.assertTrue(geometry['below'],geometry)
            self.assertEqual(geometry['appearance'],'none')
            if os.environ.get('VPA_NEW_EVIDENCE'):
                QTest.qWait(300);self.window.grab().save(str(Path(os.environ['VPA_NEW_EVIDENCE'])/'gold-recognition.png'))
            self.assertTrue(self.evaluate('document.getElementById("notation").disabled'))
            self.assertIn("recognizing",self.window.bridge.applyDocument(0,100,"ru",True))
            with patch.object(QMessageBox,"information"):
                self.window.close();self.assertFalse(self.window.closed)
            self.native_click('[data-document-action="cancel"]')
            self.wait(lambda:not c.busy and c.recognition_stage=="cancelled")
            self.wait(lambda:self.evaluate('document.getElementById("recognition-progress").hidden'))
            self.assertFalse(self.evaluate('document.querySelector("[data-action=record]").disabled'))
            self.assertFalse(c.events);self.assertIsNone(c.worker._directory)
            source.write_text("quality-score")
            self.document_action("recognize")
            self.wait(lambda:not c.busy and c.recognition_stage=="done")
            self.wait(lambda:self.evaluate('vpaPreview.state().applied.text.length>0'))
            self.assertEqual(len(c.events),158)
            self.assertIsNone(c.musicxml_path)
            self.assertEqual(c.score_path,str(source))
            self.assertIsNone(c.worker._directory)
            self.assertFalse(source.with_suffix(".musicxml").exists())
            self.assertIn("тактов 2", "\n".join(c.musical_score["warnings"]))
            self.wait(lambda:self.evaluate('document.querySelector(".editor-foot span:last-child").title.includes("тактов 2")'))
            self.assertIn("проверьте распознавание",self.evaluate('document.querySelector(".editor-foot span:last-child").textContent'))
            for language,label in (("en","review recognition"),("de","Erkennung prüfen")):
                self.evaluate('document.querySelector(\'[data-lang="'+language+'"]\').click();true')
                self.wait(lambda:label in self.evaluate('document.querySelector(".editor-foot span:last-child").textContent'))

    def test_source_recognition_bindings_and_failure(self):
        self.load_xml();self.controller.mark_clean()
        source=self.root/"source.png"
        self.window.grab().save(str(source))
        original=copy.deepcopy(self.controller.musical_score)
        missing=self.root/"missing-homr.exe"
        with patch.object(legacy.QFileDialog,"getOpenFileNames",return_value=([str(source)],"")),patch.object(self.controller,"homr_exe",return_value=missing),patch.object(legacy.QMessageBox,"critical") as message:
            self.document_action("source")
            self.wait(lambda:message.called)
        self.assertFalse(self.controller.busy)
        self.assertEqual(self.controller.musical_score,original)
        self.assertEqual(self.controller.pending_sources,[str(source)])
        with patch.object(legacy.MainWindow,"confirm_discard",return_value=True):
            self.controller.recognition_done(str(ROOT/"page-1.musicxml"),"")
        self.wait(lambda:self.evaluate('vpaPreview.state().applied.playable'))
        self.assertEqual(len(self.controller.events),158)
        self.assertEqual(self.controller.score_path,str(source))

    def test_auto_batch_order_failure_cancel_and_retry_keep_old_document(self):
        import sys
        self.load_xml();self.edit("owner notes")
        c=self.controller;original=copy.deepcopy(c.musical_score)
        sources=[self.root/"page-10.png",self.root/"page-2.png"]
        sources[1].write_text("score");sources[0].write_text("fail")
        command=lambda _exe,image:[sys.executable,"-u",str(ROOT/"tests/fixtures/mock_homr.py"),str(image)]
        with patch.object(c,"homr_exe",return_value=Path(sys.executable)),patch("recognition.homr_command",command),patch.object(legacy.MainWindow,"confirm_discard",return_value=True) as consent,patch.object(QMessageBox,"critical"):
            with patch.object(legacy.QFileDialog,"getOpenFileNames",return_value=([str(p) for p in sources],"")):
                self.document_action("source")
            self.wait(lambda:not c.busy and c.recognition_stage=="failed")
            self.assertEqual(c.pending_sources,[str(sources[1]),str(sources[0])])
            self.assertEqual(c.musical_score,original);self.assertEqual(c._manual_text,"owner notes")
            self.assertIsNone(c.worker._directory)
            sources[0].write_text("wait")
            self.document_action("recognize")
            self.wait(lambda:c.recognition_index==2 and c.busy)
            self.document_action("cancel")
            self.wait(lambda:not c.busy and c.recognition_stage=="cancelled")
            self.assertEqual(c.musical_score,original);self.assertEqual(c._manual_text,"owner notes")
            sources[0].write_text("score2")
            self.document_action("recognize")
            self.wait(lambda:not c.busy and c.recognition_stage=="done")
            self.wait(lambda:self.evaluate('vpaPreview.state().applied.tokens.length===299'))
            self.assertEqual(len(c.musical_score["measures"]),46)
            self.assertEqual(len(c.events),299);self.assertIsNone(c._manual_text)
            self.assertEqual(consent.call_count,1,"source approval is not repeated at installation/retry")
            self.assertIsNone(c.worker._directory)
        self.assertEqual(sources[0].read_text(),"score2")
        self.assertFalse(sources[0].with_suffix(".musicxml").exists())

    def test_txt_import_encodings_cancel_and_project_without_fake_timing(self):
        self.load_xml();self.edit("keep old")
        c=self.controller;original=copy.deepcopy(c.musical_score)
        source=self.root/"notation.txt";source.write_bytes("я (6г)\rо".encode("cp1251"))
        with patch.object(legacy.QFileDialog,"getOpenFileName",return_value=(str(source),"")),patch("studio_ui.QInputDialog.getItem",return_value=("cp1251",False)):
            self.document_action("text");QTest.qWait(100)
        self.assertEqual(c._manual_text,"keep old");self.assertEqual(c.musical_score,original)
        with patch.object(legacy.QFileDialog,"getOpenFileName",return_value=(str(source),"")),patch("studio_ui.QInputDialog.getItem",return_value=("cp1251",True)),patch.object(c,"confirm_discard",return_value=True):
            self.document_action("text")
            self.wait(lambda:self.evaluate('document.getElementById("reading-text").textContent==="я (6г)\\nо"'))
        self.assertEqual(c._manual_text,"я (6г)\nо");self.assertFalse(c.events);self.assertIsNone(c.musical_score)
        self.assertFalse(json.loads(self.window.bridge.document())["playable"])
        self.assertFalse(json.loads(self.window.bridge.document())["source"])
        self.assertTrue(self.evaluate('document.getElementById("transport-toggle").disabled'))
        target=self.root/"letters.vpa.json"
        with patch.object(legacy.QFileDialog,"getSaveFileName",return_value=(str(target),"")):c.save_project()
        with patch.object(legacy.QFileDialog,"getOpenFileName",return_value=(str(target),"")):c.open_project()
        self.assertEqual(c._manual_text,"я (6г)\nо");self.assertIsNone(c.musical_score)

    def test_txt_musical_adaptation_preview_restore_and_source_project(self):
        c=self.controller;c.display_layout.setCurrentText('English')
        labels=c.letter_labels('English');source_text='['+''.join(labels[p] for p in (48,60,61,64,67))+']\n['+''.join(labels[p] for p in (60,61,64,67))+']'
        path=self.root/'letters.txt';path.write_text(source_text,encoding='utf-8')
        with patch.object(c,'confirm_discard',return_value=True):c.open_text(str(path))
        proposal=json.loads(self.window.bridge.previewPractice(0,100,'en','musical'))
        self.assertEqual([t['pitches'] for t in proposal['tokens']],[[48,67],[60,67]])
        self.assertFalse(proposal['playable']);self.assertFalse(proposal['rhythm'])
        self.assertFalse(c.events);self.assertIsNone(c.musical_score)
        self.assertEqual(json.loads(self.window.bridge.applyPractice(0,100,'en','musical',False))['error'],'manual')
        self.window.bridge.applyPractice(0,100,'en','musical',True)
        self.assertEqual(c.output.toPlainText(),proposal['text']);self.assertEqual(c._text_source['text'],source_text)
        project=self.root/'letters.vpa.json';write_project(project,c.collect_state())
        self.window.bridge.applyPractice(0,100,'en','off',True)
        self.assertEqual(c.output.toPlainText(),source_text)
        with patch.object(c,'confirm_discard',return_value=True):self.assertTrue(c.open_project(str(project)))
        self.assertEqual(c.output.toPlainText(),proposal['text']);self.assertEqual(c._text_source['text'],source_text)
        self.assertFalse(json.loads(self.window.bridge.document())['playable'])
        self.assertEqual(path.read_text(encoding='utf-8'),source_text)
        self.assertTrue(self.evaluate('document.querySelector("#practice-mode option[value=musical]")!==null'))

    def test_keyboard_practice_proposal_plan_restore_and_skip_follow(self):
        c=self.controller
        source=score([(60,0,1),(61,0,1),(64,0,1),(62,1,1),(66,2,1),(67,3,1)])
        c.musical_score=copy.deepcopy(source);c.events=grouped_events(source)
        c.practice_mode='normal';c.revision+=1;c.recompute();self.window.bridge.notify()
        self.wait(lambda:self.evaluate('vpaPreview.state().applied.tokens.length===4'))
        self.action('follow-reset')
        self.evaluate('vpaPiano.press(66,"skip-note");true')
        self.assertEqual(self.evaluate('vpaPreview.state().cursor'),3)
        self.evaluate('vpaPiano.releaseManual();true')
        self.assertIn('Пропуск',self.evaluate('document.getElementById("follow-status").textContent'))
        for mode in ('keyboard','balanced'):
            for shift in (-4,0,5):
                proposal=self.window.bridge.result(shift,100,'ru',mode)
                for token in proposal['tokens']:
                    self.assertEqual(len({legacy.VP_MAP[p]['shift'] for p in token['pitches']}),1)
                result=json.loads(self.window.bridge.applyPractice(shift,100,'ru',mode,True))
                self.assertNotIn('error',result)
                plan=c.offline_plan()
                self.assertEqual([(n['start'],n['end'],n['displayMidi']) for n in plan['notes']],
                                 [(n['start'],n['end'],n['midi']) for n in __import__('arrangement').playback_plan(c.practice_model(mode,shift),shift,0)['notes']])
                self.assertEqual(c.musical_score,source)
        path=self.root/'keyboard.vpa.json';write_project(path,c.collect_state())
        self.assertEqual(read_project(path)['practice_mode'],'balanced')
        self.window.bridge.applyPractice(0,100,'ru','off',True)
        self.assertEqual(len(c.offline_plan()['notes']),len(source['notes']))
        self.assertEqual(c.musical_score,source)
        self.evaluate('document.getElementById("notation-settings").open=true;true')
        self.wait(lambda:self.evaluate('!document.getElementById("notation-overlay").hidden'))
        self.assertTrue(self.evaluate('Boolean(document.querySelector("#practice-mode option[value=keyboard]"))'))
        self.evaluate('document.getElementById("practice-mode").value="balanced";document.getElementById("practice-mode").dispatchEvent(new Event("change"));true')
        self.wait(lambda:self.evaluate('vpaPreview.state().proposal.practiceMode==="balanced"'))
        if os.environ.get('VPA_NEW_EVIDENCE'):
            QTest.qWait(300);self.window.grab().save(str(Path(os.environ['VPA_NEW_EVIDENCE'])/'keyboard-practice.png'))

    def test_gold_progress_persistent_review(self):
        c=self.controller;c._recognition_pending=True;c.recognition_stage='processing';c.recognition_total=7;c.recognition_index=2
        self.window.bridge.notify();self.evaluate('vpaDocument.dialog("open");true')
        self.wait(lambda:self.evaluate('!document.getElementById("recognition-progress").hidden'))
        try:
            QTest.qWait(1500)
            self.assertTrue(self.evaluate('document.getElementById("recognition-progress").getBoundingClientRect().width>470'))
            if os.environ.get('VPA_NEW_EVIDENCE'):
                self.window.view.grab().save(str(Path(os.environ['VPA_NEW_EVIDENCE'])/'gold-recognition-persistent.png'))
        finally:
            c._recognition_pending=False;c.recognition_stage='';self.window.bridge.notify()

    def test_feedback_layout_and_modal_tabs(self):
        self.load_xml()
        for width,height in ((1366,900),(960,680)):
            self.window.resize(width,height);self.wait(lambda:self.evaluate('innerWidth==='+str(width)))
            self.evaluate('document.getElementById("notation-settings").open=false;true')
            QTest.qWait(200)
            geometry=json.loads(self.evaluate('JSON.stringify({bottom:document.querySelector(".piano").getBoundingClientRect().bottom,reading:document.getElementById("reading").getBoundingClientRect().height,height:innerHeight})'))
            self.assertLessEqual(geometry["bottom"],height,geometry)
            self.assertGreaterEqual(geometry["reading"],95,geometry)
            self.assertEqual(self.evaluate('vpaPreview.state().keyHeight'),220,'automatic fit must preserve the preferred key height')
            self.evaluate('document.getElementById("notation-settings").open=true;true');QTest.qWait(200)
            self.assertGreaterEqual(self.evaluate('document.getElementById("reading").getBoundingClientRect().height'),95)
            self.assertLessEqual(self.evaluate('document.querySelector(".piano").getBoundingClientRect().bottom'),height)
            geometry=json.loads(self.evaluate('JSON.stringify((()=>{const form=document.querySelector("#notation-overlay .notation-controls"),r=form.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:form.clientHeight,scroll:form.scrollHeight,visible:[...form.querySelectorAll("button,input,select")].filter(el=>el.getClientRects().length).every(el=>{const b=el.getBoundingClientRect();return b.top>=r.top&&b.bottom<=r.bottom})};})())'))
            self.assertGreaterEqual(geometry["top"],0,geometry)
            self.assertLessEqual(geometry["bottom"],height,geometry)
            self.assertLessEqual(geometry["scroll"],geometry["height"]+1,geometry)
            self.assertTrue(geometry["visible"],geometry)
            self.assertTrue(self.evaluate('document.querySelector(".app").inert'))
            self.assertTrue(self.evaluate('document.getElementById("notation-overlay").contains(document.activeElement)'))
            self.native_click('[data-step-for=transpose][data-step="1"]')
            self.wait(lambda:self.evaluate('document.getElementById("transpose").value==="1"'))
            self.evaluate('document.getElementById("transpose").value="12";document.getElementById("transpose").dispatchEvent(new Event("change"));true')
            self.native_click('[data-step-for=transpose][data-step="1"]')
            self.assertEqual(self.evaluate('document.getElementById("transpose").value'),"12")
            self.evaluate('document.getElementById("transpose").value="0";document.getElementById("transpose").dispatchEvent(new Event("change"));true')
            self.native_click('[data-practice=restore]')
            self.assertEqual(self.evaluate('document.getElementById("practice-mode").value'),"off")
            self.assertTrue(self.evaluate('document.getElementById("fullness").disabled'))
            self.native_click('[data-action=cancel]')
            self.assertEqual(self.evaluate('document.getElementById("practice-mode").value'),"normal")
            self.assertFalse(self.evaluate('document.getElementById("fullness").disabled'))
            self.evaluate('document.getElementById("notation-settings").open=false;true');QTest.qWait(150)
            self.assertFalse(self.evaluate('document.querySelector(".app").inert'))
        for lang,expected_label in (("en","One semitone up"),("de","Einen Halbton höher"),("ru","На полутон выше")):
            self.native_click('[data-lang='+lang+']')
            self.evaluate('document.getElementById("notation-settings").open=true;true');QTest.qWait(150)
            self.assertEqual(self.evaluate('document.querySelector("[data-step-for=transpose][data-step=\\"1\\"]").getAttribute("aria-label")'),expected_label)
            self.assertTrue(self.evaluate('(()=>{const f=document.querySelector("#notation-overlay .notation-controls"),r=f.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&f.scrollHeight<=f.clientHeight+1;})()'))
            self.evaluate('document.getElementById("notation-settings").open=false;true');QTest.qWait(100)
        self.edit("keep this manually edited text")
        self.evaluate('document.getElementById("notation-settings").open=true;true');QTest.qWait(150)
        self.native_click('[data-action=apply]')
        self.wait(lambda:self.evaluate('!document.getElementById("conflict").hidden'))
        self.assertTrue(self.evaluate('document.getElementById("notation-overlay").contains(document.getElementById("conflict"))'))
        self.assertTrue(self.evaluate('document.getElementById("conflict").getBoundingClientRect().bottom<=innerHeight'))
        self.native_click('[data-action=keep]')
        self.assertEqual(self.controller._manual_text,"keep this manually edited text")
        self.native_click('[data-action=apply]')
        self.wait(lambda:self.evaluate('!document.getElementById("conflict").hidden'))
        self.native_click('[data-action=replace]')
        self.wait(lambda:self.controller._manual_text is None)
        self.window.resize(1366,900)
        self.evaluate('document.getElementById("notation-settings").open=true;true')
        QTest.qWait(500)
        if os.environ.get("VPA_FEEDBACK_EVIDENCE"):
            self.window.grab().save(str(ROOT/"docs/feasibility/design-live/review-tone-modal.png"))
        self.evaluate('document.getElementById("notation-settings").open=false;true');QTest.qWait(150)
        self.action("settings")
        for _ in range(3):
            self.native_click('[data-tab=view]');self.native_click('[data-tab=sound]')
            self.assertFalse(self.evaluate('document.getElementById("settings-overlay").hidden'))
        if os.environ.get("VPA_FEEDBACK_EVIDENCE"):
            QTest.qWait(500);self.window.grab().save(str(ROOT/"docs/feasibility/design-live/review-sound-settings.png"))
        self.action("settings")
        self.evaluate('vpaDocument.dialog("open");true');QTest.qWait(500)
        self.assertFalse(self.evaluate('document.getElementById("file-overlay").hidden'))
        if os.environ.get("VPA_FEEDBACK_EVIDENCE"):
            self.window.grab().save(str(ROOT/"docs/feasibility/design-live/review-open-progress.png"))

    def test_native_playback_cursor_editor_and_recording(self):
        self.load_xml()
        self.native_click("#transport-toggle")
        self.wait(lambda:self.evaluate('vpaPiano.state().playing'))
        QTest.qWait(800)
        self.assertGreater(self.evaluate('vpaPiano.state().scorePosition'),.3)
        self.assertTrue(self.evaluate('document.querySelector(".notation-token.current")!==null'))
        if os.environ.get("VPA_STUDIO_EVIDENCE"):
            QTest.qWait(100)
            self.window.grab().save(str(ROOT/"docs"/"feasibility"/"design-live"/"studio-document.png"))
        self.evaluate('document.getElementById("stop").click();true')
        self.action("edit")
        self.evaluate('document.getElementById("notation").focus();true')
        QTest.keyClick(self.window.view.focusProxy() or self.window.view,Qt.Key_K)
        self.wait(lambda:self.controller._manual_text is not None)
        self.assertFalse(self.evaluate('vpaPiano.state().playing'))
        self.assertEqual(self.evaluate('vpaPiano.state().held'),0)
        self.action("edit")
        self.native_click(".record")
        self.wait(lambda:self.evaluate('vpaRecording.state().phase==="recording"'))
        original=copy.deepcopy(self.controller.collect_state())
        blocked=json.loads(self.window.bridge.documentAction("xml",self.controller.output.toPlainText(),1))
        self.assertEqual(blocked["error"],"recording")
        self.assertEqual(self.controller.collect_state(),original)
        self.evaluate('document.getElementById("keys").focus();true')
        QTest.keyPress(self.window.view.focusProxy() or self.window.view,Qt.Key_T);QTest.qWait(250)
        QTest.keyRelease(self.window.view.focusProxy() or self.window.view,Qt.Key_T)
        self.action("record");self.wait(lambda:self.evaluate('vpaRecording.state().phase==="ready"'),8)
        self.assertGreater(self.window.recorder.current.frames,0)
        target=self.root/"piano.wav"
        with patch("recording_bridge.QFileDialog.getSaveFileName",return_value=(str(target),"")):
            self.evaluate('vpaRecording.export("wav");true')
            self.wait(lambda:self.window.recorder.current.saved)
        self.assertTrue(target.is_file())


if __name__=="__main__":unittest.main()
