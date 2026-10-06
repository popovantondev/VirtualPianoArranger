"""Real local WebEngine preview, sampler A/B and layout checks; no user files."""
import array
import base64
import io
import json
import os
import struct
from pathlib import Path
import time
import unittest
import wave

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QIcon, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from docs.design.preview_dark import PreviewBridge, PreviewWindow, ROOT


class Settings:
    def __init__(self):
        self.data = {}
    def value(self, key, default=None):
        return self.data.get(key, default)
    def setValue(self, key, value):
        self.data[key] = value


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def wait(self, predicate, seconds=20):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(0.01)
        self.fail("Preview timed out")

    def evaluate(self, script):
        result = []
        self.window.page.runJavaScript(script, result.append)
        self.wait(lambda: bool(result), 5)
        return result[0]

    def action(self, name):
        self.evaluate('document.querySelector(\'[data-action="' + name + '"]\').click(); true')

    def test_bridge_uses_existing_arrangement_without_mutating_source(self):
        bridge = PreviewBridge()
        source = json.dumps(bridge.source)
        full = json.loads(bridge.preview(0, 100, "ru"))
        easy = json.loads(bridge.preview(0, 0, "ru"))
        self.assertGreater(full["selected"], easy["selected"])
        self.assertNotEqual(full["text"], easy["text"])
        self.assertEqual(bridge.applied, (0, 0, "ru"))
        self.assertEqual(json.loads(bridge.apply(999, 0, "ru")), {"error": "invalid"})
        bridge.apply(2, 0, "de")
        self.assertEqual(bridge.applied, (2, 100, "de"))
        self.assertEqual(json.dumps(bridge.source), source)
        self.assertEqual(len(json.loads(bridge.plan())["notes"]), easy["selected"])
        self.assertEqual(json.loads(bridge.preview(0, 100, "invalid")), {"error": "invalid"})
        actions = []
        bridge.windowActionRequested.connect(actions.append)
        for action in ("minimize", "resize-ne", "maximize", "delete-project"):
            bridge.windowAction(action)
        self.assertEqual(actions, ["minimize", "resize-ne", "maximize"])

    def test_icon_contains_small_and_large_windows_frames(self):
        data = (ROOT / "assets/icons/vpa.ico").read_bytes()
        self.assertEqual(struct.unpack_from("<HHH", data), (0, 1, 7))
        sizes = []
        for index in range(7):
            width, height, _, _, planes, bits, length, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * index)
            sizes.append(width or 256)
            self.assertEqual(width, height)
            self.assertEqual((planes, bits), (1, 32))
            self.assertTrue(data[offset:offset+length].startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(sizes, [16, 24, 32, 48, 64, 128, 256])
        self.assertFalse(QIcon(str(ROOT / "assets/icons/vpa.ico")).isNull())
        self.assertEqual(QImage(str(ROOT / "assets/icons/vpa-1024.png")).width(), 1024)

    def test_settings_overlay_focus_and_escape(self):
        self.window = PreviewWindow(Settings())
        try:
            self.window.resize(1366, 768)
            self.window.show()
            self.wait(lambda: self.evaluate('Boolean(window.vpaPreview && vpaPreview.state().ready)'))
            self.evaluate('document.querySelector("[data-lang=de]").click();true')
            self.action("settings")
            self.assertTrue(self.evaluate('document.querySelector(".app").inert'))
            self.assertTrue(self.evaluate('document.querySelector("#settings").getBoundingClientRect().bottom<innerHeight'))
            self.assertTrue(self.evaluate('document.querySelector("#settings-overlay").getBoundingClientRect().height===innerHeight'))
            target = self.window.view.focusProxy() or self.window.view
            self.evaluate('const controls=[...document.querySelectorAll("#settings button,#settings input,#settings select")].filter(el=>!el.disabled&&el.getClientRects().length);controls.at(-1).focus();true')
            QTest.keyClick(target,Qt.Key_Tab)
            self.wait(lambda: self.evaluate('document.activeElement.matches("#settings [data-action=settings]")'),3)
            QTest.keyClick(target,Qt.Key_Tab,Qt.ShiftModifier)
            self.wait(lambda: self.evaluate('document.activeElement.matches("[data-action=cancel]")'),3)
            if os.environ.get("VPA_PREVIEW_EVIDENCE"):
                QTest.qWait(200)
                self.window.view.grab().save(str(ROOT / "docs/feasibility/design-live/revision-7-settings-fresh-de.png"))
            QTest.keyClick(target,Qt.Key_Escape)
            self.wait(lambda: self.evaluate('!vpaPreview.state().settings'),3)
            self.assertFalse(self.evaluate('document.querySelector(".app").inert'))
            self.assertTrue(self.evaluate('document.activeElement.matches(".app [data-action=settings]")'))
        finally:
            self.window.close()
            self.app.processEvents()
            QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def test_keyboard_finish_and_language_pedals(self):
        self.window = PreviewWindow(Settings())
        try:
            self.window.resize(1366, 768)
            self.window.show()
            self.wait(lambda: self.evaluate('Boolean(window.vpaPreview && vpaPreview.state().ready)'))
            self.assertEqual(self.evaluate('document.querySelectorAll("[data-t=keyHint]").length'),0)
            self.assertEqual(self.evaluate('document.querySelectorAll(".language-pedals .pedal-label").length'),3)
            self.assertTrue(self.evaluate('document.querySelector("[data-action=credits]").closest(".piano-bottom-meta")!==null'))
            shape = json.loads(self.evaluate('''JSON.stringify((()=>{
                const white=document.querySelector(".key.white"),black=document.querySelector(".key.black");
                const base=parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--key-height"));
                return {extension:white.getBoundingClientRect().height-base,
                    ratio:black.getBoundingClientRect().height/white.getBoundingClientRect().height,
                    radius:getComputedStyle(white).borderBottomLeftRadius,
                    frontBorder:getComputedStyle(white,"::after").borderTopWidth};
            })())'''))
            self.assertAlmostEqual(shape["extension"],24,delta=.1)
            self.assertAlmostEqual(shape["ratio"],.63,delta=.01)
            self.assertEqual(shape["radius"],"6px")
            self.assertEqual(shape["frontBorder"],"0px")
            if os.environ.get("VPA_PEDAL_EVIDENCE"):
                QTest.qWait(200)
                self.window.view.grab().save(str(ROOT / "docs/feasibility/design-live/revision-10-1366.png"))
            target = self.window.view.focusProxy() or self.window.view
            self.evaluate('document.documentElement.classList.add("reduce-motion");true')
            for lang in ("en","de","ru"):
                rect = json.loads(self.evaluate('JSON.stringify(document.querySelector("[data-lang='+lang+']").getBoundingClientRect().toJSON())'))
                QTest.mouseClick(target,Qt.LeftButton,Qt.NoModifier,QPoint(int(rect["x"]+rect["width"]/2),int(rect["y"]+rect["height"]/2)))
                self.wait(lambda: self.evaluate('document.documentElement.lang==="'+lang+'"'),3)
                self.assertEqual(self.evaluate('document.querySelectorAll("[data-lang][aria-pressed=true]").length'),1)
                self.assertEqual(self.evaluate('document.querySelector("[data-lang][aria-pressed=true]").dataset.lang'),lang)
                self.assertEqual(self.evaluate('getComputedStyle(document.querySelector("[data-lang='+lang+']"),"::before").transform'),"matrix(1, 0, 0, 1, 0, 3)")
                self.assertEqual(self.evaluate('vpaPiano.state().held'),0)
                after = json.loads(self.evaluate('JSON.stringify(document.querySelector("[data-lang='+lang+']").getBoundingClientRect().toJSON())'))
                self.assertEqual(rect,after,"depressing the pedal must not move its hit box")
            self.evaluate('document.querySelector("[data-lang=en]").focus();true')
            QTest.keyClick(target,Qt.Key_Space)
            self.wait(lambda: self.evaluate('document.documentElement.lang==="en"'),3)
            self.assertFalse(self.evaluate('vpaPiano.state().sustain'),"language pedal is not an audio sustain pedal")
            self.assertEqual(self.evaluate('vpaPiano.state().held'),0)
            self.action("piano")
            self.assertGreater(self.evaluate('document.querySelector("[data-action=credits]").getBoundingClientRect().height'),0)
            self.action("credits")
            self.assertFalse(self.evaluate('document.querySelector("#notice").hidden'))
            self.assertTrue(self.evaluate('document.querySelector("#notice-text").textContent.includes("Salamander")'))
            self.action("notice-close")
        finally:
            self.window.close()
            self.app.processEvents()
            QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def test_centered_notation_playback_cursor_and_sustain(self):
        self.window = PreviewWindow(Settings())
        try:
            self.window.resize(1366,768)
            self.window.show()
            self.wait(lambda: self.evaluate('Boolean(window.vpaPreview && vpaPreview.state().ready)'))
            for width,height,size in ((1366,768,24),(960,680,40),(1920,1080,16)):
                self.window.resize(width,height)
                self.wait(lambda: self.evaluate('innerWidth==='+str(width)))
                self.evaluate(f'document.querySelector("#font-size").value={size};document.querySelector("#font-size").dispatchEvent(new Event("input"));true')
                layout = json.loads(self.evaluate('''JSON.stringify((()=>{
                    const pane=document.querySelector("#reading"),text=document.querySelector("#reading-text");
                    const p=pane.getBoundingClientRect(),r=text.getBoundingClientRect();
                    const starts=[...text.querySelectorAll('.notation-row')].map(el=>el.getBoundingClientRect().left);
                    return {offset:Math.abs((r.left+r.right)/2-(p.left+p.left+pane.clientWidth)/2),
                        align:getComputedStyle(text).textAlign,starts,overflow:pane.scrollWidth>pane.clientWidth+1};
                })())'''))
                self.assertLessEqual(layout["offset"],1,layout)
                self.assertEqual(layout["align"],"center")
                self.assertLess(max(layout["starts"])-min(layout["starts"]),1)
                self.assertFalse(layout["overflow"])
            self.window.resize(1366,768)
            self.evaluate('vpaPreview.setHeight(240);document.querySelector("#font-size").value=32;document.querySelector("#font-size").dispatchEvent(new Event("input"));vpaPiano.setSustain(true);true')
            for action in ("settings","settings","piano","piano","edit","edit"):
                self.action(action)
                self.assertTrue(self.evaluate('vpaPiano.state().sustain'),action)
            self.evaluate('document.querySelector("#tempo").value=200;document.querySelector("#tempo").dispatchEvent(new Event("change"));true')
            rect = json.loads(self.evaluate('JSON.stringify(document.querySelector("#transport-toggle").getBoundingClientRect().toJSON())'))
            target = self.window.view.focusProxy() or self.window.view
            QTest.mouseClick(target,Qt.LeftButton,Qt.NoModifier,QPoint(int(rect["x"]+rect["width"]/2),int(rect["y"]+rect["height"]/2)))
            self.wait(lambda: self.evaluate('vpaPiano.state().playing && vpaPreview.state().cursor>=6'),5)
            self.assertTrue(self.evaluate('vpaPiano.state().sustain'))
            self.assertGreater(self.evaluate('document.querySelector("#reading").scrollTop'),0)
            self.assertEqual(self.evaluate('document.querySelectorAll(".notation-token.current").length'),1)
            for lang,word in (("en","Playback position"),("de","Wiedergabeposition"),("ru","Позиция проигрывания")):
                self.evaluate(f'document.querySelector("[data-lang={lang}]").click();true')
                self.assertTrue(self.evaluate('document.querySelector("#follow-status").textContent.includes('+json.dumps(word)+')'))
            self.action("play")
            self.wait(lambda: self.evaluate('vpaPiano.state().paused && document.querySelector("#follow-status").textContent.includes("пауза")'),3)
            cursor = self.evaluate('vpaPreview.state().cursor')
            position = self.evaluate('vpaPiano.state().scorePosition')
            self.evaluate('document.querySelector("#tempo").value=50;document.querySelector("#tempo").dispatchEvent(new Event("change"));true')
            QTest.qWait(180)
            self.assertEqual(self.evaluate('vpaPreview.state().cursor'),cursor)
            self.assertEqual(self.evaluate('vpaPiano.state().scorePosition'),position)
            self.assertTrue(self.evaluate('vpaPiano.state().sustain'))
            expected = self.evaluate('vpaPreview.state().applied.tokens.filter(token=>token.start<=vpaPiano.state().scorePosition+.001).length-1')
            self.assertEqual(cursor,expected)
            self.evaluate('document.querySelector("#follow").checked=false;document.querySelector("#follow").dispatchEvent(new Event("change"));true')
            scroll = self.evaluate('document.querySelector("#reading").scrollTop')
            self.action("play")
            self.wait(lambda: self.evaluate('vpaPreview.state().cursor>'+str(cursor)),4)
            self.assertEqual(self.evaluate('document.querySelector("#reading").scrollTop'),scroll,"turning off auto-scroll does not stop the time cursor")
            self.evaluate('document.querySelector("#follow").checked=true;document.querySelector("#follow").dispatchEvent(new Event("change"));true')
            self.action("piano")
            self.assertTrue(self.evaluate('vpaPiano.state().playing && vpaPiano.state().sustain'))
            self.action("piano")
            self.action("edit")
            self.evaluate('document.querySelector("#notation").value="я я д";document.querySelector("#notation").dispatchEvent(new Event("input"));true')
            self.action("edit")
            QTest.qWait(240)
            self.assertEqual(self.evaluate('document.querySelector("#notation").value'),"я я д")
            self.assertEqual(self.evaluate('vpaPreview.state().cursor'),0,"edited text must not receive invented score timing")
            self.assertTrue(self.evaluate('document.querySelector("#follow-status").textContent.includes("Ручной текст")'))
            self.evaluate('document.querySelector("#stop").click();true')
            self.wait(lambda: self.evaluate('!vpaPiano.state().playing && !vpaPiano.state().sustain && vpaPiano.state().voices===0'),3)
            self.assertEqual(self.evaluate('vpaPreview.state().cursor'),0)
            self.evaluate('vpaPiano.setSustain(true);window.dispatchEvent(new Event("blur"));true')
            self.assertFalse(self.evaluate('vpaPiano.state().sustain'))
            if os.environ.get("VPA_CURSOR_EVIDENCE"):
                self.evaluate('vpaPreview.apply(true);true')
                self.wait(lambda: self.evaluate('!vpaPreview.state().edited'))
                QTest.qWait(200)
                self.window.view.grab().save(str(ROOT / "docs/feasibility/design-live/revision-12-centered.png"))
        finally:
            self.window.close()
            self.app.processEvents()
            QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def test_editor_centred_and_chrome_not_selectable(self):
        self.window = PreviewWindow(Settings())
        try:
            self.window.resize(1440,900)
            self.window.show()
            self.wait(lambda:self.evaluate('Boolean(window.vpaPreview && vpaPreview.state().ready)'))
            self.evaluate('document.querySelector("#notation").value="AAAA AAAA\\nAA";true')
            self.action("edit")
            data=json.loads(self.evaluate('JSON.stringify({padding:parseFloat(getComputedStyle(document.querySelector("#notation")).paddingLeft),width:document.querySelector("#notation").clientWidth,editor:getComputedStyle(document.querySelector("#notation")).userSelect,footer:getComputedStyle(document.querySelector("footer")).userSelect,key:getComputedStyle(document.querySelector(".key span")).userSelect})'))
            self.assertEqual(data["padding"],24)
            self.assertEqual(self.evaluate('getComputedStyle(document.querySelector("#notation")).textAlign'),'center')
            self.assertEqual(data["editor"],"text")
            self.assertEqual(data["footer"],"none")
            self.assertEqual(data["key"],"none")
            self.window.resize(960,680)
            self.app.processEvents()
            self.assertTrue(self.evaluate('parseFloat(getComputedStyle(document.querySelector("#notation")).paddingLeft)>=24'))
        finally:
            self.window.close();self.window.deleteLater()
            self.app.processEvents()
            QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

    def test_live_preview(self):
        self.window = PreviewWindow(Settings())
        errors = []
        self.window.page.javaScriptConsoleMessage = lambda _level, message, _line, _source: errors.append(message)
        try:
            self.window.resize(1366, 768)
            self.window.show()
            self.assertTrue(self.window.windowFlags() & Qt.FramelessWindowHint)
            self.assertFalse(self.window.windowIcon().isNull())
            self.wait(lambda: self.evaluate('Boolean(window.vpaPreview && window.vpaPiano && vpaPiano.state().ready && vpaPreview.state().ready)'))
            self.assertEqual(self.evaluate('document.querySelectorAll(".key").length'), 61)
            self.assertEqual(self.evaluate('document.querySelectorAll(".key span").length'), 61)
            self.assertTrue(self.evaluate('vpaPreview.state().tokenCount > 0'))
            self.assertTrue(self.evaluate('document.querySelector("#proposal-message").textContent.includes("совпадает")'))

            def bounds():
                return self.evaluate('JSON.stringify({width:innerWidth,height:innerHeight,scroll:document.documentElement.scrollWidth, bottom:document.querySelector("footer").getBoundingClientRect().bottom, keys:[...document.querySelectorAll(".key")].every(k=>{const r=k.getBoundingClientRect();return r.left>=0 && r.right<=innerWidth+1 && r.bottom<=innerHeight})})')
            evidence = ROOT / "docs" / "feasibility" / "design-live"
            if os.environ.get("VPA_PREVIEW_EVIDENCE"):
                evidence.mkdir(parents=True, exist_ok=True)
            for width, height, zoom in [(1366,768,1),(1920,1080,1),(1920,1080,1.25),(1920,1080,1.5),(960,680,1)]:
                self.window.resize(width,height)
                self.window.view.setZoomFactor(zoom)
                self.wait(lambda: self.evaluate('Math.abs(innerWidth-'+str(width/zoom)+')<2'))
                QTest.qWait(160)
                self.evaluate('vpaPreview.setHeight(156); true')
                data = json.loads(bounds())
                self.assertLessEqual(data["scroll"], data["width"]+1, (width,height,zoom,data))
                self.assertTrue(data["keys"], (width,height,zoom,data))
                self.assertLessEqual(data["bottom"], data["height"]+1, (width,height,zoom,data))
                if os.environ.get("VPA_PREVIEW_EVIDENCE"):
                    self.window.view.grab()
                    QTest.qWait(100)
                    self.window.view.grab().save(str(evidence / f"revision-7-{width}-{zoom}.png"))
            self.window.resize(1366,768)
            self.window.view.setZoomFactor(1)
            self.action("settings")
            self.assertFalse(self.evaluate('document.querySelector("#settings-overlay").hidden'))
            self.assertTrue(self.evaluate('document.querySelector(".app").inert'))
            self.assertTrue(self.evaluate('document.querySelector("#settings").closest("#settings-overlay")!==null'))
            self.assertTrue(self.evaluate('getComputedStyle(document.querySelector("#settings-overlay")).position==="fixed"'))
            self.assertGreater(self.evaluate('document.querySelector("#settings").getBoundingClientRect().width'),600)
            self.assertTrue(self.evaluate('document.activeElement.closest("#settings")!==null'))
            for lang in ("de", "en", "ru"):
                self.evaluate('document.querySelector(\'[data-lang="'+lang+'"]\').click(); true')
                self.assertEqual(self.evaluate('document.documentElement.lang'),lang)
                self.assertTrue(self.evaluate('document.documentElement.scrollWidth <= innerWidth+1'))
                if os.environ.get("VPA_PREVIEW_EVIDENCE") and lang=="de":
                    QTest.qWait(150)
                    self.window.view.grab().save(str(evidence / "revision-7-settings-de.png"))
            self.evaluate('document.querySelector("#font-size").value=40; document.querySelector("#font-size").dispatchEvent(new Event("input")); true')
            self.assertEqual(self.evaluate('document.querySelector("#font-value").textContent'),"40")
            self.evaluate('document.querySelector("#fullness").value=0; document.querySelector("#fullness").dispatchEvent(new Event("input")); true')
            self.wait(lambda: self.evaluate('vpaPreview.state().proposal.fullness===0'))
            old = self.evaluate('document.querySelector("#notation").value')
            self.assertEqual(self.evaluate('vpaPreview.state().applied.fullness'),100)
            self.action("apply")
            self.wait(lambda: self.evaluate('vpaPreview.state().applied.fullness===0'))
            self.assertNotEqual(self.evaluate('document.querySelector("#notation").value'),old)
            self.action("settings")
            self.action("edit")
            self.evaluate('document.querySelector("#notation").value="мои правки"; document.querySelector("#notation").dispatchEvent(new Event("input")); true')
            target = self.window.view.focusProxy() or self.window.view
            QTest.keyPress(target, Qt.Key_T)
            self.assertEqual(self.evaluate('vpaPiano.state().held'),0,"editor must not play notes")
            QTest.keyRelease(target, Qt.Key_T)
            self.action("settings")
            self.action("apply")
            self.assertFalse(self.evaluate('document.querySelector("#conflict").hidden'))
            self.action("keep")
            self.assertTrue(self.evaluate('document.querySelector("#notation").value.startsWith("мои правки")'))
            self.action("apply"); self.action("replace")
            self.wait(lambda: self.evaluate('!vpaPreview.state().edited'))
            self.action("settings")
            self.action("edit")

            self.action("play")
            self.wait(lambda: self.evaluate('vpaPiano.state().playing'))
            self.action("settings")
            self.assertTrue(self.evaluate('vpaPiano.state().playing'),"opening settings preserves the score")
            self.assertEqual(self.evaluate('vpaPiano.state().held'),0)
            self.evaluate('document.querySelector("#transpose").focus(); document.activeElement.dispatchEvent(new KeyboardEvent("keydown",{code:"Numpad6",key:"ArrowRight",location:3,bubbles:true,cancelable:true}));true')
            self.assertEqual(self.evaluate('vpaPiano.state().held'),0,"settings input is not a piano key")
            self.action("settings")
            self.evaluate('vpaPiano.press(64,"test-manual"); true')
            self.action("piano")
            self.assertTrue(self.evaluate('document.querySelector("#piano-body").hidden'))
            self.assertTrue(self.evaluate('vpaPiano.state().playing'))
            self.assertEqual(self.evaluate('vpaPiano.state().held'),0)
            self.action("piano")
            self.evaluate('vpaPiano.setReverb("hall",50); document.querySelector("#volume").dispatchEvent(new Event("input")); true')
            self.assertTrue(self.evaluate('vpaPiano.state().playing'))
            self.evaluate('document.querySelector("#tempo").value=150; document.querySelector("#tempo").dispatchEvent(new Event("change")); true')
            self.assertTrue(self.evaluate('vpaPiano.state().playing'))
            self.action("play")
            self.assertTrue(self.evaluate('vpaPiano.state().paused'))
            self.action("play")
            self.wait(lambda: self.evaluate('vpaPiano.state().playing'))
            self.evaluate('document.querySelector("#stop").click(); true')
            self.assertFalse(self.evaluate('vpaPiano.state().playing'))
            self.action("follow-reset")
            self.evaluate('const first=vpaPreview.state().applied.tokens[0]; first.pitches.forEach(p=>vpaPiano.press(p,"follow-"+p)); true')
            self.assertEqual(self.evaluate('vpaPreview.state().cursor'),1,"held chord advances once complete")
            self.evaluate('vpaPiano.releaseManual(); document.querySelector("#keys").focus(); true')
            QTest.keyPress(target,Qt.Key_T)
            self.wait(lambda: self.evaluate('vpaPiano.state().held===1'),3)
            self.assertEqual(self.evaluate('vpaPiano.state().held'),1,self.evaluate('JSON.stringify({editing:vpaPreview.state().editing,settings:vpaPreview.state().settings,focus:document.activeElement.id,canPlay:vpaPianoHost.canPlay()})'))
            QTest.keyRelease(target,Qt.Key_T)
            self.wait(lambda: self.evaluate('vpaPiano.state().held===0 && !document.querySelector(\'.key[data-midi="60"]\').classList.contains("active")'),3)
            navigation = ["Insert", "End", "ArrowDown", "PageDown", "ArrowLeft", "Clear", "ArrowRight", "Home", "ArrowUp", "PageUp"]
            for digit, alternate in enumerate(navigation):
                for numlock, key, code in ((True, str(digit), f"Numpad{digit}"), (False, alternate, f"Numpad{digit}"), (False, alternate, alternate)):
                    payload = json.dumps({"code": code, "key": key, "digit": digit, "location": 3, "bubbles": True, "cancelable": True, "numlock": numlock})
                    result = json.loads(self.evaluate('''JSON.stringify((()=>{
                        const info='''+payload+''';
                        const down=new KeyboardEvent("keydown",info),keys=document.querySelector("#keys");
                        Object.defineProperty(down,"getModifierState",{value:name=>name==="NumLock"&&info.numlock});
                        keys.dispatchEvent(down);
                        const midi=Number(Object.keys(vpaPianoHost.mapping).find(p=>vpaPianoHost.mapping[p].key===String(info.digit)&&!vpaPianoHost.mapping[p].shift));
                        const result={held:vpaPiano.state().held,active:document.querySelector('.key[data-midi="'+midi+'"]').classList.contains("active"),prevented:down.defaultPrevented};
                        keys.dispatchEvent(new KeyboardEvent("keyup",info));result.released=vpaPiano.state().held;
                        return result;
                    })())'''))
                    self.assertEqual(result, {"held": 1, "active": True, "prevented": True, "released": 0}, (digit, numlock, code))
            self.evaluate('document.querySelector("#keys").dispatchEvent(new KeyboardEvent("keydown",{code:"ArrowRight",key:"ArrowRight",location:0,bubbles:true}));true')
            self.assertEqual(self.evaluate('vpaPiano.state().held'),0,"ordinary navigation is not a keypad note")
            self.evaluate('document.querySelector("#keys").dispatchEvent(new KeyboardEvent("keydown",{code:"Digit6",key:"6",bubbles:true})); document.querySelector("#keys").dispatchEvent(new KeyboardEvent("keydown",{code:"Numpad6",key:"ArrowRight",bubbles:true}));true')
            self.assertEqual(self.evaluate('vpaPiano.state().held'),2)
            self.evaluate('document.querySelector("#keys").dispatchEvent(new KeyboardEvent("keyup",{code:"Digit6",bubbles:true}));true')
            self.assertEqual(self.evaluate('vpaPiano.state().held'),1,"releasing one alias preserves the other")
            self.evaluate('document.querySelector("#keys").dispatchEvent(new KeyboardEvent("keyup",{code:"Numpad6",bubbles:true}));true')
            self.assertEqual(self.evaluate('vpaPiano.state().held'),0)
            # Also exercise the Qt -> Chromium event path, not only DOM events.
            self.evaluate('document.querySelector("#keys").focus();window.__keyInfo=null;document.addEventListener("keydown",e=>window.__keyInfo=JSON.stringify({code:e.code,key:e.key,location:e.location,canPlay:vpaPianoHost.canPlay()}),{once:true});true')
            QTest.keyPress(target,Qt.Key_6,Qt.KeypadModifier)
            self.wait(lambda: self.evaluate('Boolean(window.__keyInfo)'),3)
            self.assertEqual(self.evaluate('vpaPiano.state().held'),1,self.evaluate('window.__keyInfo'))
            QTest.keyRelease(target,Qt.Key_6,Qt.KeypadModifier)
            self.wait(lambda: self.evaluate('vpaPiano.state().held===0'),3)
            self.assertEqual(self.evaluate('vpaPiano.state().held'),0)
            self.evaluate('window.__keyInfo=null;document.addEventListener("keydown",e=>window.__keyInfo=JSON.stringify({code:e.code,key:e.key,location:e.location}),{once:true});true')
            QTest.keyPress(target,Qt.Key_Right,Qt.KeypadModifier)
            self.wait(lambda: self.evaluate('Boolean(window.__keyInfo)'),3)
            self.assertEqual(self.evaluate('vpaPiano.state().held'),1,self.evaluate('window.__keyInfo'))
            QTest.keyRelease(target,Qt.Key_Right,Qt.KeypadModifier)
            self.wait(lambda: self.evaluate('vpaPiano.state().held===0'),3)
            self.action("edit")
            self.evaluate('document.querySelector("#notation").dispatchEvent(new KeyboardEvent("keydown",{code:"Numpad6",key:"6",bubbles:true}));true')
            self.assertEqual(self.evaluate('vpaPiano.state().held'),0)
            self.action("edit")
            self.evaluate('document.querySelector("#key-labels").value="de";document.querySelector("#key-labels").dispatchEvent(new Event("change"));true')
            self.assertEqual(self.evaluate('document.querySelector(\'.key[data-midi="86"] span\').textContent'),"y")
            self.evaluate('document.querySelector("#key-labels").value="none";document.querySelector("#key-labels").dispatchEvent(new Event("change"));true')
            self.assertTrue(self.evaluate('[...document.querySelectorAll(".key span")].every(s=>s.textContent==="")'))
            self.evaluate('document.querySelector("#key-labels").value="ru";document.querySelector("#key-labels").dispatchEvent(new Event("change"));true')
            self.evaluate('vpaPreview.setHeight(240,true); true')
            self.assertGreaterEqual(self.window.settings.data["key-height"],112)

            # Button hit box stays fixed while only its visual surface moves.
            self.assertIn("0.13s",self.evaluate('getComputedStyle(document.querySelector("[data-action=open]"),"::before").transitionDuration'))
            # Offscreen Chromium has no exposed compositor clock. Check the real
            # hover/press target geometry without depending on animation frames.
            self.evaluate('const css=document.createElement("style");css.textContent=".gold-key::before,.gold-label{transition:none!important}";document.head.append(css);true')
            rect = json.loads(self.evaluate('JSON.stringify(document.querySelector("[data-action=open]").getBoundingClientRect().toJSON())'))
            QTest.mouseMove(target,QPoint(int(rect["x"]+rect["width"]/2),int(rect["y"]+rect["height"]/2)))
            point = QPoint(int(rect["x"]+rect["width"]/2),int(rect["y"]+rect["height"]/2))
            self.app.sendEvent(target,QMouseEvent(QEvent.MouseMove,QPointF(point),QPointF(target.mapToGlobal(point)),Qt.NoButton,Qt.NoButton,Qt.NoModifier))
            QTest.qWait(180)
            after = json.loads(self.evaluate('JSON.stringify(document.querySelector("[data-action=open]").getBoundingClientRect().toJSON())'))
            self.assertEqual(rect,after)
            hover_info = self.evaluate('JSON.stringify({hover:document.querySelector("[data-action=open]").matches(":hover"),reduced:matchMedia("(prefers-reduced-motion:reduce)").matches,down:getComputedStyle(document.querySelector("[data-action=open]")).getPropertyValue("--key-down")})')
            self.assertEqual(self.evaluate('getComputedStyle(document.querySelector("[data-action=open]"),"::before").transform'),"matrix(1, 0, 0, 1, 0, 2)",hover_info)
            QTest.mousePress(target,Qt.LeftButton,Qt.NoModifier,QPoint(int(rect["x"]+10),int(rect["y"]+10)))
            QTest.qWait(160)
            self.assertEqual(self.evaluate('getComputedStyle(document.querySelector("[data-action=open]"),"::before").transform'),"matrix(1, 0, 0, 1, 0, 4)")
            QTest.mouseRelease(target,Qt.LeftButton,Qt.NoModifier,QPoint(int(rect["x"]+10),int(rect["y"]+10)))
            self.action("notice-close")

            pcm = {}
            for name,preset,amount in [("dry","off",50),("zero","hall",0),("room","room",50),("hall","hall",50)]:
                self.evaluate('window.__audio=null; vpaPiano.renderDemo({preset:"'+preset+'",amount:'+str(amount)+'}).then(r=>window.__audio=JSON.stringify(r)); true')
                self.wait(lambda: self.evaluate('Boolean(window.__audio)'),30)
                result = json.loads(self.evaluate('window.__audio'))
                self.assertGreater(result["rms"],.001)
                self.assertLess(result["peak"],.999)
                if name in ("dry","zero"):
                    self.assertEqual((result["dryGain"],result["wetGain"]),(1,0))
                raw = base64.b64decode(result["wave"])
                with wave.open(io.BytesIO(raw)) as wav:
                    pcm[name] = array.array("h",wav.readframes(wav.getnframes()))
                if os.environ.get("VPA_PREVIEW_EVIDENCE") and name!="zero":
                    (evidence / f"reverb-{name}.wav").write_bytes(raw)
                print(f"REVERB {name}: peak={result['peak']:.4f}, rms={result['rms']:.4f}",flush=True)
            # Independent Chromium renders can round at a different 16-bit
            # boundary. Verify zero wet gain and at most one quantisation step.
            delta=max(abs(a-b) for a,b in zip(pcm["dry"],pcm["zero"]))
            self.assertLessEqual(delta,1,"0% must bypass added reverb")
            print(f"REVERB bypass max delta: {delta} / 32768",flush=True)
            self.assertNotEqual(pcm["dry"],pcm["room"])
            self.assertNotEqual(pcm["room"],pcm["hall"])
            tail = lambda samples: sum(x*x for x in samples[-192000:])
            self.assertGreater(tail(pcm["hall"]),tail(pcm["room"]))
            self.assertEqual(self.window.interceptor.blocked,[])
            self.assertFalse(any("Uncaught" in error or "TypeError" in error for error in errors),errors)
            self.evaluate('document.querySelector("[data-window=maximize]").click();true')
            self.wait(lambda: self.window.isMaximized())
            self.wait(lambda: self.evaluate('document.documentElement.classList.contains("maximized")'))
            self.evaluate('document.querySelector("[data-window=maximize]").click();true')
            self.wait(lambda: not self.window.isMaximized())
            self.evaluate('document.querySelector("[data-window=minimize]").click();true')
            self.wait(lambda: self.window.isMinimized())
            self.window.showNormal()
            self.evaluate('document.querySelector("[data-window=close]").click();true')
            self.wait(lambda: self.window.closed)
        finally:
            self.window.close()
            self.app.processEvents()
            QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


if __name__ == "__main__":
    unittest.main()
