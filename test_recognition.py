import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtWidgets import QApplication
from recognition import HomrWorker, homr_command, runtime_executable

ROOT = Path(__file__).resolve().parent


class RecognitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def run_job(self, mode, cancel=False):
        with tempfile.TemporaryDirectory(prefix="vpa-omr-test-") as folder:
            source = Path(folder)/"source.png"
            source.write_text(mode)
            old_xml = source.with_suffix(".musicxml")
            old_xml.write_text("old result")
            worker = HomrWorker(sys.executable, source)
            results, errors, cancelled, stages, logs = [], [], [], [], []
            worker.done.connect(lambda path,log:results.append((path,Path(path).read_text())))
            worker.failed.connect(errors.append)
            worker.cancelled.connect(lambda:cancelled.append(True))
            worker.stage.connect(stages.append);worker.log.connect(logs.append)
            command=lambda _exe,image:[sys.executable,"-u",str(ROOT/"tests/fixtures/mock_homr.py"),str(image)]
            start=time.monotonic()
            with patch("recognition.homr_command",command):
                worker.start()
                while worker.isRunning():
                    self.app.processEvents()
                    if cancel and "processing" in stages:worker.cancel()
                    if time.monotonic()-start>12:
                        worker.cancel();worker.wait(6000);self.fail("Job timed out")
                    time.sleep(.01)
                self.app.processEvents()
            self.assertEqual(source.read_text(),mode)
            self.assertEqual(old_xml.read_text(),"old result")
            job_folder=Path(worker._directory.name)
            worker.cleanup()
            self.assertFalse(job_folder.exists())
            return results,errors,cancelled,stages,logs,time.monotonic()-start

    def test_success_uses_fresh_isolated_result(self):
        result,error,cancelled,stages,_,_=self.run_job("success")
        self.assertEqual(len(result),1);self.assertEqual(result[0][1],"<score-partwise/>")
        self.assertFalse(error or cancelled);self.assertIn("reading",stages)

    def test_failure_never_imports_previous_xml(self):
        result,error,_,_,_,_=self.run_job("fail")
        self.assertFalse(result);self.assertIn("controlled failure",error[0])

    def test_missing_result_is_failure_even_with_old_xml(self):
        result,error,_,_,_,_=self.run_job("missing")
        self.assertFalse(result);self.assertIn("no MusicXML",error[0])

    def test_cancel_stops_process_and_retry_succeeds(self):
        result,error,cancelled,_,_,duration=self.run_job("wait",True)
        self.assertFalse(result or error);self.assertTrue(cancelled);self.assertLess(duration,5)
        self.assertTrue(self.run_job("success")[0])

    def test_log_is_bounded(self):
        result,error,_,_,logs,_=self.run_job("log")
        self.assertTrue(result);self.assertFalse(error);self.assertLessEqual(len(logs[0]),5000)

    def test_portable_command_is_isolated(self):
        with tempfile.TemporaryDirectory(prefix="vpa-runtime-test-") as folder:
            base=Path(folder).resolve()
            exe=base/"python/python.exe"
            (base/"site-packages/homr").mkdir(parents=True)
            (base/"site-packages/homr/main.py").touch()
            for directory,names in (("homr/segmentation",["segnet_test.onnx"]),("homr/transformer",["encoder_test.onnx","decoder_test.onnx"]),("rapidocr/models",["det.onnx","rec.onnx","cls.onnx"])):
                target=base/"site-packages"/directory;target.mkdir(parents=True,exist_ok=True)
                for name in names:(target/name).write_bytes(b"test")
            command=homr_command(exe,ROOT/"input.png")
            self.assertIn("-I",command)
            self.assertNotIn("0.3", " ".join(command))
            self.assertIn("site-packages",command[-3])
            self.assertEqual(Path(command[-2]).name,"homr_runner.py")
            existing=Path.is_file
            for helper in ("omr_quality.py","omr_duration.py","omr_timing.py","omr_heads.py","omr_notation.py","omr_meter.py"):
                with patch.object(Path,"is_file",lambda path:False if path.name==helper else existing(path)):
                    with self.assertRaisesRegex(RuntimeError,"runner is missing"):homr_command(exe,ROOT/"input.png")
            host=base/"_internal";isolated=host/"recognition_app"
            isolated.mkdir(parents=True)
            helpers=("homr_runner.py","omr_layout.py","omr_quality.py","omr_duration.py","omr_timing.py","omr_heads.py","omr_notation.py","omr_meter.py")
            for helper in helpers:
                (isolated/helper).touch();(host/helper).touch()
            with patch("recognition.__file__",str(host/"recognition.py")),patch("recognition.sys.frozen",True,create=True):
                frozen=homr_command(exe,ROOT/"input.png")
                self.assertEqual(Path(frozen[-2]).parent,isolated)
                # Root copies cannot silently substitute a missing isolated runner.
                with patch.object(Path,"is_file",lambda path:False if path==isolated/"omr_notation.py" else existing(path)):
                    with self.assertRaisesRegex(RuntimeError,"runner is missing"):homr_command(exe,ROOT/"input.png")

    def test_batch_is_atomic_and_cancelled_between_pages(self):
        with tempfile.TemporaryDirectory(prefix="vpa-batch-test-") as folder:
            sources=[Path(folder)/f"page-{i}.png" for i in range(2)]
            command=lambda _exe,image:[sys.executable,"-u",str(ROOT/"tests/fixtures/mock_homr.py"),str(image)]
            for mode in ("success","fail","wait"):
                sources[0].write_text("success");sources[1].write_text(mode)
                worker=HomrWorker(sys.executable,sources);results=[];errors=[];cancelled=[];pages=[];single=[]
                worker.done.connect(lambda *_:single.append(True))
                worker.batchDone.connect(lambda paths,_log:results.append([Path(p).read_text() for p in paths]))
                worker.failed.connect(errors.append);worker.cancelled.connect(lambda:cancelled.append(True))
                worker.page.connect(lambda index,total:pages.append((index,total)))
                with patch("recognition.homr_command",command):
                    worker.start();start=time.monotonic()
                    while worker.isRunning():
                        self.app.processEvents()
                        if mode=="wait" and (2,2) in pages:worker.cancel()
                        if time.monotonic()-start>12:worker.cancel();worker.wait(6000);self.fail("Batch timed out")
                        time.sleep(.01)
                    self.app.processEvents()
                self.assertEqual(pages,[(1,2),(2,2)]);self.assertFalse(single)
                if mode=="success":self.assertEqual(results,[["<score-partwise/>"]*2]);self.assertFalse(errors or cancelled)
                else:self.assertFalse(results);self.assertTrue(errors if mode=="fail" else cancelled)
                directory=Path(worker._directory.name);worker.cleanup();self.assertFalse(directory.exists())
                self.assertEqual(sources[1].read_text(),mode)

    def test_meter_context_is_sequential_validated_and_reset_per_job(self):
        import json
        with tempfile.TemporaryDirectory(prefix='vpa-meter-worker-test-') as folder:
            source=Path(folder)/'source.png';source.write_text('unchanged')
            worker=HomrWorker(sys.executable,[source]*3);seen=[]
            contexts=[{'beats':4,'beatType':4},{'beats':True,'beatType':4},None]
            def recognize(_source,directory):
                seen.append(worker._meter_context)
                path=directory/'score.musicxml';path.write_text('<score-partwise/>')
                context=contexts[(len(seen)-1)%3]
                path.with_suffix('.recognition.json').write_text(json.dumps({'quality':{'meterContext':context}}))
                return str(path),''
            with patch.object(worker,'_recognize_one',side_effect=recognize):
                worker.run();worker.cleanup()
                worker._meter_context={'beats':3,'beatType':4}
                worker.run();worker.cleanup()
            self.assertEqual(seen,[None,{'beats':4,'beatType':4},None]*2)
            self.assertEqual(source.read_text(),'unchanged')

    def test_missing_runtime_is_not_implicitly_downloaded(self):
        with tempfile.TemporaryDirectory(prefix="vpa-runtime-test-") as folder:
            base=Path(folder);(base/"site-packages/homr").mkdir(parents=True)
            (base/"site-packages/homr/main.py").touch()
            with self.assertRaisesRegex(RuntimeError,"local models"):
                homr_command(base/"python/python.exe",base/"input.png")

    def test_quality_warnings_are_installed_and_saved_per_page_without_webengine(self):
        import json
        import xml.etree.ElementTree as ET
        from PySide6.QtWidgets import QWidget
        from studio_ui import DocumentController
        from test_design_preview import Settings
        from test_omr_quality import score_xml
        from omr_quality import rhythm_report
        from project_io import write_project,read_project
        with tempfile.TemporaryDirectory(prefix="vpa-quality-controller-") as folder:
            paths=[]
            for index in (1,2):
                path=Path(folder)/f"page-{index}.musicxml";root=score_xml([12,18],(4,4))
                ET.ElementTree(root).write(path);paths.append(str(path))
                report=rhythm_report(root)
                report["durationCorrections"]=[{"measure":2,"from":"note_2","to":"note_4"}]
                report["timingCorrections"]=[{"measure":2,"movedNotes":2}]
                report["tieCorrections"]=[{"measure":2}]
                report["heldNoteRecoveries"]=[{"measure":2}]
                path.with_suffix(".recognition.json").write_text(json.dumps({"quality":report}))
            before=[Path(p).read_bytes() for p in paths]
            for language,label,timing in (("Русский","страница","синхронизация"),("English","page","synchronization"),("Deutsch","Seite","Synchronisation")):
                shell=QWidget();controller=DocumentController(shell,Settings())
                controller.ui_lang.setCurrentText(language)
                controller.recognition_batch_done(paths,"")
                self.assertEqual(controller.recognition_stage,"done")
                warnings="\n".join(controller.musical_score["warnings"])
                self.assertIn(label+" 1",warnings);self.assertIn(label+" 2",warnings)
                self.assertIn(timing,warnings)
                self.assertIn({"Русский":"связки удержания","English":"held-note ties","Deutsch":"Haltebögen"}[language],warnings)
                self.assertIn({"Русский":"пропущенные продолжения","English":"missing held-note continuations","Deutsch":"fehlende Fortsetzungen"}[language],warnings)
                project=Path(folder)/"result.vpa.json";write_project(project,controller.collect_state())
                self.assertEqual(read_project(project)["musical_score"]["warnings"],controller.musical_score["warnings"])
                shell.deleteLater();self.app.processEvents()
            self.assertEqual([Path(p).read_bytes() for p in paths],before)


if __name__=="__main__":unittest.main()
