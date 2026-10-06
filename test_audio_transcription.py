import math
from pathlib import Path
import tempfile
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import patch
from audio_transcription import youtube_source,segment,extraction_command,note_draft,wav_duration


class AudioPreparationTests(unittest.TestCase):
    def test_prepared_runner_with_mock_backend_not_real_inference(self):
        from audio_transcription_runner import predict_draft
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);wav=root/'source.wav';model=root/'fixture.onnx';model.write_bytes(b'fixture')
            with wave.open(str(wav),'wb') as stream:
                stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(22050);stream.writeframes(b'\0\0'*22050)
            calls=[]
            def predict(path,model_or_model_path):
                calls.append((path,model_or_model_path));return {},None,[(0,.5,60,.8,None)]
            with patch.dict('sys.modules',{'basic_pitch':SimpleNamespace(),
                    'basic_pitch.inference':SimpleNamespace(predict=predict)}):
                draft=predict_draft(wav,model)
            self.assertEqual(calls,[(str(wav),str(model))]);self.assertFalse(draft['exact'])
            self.assertEqual(draft['notes'][0]['pitch'],60)

    def test_youtube_link_is_only_validated_not_fetched(self):
        expected='https://www.youtube.com/watch?v=TL1v3KVi6go'
        self.assertEqual(youtube_source(expected),expected)
        self.assertEqual(youtube_source('https://youtu.be/TL1v3KVi6go?t=2'),expected)
        for url in ('http://youtube.com/watch?v=TL1v3KVi6go','https://127.0.0.1/video',
                    'https://youtube.com.evil.org/watch?v=TL1v3KVi6go',
                    'https://user:pass@youtube.com/watch?v=TL1v3KVi6go','https://youtube.com/watch?v=bad'):
            with self.assertRaises(ValueError):youtube_source(url)

    def test_segment_limits(self):
        self.assertEqual(segment(2,30),(2.,30.))
        for a,b in ((True,2),(math.inf,3),(0,601),(-1,3),(0,0)):
            with self.assertRaises(ValueError):segment(a,b)

    def test_local_argv_no_shell_network_or_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'a space;$.mp4';source.write_bytes(b'fixture')
            exe=root/'ffmpeg.exe';exe.write_bytes(b'fixture')
            target=root/'out.wav';args=extraction_command(exe,source,target)
            self.assertIn(str(source.resolve()),args);self.assertIn('file,pipe',args);self.assertIn('-n',args)
            target.write_bytes(b'existing')
            with self.assertRaises(ValueError):extraction_command(exe,source,target)
            self.assertEqual(target.read_bytes(),b'existing')

    def test_second_draft_never_invents_beats_confidence_or_retunes(self):
        events=[(1.,1.5,30,.8,None),(0.,.5,60,.7,[0,1])]
        draft=note_draft(events,2,'test.wav')
        self.assertFalse(draft['exact']);self.assertIsNone(draft['tempo']);self.assertIsNone(draft['meter'])
        self.assertEqual([n['pitch'] for n in draft['notes']],[60,30])
        self.assertEqual(draft['notes'][1]['start_seconds'],1)
        self.assertNotIn('confidence',draft['notes'][0])
        self.assertEqual(len(draft['warnings']),3)

    def test_bad_inference_rejected_not_silently_repaired(self):
        for event in ((0,math.nan,60,.8,None),(0,0,60,.8,None),(0,3,60,.8,None),(0,1,128,.8,None)):
            with self.assertRaises(ValueError):note_draft([event],2,'x.wav')

    def test_pcm_duration_and_truncation(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.wav'
            with wave.open(str(path),'wb') as stream:
                stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(22050);stream.writeframes(b'\0\0'*22050)
            self.assertEqual(wav_duration(path),1)
            path.write_bytes(path.read_bytes()[:-20])
            with self.assertRaises(ValueError):wav_duration(path)
