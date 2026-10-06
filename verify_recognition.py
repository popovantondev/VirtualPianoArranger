"""Opt-in real OMR smoke test; copies source, prints no personal paths."""
import argparse
import json
from fractions import Fraction
from pathlib import Path
import time
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication
from music_time import read_musicxml, merge_scores
from recognition import HomrWorker, runtime_executable, homr_command
from omr_quality import result_warnings


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("image",type=Path,nargs="+")
    parser.add_argument("--timeout",type=int,default=180)
    parser.add_argument("--offline-proof",action="store_true",help="Disable child socket connections for this test")
    parser.add_argument("--expected-quarter-beats",type=Fraction,help="Known source duration for every bar; verification only, never changes notes")
    parser.add_argument("--expected-page-measures",type=lambda value:[int(n) for n in value.split(",")],help="Known source measure counts, comma-separated")
    args=parser.parse_args()
    if args.expected_quarter_beats is not None and args.expected_quarter_beats<=0:parser.error("Expected beat count must be positive")
    if args.expected_page_measures is not None and any(n<=0 for n in args.expected_page_measures):parser.error("Expected measure counts must be positive")
    app=QCoreApplication([])
    worker=HomrWorker(runtime_executable(Path(__file__).resolve().parent),args.image)
    result={};start=time.monotonic()
    def success(paths,_log):
        try:
            scores=[read_musicxml(path) for path in paths]
            reports=[json.loads(Path(path).with_suffix(".recognition.json").read_text(encoding="utf-8")) for path in paths]
            for page,(path,score) in enumerate(zip(paths,scores),1):score["warnings"].extend(result_warnings(path,page,"English"))
            score=scores[0] if len(scores)==1 else merge_scores(scores)
            result.update(ok=True,notes=len(score["notes"]),measures=len(score["measures"]),
                          pages=len(scores),exact=score["exact"],warnings=score["warnings"],
                          pageMeasures=[len(s["measures"]) for s in scores],
                          pageStaves=[sorted({n["staff"] for n in s["notes"]}) for s in scores],
                          quality=[report.get("quality") for report in reports])
            if args.expected_quarter_beats is not None:
                mismatches=[{"page":page,"measure":index,"actual":measure["duration"]}
                            for page,s in enumerate(scores,1) for index,measure in enumerate(s["measures"],1)
                            if Fraction(*measure["duration"])!=args.expected_quarter_beats]
                result["beatVerification"]={"expected":[args.expected_quarter_beats.numerator,args.expected_quarter_beats.denominator],
                                            "checked":sum(len(s["measures"]) for s in scores),"mismatches":mismatches}
                if mismatches:result["ok"]=False
            if args.expected_page_measures is not None:
                result["pageCountVerified"]=result["pageMeasures"]==args.expected_page_measures
                if not result["pageCountVerified"]:result["ok"]=False
        except Exception as error:result.update(ok=False,error=type(error).__name__)
    worker.done.connect(lambda path,log:success([path],log))
    worker.batchDone.connect(success)
    worker.failed.connect(lambda text:result.update(ok=False,error=text[-1000:]))
    worker.cancelled.connect(lambda:result.update(ok=False,error="cancelled or timed out"))
    worker.stage.connect(lambda stage:print(stage,flush=True))
    worker.page.connect(lambda index,total:print(f"page {index}/{total}",flush=True))
    def command(exe,image):
        args_command=homr_command(exe,image)
        if args.offline_proof:
            args_command[args_command.index("-c")+1]="import socket;socket.socket.connect=lambda *a:(_ for _ in ()).throw(OSError('Network disabled for offline test'));"+args_command[args_command.index("-c")+1]
        return args_command
    with patch("recognition.homr_command",command):
        worker.start()
        while worker.isRunning():
            app.processEvents()
            if time.monotonic()-start>args.timeout:worker.cancel()
            time.sleep(.02)
    app.processEvents();worker.cleanup()
    result["cleaned"]=worker._directory is None
    result["seconds"]=round(time.monotonic()-start,2)
    # Windows legacy console encodings cannot print every musical/arrow mark.
    print(json.dumps(result,ensure_ascii=True))
    return 0 if result.get("ok") else 1


if __name__=="__main__":raise SystemExit(main())
