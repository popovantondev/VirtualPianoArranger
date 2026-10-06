"""Single current PCM recording and verified, no-overwrite audio export.

Storage/export safeguards follow SoundLeaf's DurableWave/ProfileExport ideas;
this is a Python implementation, not its Windows loopback recorder.
"""
import base64
import binascii
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import uuid
import wave

MAX_SECONDS = 1800
PROFILES = {
    "wav": ("WAV · PCM 16-bit", "pcm_s16le", []),
    "flac": ("FLAC · lossless", "flac", ["-c:a", "flac", "-f", "flac"]),
    "mp3": ("MP3 · 192 kbps", "libmp3lame", ["-c:a", "libmp3lame", "-b:a", "192k", "-f", "mp3"]),
    "m4a": ("M4A · AAC 192 kbps", "aac", ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-f", "ipod"]),
    "aac": ("AAC · ADTS 192 kbps", "aac", ["-c:a", "aac", "-b:a", "192k", "-f", "adts"]),
    "ogg": ("OGG · Opus 128 kbps", "libopus", ["-c:a", "libopus", "-b:a", "128k", "-ar", "48000", "-application", "audio", "-f", "ogg"]),
    "mkv": ("MKV · AAC 192 kbps", "aac", ["-c:a", "aac", "-b:a", "192k", "-f", "matroska"]),
}


class RecordingError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def run_encoder(executable, arguments, timeout=30):
    return subprocess.run([str(executable), *arguments], stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


def find_encoder(root):
    # Existing SoundLeaf is a local fallback, not a bundled or installed dependency.
    candidates = [os.environ.get("VPA_FFMPEG"), str(Path(root) / "tools" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")),
                  shutil.which("ffmpeg")]
    if os.name == "nt":
        candidates.append(str(Path(os.environ.get("PUBLIC", "C:/Users/Public")) / "Player/tools/ffmpeg.exe"))
    return next((Path(p) for p in candidates if p and Path(p).is_file()), None)


def publish_new(partial, target):
    """Atomic same-volume publication, refusing even a late destination race."""
    target = Path(target)
    if os.name == "nt":
        os.rename(partial, target)  # Windows rename never replaces an existing target.
    else:
        os.link(partial, target)
        Path(partial).unlink()


class CurrentRecording:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = None
        self.stream = None
        self.session = ""
        self.frames = self.sequence = self.rate = 0
        self.saved = False
        self.error = ""
        self._checkpoint_frames = 0

    @property
    def active(self):
        return self.stream is not None

    @property
    def seconds(self):
        return self.frames / self.rate if self.rate else 0

    def _header(self):
        size = self.frames * 4
        return struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", size + 36, b"WAVE", b"fmt ", 16,
                           1, 2, self.rate, self.rate * 4, 4, 16, b"data", size)

    def checkpoint(self):
        if self.stream:
            end = max(44, self.stream.tell())
            self.stream.seek(0)
            self.stream.write(self._header())
            self.stream.seek(end)
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self._checkpoint_frames = self.frames

    def begin(self, rate, replace=False):
        if self.active:
            raise RecordingError("busy")
        if type(rate) is not int or not 8000 <= rate <= 192000:
            raise RecordingError("invalid")
        if self.path and not self.saved and self.frames and not replace:
            raise RecordingError("replace")
        old = self.path
        previous = self.__dict__.copy()
        self.session = uuid.uuid4().hex
        path = self.folder / (self.session + ".partial.wav")
        stream = path.open("xb+")
        self.path, self.stream, self.rate = path, stream, rate
        self.frames = self.sequence = self._checkpoint_frames = 0
        self.saved, self.error = False, ""
        try:
            self.checkpoint()  # A durable header exists before the worklet is armed.
            if old:
                old.unlink(missing_ok=True)
        except OSError:
            stream.close()
            path.unlink(missing_ok=True)
            self.__dict__.update(previous)
            raise
        return self.session

    def append(self, session, sequence, encoded):
        if not self.active or session != self.session or sequence != self.sequence:
            raise RecordingError("sequence")
        if not isinstance(encoded, str) or len(encoded) > 90000:
            raise RecordingError("invalid")
        try:
            pcm = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise RecordingError("invalid") from None
        if not pcm or len(pcm) % 4:
            raise RecordingError("invalid")
        if self.frames + len(pcm) // 4 > self.rate * MAX_SECONDS:
            raise RecordingError("limit")
        self.stream.write(pcm)
        self.frames += len(pcm) // 4
        self.sequence += 1
        if self.frames - self._checkpoint_frames >= self.rate:
            self.checkpoint()

    def finish(self, session, error=""):
        if session != self.session or not self.active:
            raise RecordingError("sequence")
        try:
            self.checkpoint()
        finally:
            self.stream.close()
            self.stream = None
        self.error = error
        if not self.frames:
            self.path.unlink(missing_ok=True)
            self.path = None
            raise RecordingError("empty")
        with wave.open(str(self.path), "rb") as pcm:
            if pcm.getnframes() != self.frames or pcm.getnchannels() != 2 or self.path.stat().st_size != 44 + self.frames * 4:
                raise RecordingError("invalid")
        final = self.path.with_name(self.session + ".wav")
        publish_new(self.path, final)
        self.path = final
        return final

    def dispose(self, discard=False):
        if self.active:
            self.finish(self.session, "interrupted")
        if discard and self.path:
            self.path.unlink(missing_ok=True)
            self.path = None


class AudioExporter:
    def __init__(self, executable=None):
        self.executable = executable
        self.codecs = set()
        if executable:
            try:
                result = run_encoder(executable, ["-hide_banner", "-encoders"], 5)
                if result.returncode == 0:
                    self.codecs = set(re.findall(r"^\s*A\S{5}\s+(\S+)", result.stdout.decode("utf-8", "replace"), re.M))
            except (OSError, subprocess.TimeoutExpired):
                pass

    def formats(self):
        return [{"id": key, "label": spec[0], "available": key == "wav" or spec[1] in self.codecs}
                for key, spec in PROFILES.items()]

    def export(self, source, target, format_id):
        source, target = Path(source), Path(target)
        if format_id not in PROFILES or target.suffix.lower() != "." + format_id:
            raise RecordingError("invalid")
        if target.exists() or target.resolve() == source.resolve():
            raise RecordingError("exists")
        if format_id != "wav" and PROFILES[format_id][1] not in self.codecs:
            raise RecordingError("encoder")
        with wave.open(str(source), "rb") as pcm:
            expected = pcm.getnframes() / pcm.getframerate()
            if not pcm.getnframes() or pcm.getnchannels() != 2 or pcm.getsampwidth() != 2 or source.stat().st_size != 44+pcm.getnframes()*4:
                raise RecordingError("empty")
        fd, temp = tempfile.mkstemp(prefix=".vpa-export-", suffix="." + format_id, dir=target.parent)
        os.close(fd)
        partial = Path(temp)
        try:
            if format_id == "wav":
                shutil.copyfile(source, partial)
                with wave.open(str(partial), "rb") as pcm:
                    if abs(pcm.getnframes() / pcm.getframerate() - expected) > .001:
                        raise RecordingError("verify")
            else:
                # The exclusively reserved temporary path is ours, never the user's target.
                args = ["-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-xerror", "-i", str(source),
                        "-map", "0:a:0", "-vn", "-ac", "2", "-threads", "2", *PROFILES[format_id][2], str(partial)]
                timeout = max(30, min(3600, expected * 3 + 30))
                result = run_encoder(self.executable, args, timeout)
                if result.returncode or partial.stat().st_size < 64:
                    raise RecordingError("encode")
                decoded = run_encoder(self.executable, ["-hide_banner", "-loglevel", "error", "-nostdin", "-xerror",
                    "-progress", "pipe:1", "-nostats", "-i", str(partial), "-map", "0:a:0", "-f", "null", "-"], timeout)
                times = re.findall(rb"out_time_us=(\d+)", decoded.stdout)
                if decoded.returncode or not times or abs(int(times[-1]) / 1000000 - expected) > .25:
                    raise RecordingError("verify")
            with partial.open("rb+") as stream:
                os.fsync(stream.fileno())
            publish_new(partial, target)
            return target
        except subprocess.TimeoutExpired:
            raise RecordingError("timeout") from None
        finally:
            partial.unlink(missing_ok=True)
