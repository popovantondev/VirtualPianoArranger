"""Explicit, isolated EXE smoke mode; never opens the owner's projects."""
import json
import os
from pathlib import Path
import subprocess
import time
import tempfile

from PySide6.QtCore import QObject, QTimer, QSize, Qt
from PySide6.QtGui import QPainter, QPdfWriter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication
from shiboken6 import delete as delete_qt_object

from project_io import atomic_write_text
from recognition import homr_command


class StudioSmoke(QObject):
    def __init__(self, window, report):
        super().__init__(window)
        self.window, self.report = window, report
        self.started=time.monotonic();self.pending=False;self.finished=False
        self.errors=[]
        window.page.javaScriptConsoleMessage=lambda _level,message,_line,_source:self.errors.append(message[:500])
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(200)

    def finish(self, data, code):
        if self.finished:return
        self.finished=True;self.timer.stop()
        data["seconds"]=round(time.monotonic()-self.started,2)
        try:atomic_write_text(self.report,json.dumps(data,ensure_ascii=False,indent=2))
        except OSError:code=3
        QApplication.instance().exit(code)

    def poll(self):
        if time.monotonic()-self.started>35:
            self.finish({"ok":False,"error":"Studio WebEngine timed out","console":self.errors[-5:]},1);return
        if self.pending:return
        self.pending=True
        self.window.page.runJavaScript('''JSON.stringify({
            active:Boolean(window.vpaDocument?.active),ready:Boolean(window.vpaPreview?.state().ready),
            keys:document.querySelectorAll('.key').length,
            empty:document.getElementById('notation')?.value==='',
            samples:window.vpaPiano?.state().cached||0,
            language:document.documentElement?.lang||'',
            font:document.querySelector('.brand-icon')?.getAttribute('src')
        })''',self.probe)

    def probe(self, raw):
        self.pending=False
        if self.finished:return
        try:data=json.loads(raw or "{}")
        except (ValueError,TypeError):return
        if not data.get("active") or not data.get("ready"):return
        if any("Uncaught" in message for message in self.errors):
            self.finish({"ok":False,"error":"Unhandled Studio JavaScript error","console":self.errors[-5:]},1);return
        if data.get("keys")!=61 or not data.get("empty") or data.get("samples",0)<30:
            self.finish({"ok":False,"error":"Incomplete Studio resources","ui":data},1);return
        try:
            # Exercise actual QtPdf/PDFium loading and rasterization, not just
            # an import. This original one-page fixture uses no owner document.
            with tempfile.TemporaryDirectory(prefix="vpa-pdf-smoke-") as folder:
                pdf_path = str(Path(folder) / "original-demo.pdf")
                writer = QPdfWriter(pdf_path)
                writer.setResolution(72)
                painter = QPainter(writer)
                painter.fillRect(20, 20, 120, 80, Qt.GlobalColor.black)
                painter.end()
                del painter
                del writer
                document = QPdfDocument(self)
                try:
                    if document.load(pdf_path) != QPdfDocument.Error.None_ or document.pageCount() != 1:
                        raise RuntimeError("Packaged QtPdf could not open the original fixture")
                    image = document.render(0, QSize(160, 220))
                    if image.isNull() or not any(
                        image.pixelColor(x, y).alpha() > 0 and image.pixelColor(x, y).lightness() < 100
                        for x in range(image.width()) for y in range(image.height())
                    ):
                        raise RuntimeError("Packaged QtPdf did not rasterize the fixture")
                finally:
                    document.close()
                    delete_qt_object(document)
            exe=self.window.bridge.controller.homr_exe()
            args=homr_command(exe,Path("unused-smoke-input.png"))
            packages=str(exe.parent.parent/"site-packages")
            command=[str(exe),"-I","-c",
                     "import sys;sys.path.insert(0,sys.argv[1]);sys.path.insert(1,sys.argv[2]);"
                     "import homr.main;import onnxruntime;import homr_runner;"
                     "import xml.etree.ElementTree as ET;ET.fromstring('<score-partwise/>');"
                     "print('HOMR_IMPORT_OK')",
                     packages,str(Path(args[-2]).parent)]
            process=subprocess.run(command,capture_output=True,text=True,timeout=30,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
            if process.returncode or "HOMR_IMPORT_OK" not in process.stdout:
                raise RuntimeError("Bundled recognition imports failed: "+process.stderr[-1500:])
        except (OSError,RuntimeError,subprocess.TimeoutExpired) as error:
            self.finish({"ok":False,"ui":data,"error":str(error)},1);return
        self.finish({"ok":True,"ui":data,"pdfRendered":True,"recognitionImports":True,"recognitionXml":True,"console":self.errors[-5:]},0)
