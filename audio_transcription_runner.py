"""Prepared Basic Pitch child entry point. Requires a separate approved runtime.

No model download or dependency installation. Input is pre-extracted PCM WAV;
stdout is one bounded draft/error JSON, diagnostic/model output goes stderr.
Not yet wired to the app or packaged as an operational feature.
"""
import contextlib
import json
from pathlib import Path
import sys
from audio_transcription import note_draft,wav_duration


def predict_draft(wav,model):
    duration=wav_duration(wav)
    if not Path(model).is_file():raise ValueError('A local approved model file is required')
    # Imported only inside the separately prepared inference child.
    with contextlib.redirect_stdout(sys.stderr):
        from basic_pitch.inference import predict
        _,_,events=predict(str(wav),model_or_model_path=str(model))
    clean=[(float(a),float(b),int(p),float(activation),bends) for a,b,p,activation,bends in events]
    return note_draft(clean,duration,Path(wav).name)


def main(argv):
    try:
        if len(argv)!=2:raise ValueError('Expected local WAV and model paths')
        result={'ok':True,'draft':predict_draft(*argv)};code=0
    except ModuleNotFoundError:
        result={'ok':False,'code':'engine_missing','message':'Separate Basic Pitch runtime is not prepared.'};code=2
    except (ValueError,OSError,RuntimeError) as error:
        result={'ok':False,'code':'transcription_failed','message':str(error)[:1000]};code=1
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    return code


if __name__=='__main__':sys.exit(main(sys.argv[1:]))
