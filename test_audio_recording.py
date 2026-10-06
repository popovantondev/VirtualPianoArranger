import base64
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave

from audio_recording import AudioExporter, CurrentRecording, MAX_SECONDS, PROFILES, RecordingError, find_encoder


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="vpa-recording-test-")
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def record(self, seconds=.5):
        c = CurrentRecording(self.root / "current")
        session = c.begin(48000)
        pcm = b"".join(struct.pack("<hh",int(10000*math.sin(2*math.pi*440*i/48000)),int(6000*math.sin(2*math.pi*660*i/48000))) for i in range(int(48000*seconds)))
        for seq, start in enumerate(range(0,len(pcm),16000)):
            c.append(session,seq,base64.b64encode(pcm[start:start+16000]).decode())
        c.finish(session)
        return c

    def test_stream_header_frames_and_stereo(self):
        c = self.record()
        with wave.open(str(c.path),"rb") as pcm:
            self.assertEqual((pcm.getnchannels(),pcm.getsampwidth(),pcm.getframerate(),pcm.getnframes()),(2,2,48000,24000))
            left,right=struct.unpack("<hh",pcm.readframes(2)[4:8])
            self.assertNotEqual(left,right)
        self.assertFalse(c.active)
        self.assertEqual(c.path.stat().st_size,44+c.frames*4)
        self.assertEqual(len(list(c.folder.iterdir())),1)

    def test_confirm_replace_and_validation(self):
        c=self.record()
        old=c.path.read_bytes()
        with self.assertRaisesRegex(RecordingError,"replace"):
            c.begin(48000)
        self.assertEqual(c.path.read_bytes(),old)
        c.saved=True
        session=c.begin(48000)
        for seq, value in ((1,"AAAA"),(0,"!!!"),(0,"AAAA")):
            with self.assertRaises(RecordingError):
                c.append(session,seq,value)
        with self.assertRaisesRegex(RecordingError,"empty"):
            c.finish(session)
        self.assertFalse(c.active)

    def test_wav_export_and_existing_file_not_overwritten(self):
        c=self.record()
        exporter=AudioExporter()
        target=self.root/"export.wav"
        exporter.export(c.path,target,"wav")
        self.assertEqual(c.path.read_bytes(),target.read_bytes())
        with self.assertRaisesRegex(RecordingError,"exists"):
            exporter.export(c.path,target,"wav")
        with self.assertRaisesRegex(RecordingError,"encoder"):
            exporter.export(c.path,self.root/"export.mp3","mp3")
        self.assertEqual([f["id"] for f in exporter.formats() if f["available"]],["wav"])
        self.assertFalse(list(self.root.glob(".vpa-export-*")))

    def test_failed_start_checkpoint_keeps_previous_recording(self):
        c=self.record()
        original=c.path
        data=original.read_bytes()
        with patch("audio_recording.os.fsync",side_effect=OSError("disk error")),self.assertRaises(OSError):
            c.begin(48000,replace=True)
        self.assertEqual(c.path,original)
        self.assertEqual(original.read_bytes(),data)
        self.assertFalse(c.active)
        self.assertEqual(len(list(c.folder.iterdir())),1)

    def test_duration_limit_rejects_more_audio_without_closing_stream(self):
        c=CurrentRecording(self.root/"limit")
        session=c.begin(8000)
        c.frames=c.rate*MAX_SECONDS
        with self.assertRaisesRegex(RecordingError,"limit"):
            c.append(session,0,base64.b64encode(b"\x00"*4).decode())
        self.assertTrue(c.active)
        self.assertEqual(c.sequence,0)
        c.frames=0
        with self.assertRaisesRegex(RecordingError,"empty"):
            c.finish(session)

    def test_export_publication_race_keeps_source_and_target(self):
        c=self.record()
        target=self.root/"race.wav"
        original=c.path.read_bytes()
        def collision(_partial,_target):
            target.write_bytes(b"owner-file")
            raise FileExistsError("late collision")
        with patch("audio_recording.publish_new",side_effect=collision),self.assertRaises(FileExistsError):
            AudioExporter().export(c.path,target,"wav")
        self.assertEqual(target.read_bytes(),b"owner-file")
        self.assertEqual(c.path.read_bytes(),original)
        self.assertFalse(list(self.root.glob(".vpa-export-*")))

    def test_all_local_encoder_formats(self):
        encoder=find_encoder(Path(__file__).parent)
        if not encoder:
            self.skipTest("no installed FFmpeg; WAV remains available")
        c=self.record(1)
        original=c.path.read_bytes()
        exporter=AudioExporter(encoder)
        for format_id in PROFILES:
            self.assertTrue(next(f for f in exporter.formats() if f["id"]==format_id)["available"],format_id)
            exporter.export(c.path,self.root/ ("stereo."+format_id),format_id)
            self.assertGreater((self.root/("stereo."+format_id)).stat().st_size,64)
        self.assertEqual(original,c.path.read_bytes())
        print("AUDIO EXPORT: WAV, FLAC, MP3, M4A, AAC, OGG/Opus, MKV/AAC encoded and fully decoded")


if __name__=="__main__":
    unittest.main()
