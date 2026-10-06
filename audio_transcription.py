"""Prepared audio transcription boundary; no downloads, installs or UI actions.

Outputs are unverified SECOND-based drafts, not guessed bars/tempo/Score.
Local decoding and inference belong to separate cancellable processes in the
future adapter. Online sources are validated here, never fetched implicitly.
"""
import math
from pathlib import Path
import re
from urllib.parse import parse_qs,urlsplit
import wave

MAX_SECONDS=600
MAX_NOTES=100000
MEDIA_EXTENSIONS={'.wav','.mp3','.flac','.m4a','.aac','.ogg','.opus','.mp4','.mkv','.mov','.webm','.avi'}


def youtube_source(url):
    if not isinstance(url,str) or len(url)>2048:raise ValueError('Invalid video URL')
    value=urlsplit(url)
    if value.scheme!='https' or value.username or value.password or value.port not in (None,443):
        raise ValueError('Only public HTTPS YouTube URLs are supported')
    host=value.hostname
    if host=='youtu.be':video=value.path.strip('/')
    elif host in ('youtube.com','www.youtube.com','m.youtube.com') and value.path=='/watch':
        ids=parse_qs(value.query).get('v',[])
        video=ids[0] if len(ids)==1 else ''
    else:raise ValueError('Unsupported video host or path')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}',video):raise ValueError('Invalid YouTube video ID')
    return 'https://www.youtube.com/watch?v='+video


def local_source(path):
    path=Path(path).resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in MEDIA_EXTENSIONS:raise ValueError('Unsupported local media file')
    if not 0<path.stat().st_size<=2_000_000_000:raise ValueError('Media file exceeds size limit')
    return path


def segment(start,length):
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (start,length)):
        raise ValueError('Invalid audio segment')
    if not 0<=start<=86400 or not 0<length<=MAX_SECONDS:raise ValueError('Audio segment exceeds limits')
    return float(start),float(length)


def extraction_command(ffmpeg,source,target,start=0,length=30):
    """Only build argv. Caller must own a new temporary output and child job."""
    start,length=segment(start,length);source=local_source(source)
    ffmpeg=Path(ffmpeg).resolve(strict=True);target=Path(target).resolve()
    if not ffmpeg.is_file() or target.exists() or target.suffix.lower()!='.wav':raise ValueError('Invalid decoder or WAV output')
    if not target.parent.is_dir():raise ValueError('Missing temporary output directory')
    return [str(ffmpeg),'-nostdin','-hide_banner','-loglevel','error','-n',
            '-protocol_whitelist','file,pipe','-ss',str(start),'-i',str(source),
            '-t',str(length),'-map','0:a:0','-vn','-ac','1','-ar','22050',
            '-c:a','pcm_s16le','-f','wav',str(target)]


def wav_duration(path):
    with wave.open(str(path),'rb') as audio:
        if (audio.getcomptype()!='NONE' or audio.getnchannels()!=1 or
                audio.getframerate()!=22050 or audio.getsampwidth()!=2):raise ValueError('Expected mono 22050 Hz PCM16 WAV')
        duration=audio.getnframes()/22050
        if not 0<duration<=MAX_SECONDS:raise ValueError('WAV duration exceeds limit')
        # A declared RIFF length alone does not prove the samples exist.
        remaining=audio.getnframes()
        while remaining:
            count=min(remaining,22050)
            if len(audio.readframes(count))!=count*2:raise ValueError('Truncated WAV data')
            remaining-=count
        return duration


def note_draft(events,duration,source_name):
    if type(duration) not in (float,int) or not math.isfinite(duration) or not 0<duration<=MAX_SECONDS:
        raise ValueError('Invalid draft duration')
    if not isinstance(source_name,str) or len(source_name)>300:raise ValueError('Invalid source name')
    if not isinstance(events,(list,tuple)) or len(events)>MAX_NOTES:raise ValueError('Too many inferred notes')
    notes=[];bend=False
    for i,event in enumerate(events):
        if not isinstance(event,(tuple,list)) or len(event)!=5:raise ValueError('Invalid inferred note')
        start,end,pitch,activation,bends=event
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (start,end,activation)):
            raise ValueError('Non-finite inferred note')
        if not 0<=start<end<=duration or type(pitch) is not int or not 0<=pitch<=127 or not 0<=activation<=1:
            raise ValueError('Invalid inferred note range')
        if bends is not None and not isinstance(bends,(list,tuple)):raise ValueError('Invalid bend data')
        bend|=bool(bends)
        notes.append({'id':str(i),'start_seconds':float(start),'end_seconds':float(end),
                      'pitch':pitch,'activation':float(activation)})
    warnings=['Audio-derived notes are unverified. Check pitches, chord tones and note ends.',
              'Tempo, meter, voices and sustain have not been inferred.']
    if bend:warnings.append('Inferred continuous pitch bends are not included in piano notes.')
    return {'version':1,'units':'seconds','exact':False,'source_name':source_name,
            'duration_seconds':float(duration),'tempo':None,'meter':None,
            'notes':sorted(notes,key=lambda n:(n['start_seconds'],n['id'])),'warnings':warnings}
