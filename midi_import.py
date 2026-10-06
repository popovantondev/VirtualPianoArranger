"""Bounded SMF 0/1 PPQN importer, independent of Qt and MIDI devices.

Tracks/channels/programs identify selectable parts; they do not select a
different synthesizer. Note overlap is FIFO within a track/channel/pitch.
"""
from bisect import bisect_right
from collections import defaultdict, deque
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from music_time import pair, rational, validate_score

MAX_BYTES=16_000_000
MAX_EVENTS=200_000


class Reader:
    def __init__(self,data):self.data=data;self.at=0
    def take(self,size):
        if size<0 or self.at+size>len(self.data):raise ValueError('Truncated MIDI data')
        value=self.data[self.at:self.at+size];self.at+=size;return value
    def byte(self):return self.take(1)[0]
    def vlq(self):
        value=0
        for _ in range(4):
            byte=self.byte();value=(value<<7)|(byte&127)
            if byte<128:return value
        raise ValueError('Invalid MIDI variable-length value')


def _name(raw):
    try:value=raw.decode('utf-8')
    except UnicodeDecodeError:value=raw.decode('cp1252',errors='replace')
    return ''.join(c for c in value if ord(c)>=32)[:200]


def read_midi(path):
    with Path(path).open('rb') as stream:data=stream.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:raise ValueError('MIDI exceeds 16 MB')
    reader=Reader(data)
    if reader.take(4)!=b'MThd':raise ValueError('Not a Standard MIDI File')
    size=int.from_bytes(reader.take(4),'big');header=Reader(reader.take(size))
    fmt=int.from_bytes(header.take(2),'big');tracks=int.from_bytes(header.take(2),'big');ppqn=int.from_bytes(header.take(2),'big')
    if fmt not in (0,1):raise ValueError('Only MIDI format 0/1 is supported; format 2 is asynchronous')
    if not 1<=tracks<=1000 or (fmt==0 and tracks!=1):raise ValueError('Invalid MIDI track count')
    if ppqn&0x8000 or ppqn==0:raise ValueError('SMPTE MIDI timing is not supported; use PPQN')
    events=[];names={};end=0;warnings=[];exact=True
    def warn(message,uncertain=False):
        nonlocal exact
        if message not in warnings:warnings.append(message)
        if uncertain:exact=False
    for track in range(tracks):
        if reader.take(4)!=b'MTrk':raise ValueError('Missing MIDI track chunk')
        chunk=Reader(reader.take(int.from_bytes(reader.take(4),'big')))
        tick=0;running=None;ended=False;ordinal=0;port=0
        while chunk.at<len(chunk.data):
            tick+=chunk.vlq()
            if tick>10**9:raise ValueError('MIDI timeline exceeds limit')
            status=chunk.byte()
            if status<128:
                if running is None:raise ValueError('MIDI running status has no channel message')
                chunk.at-=1;status=running
            if status==0xff:
                kind=chunk.byte();payload=chunk.take(chunk.vlq());running=None
                if kind==0x2f:
                    tail=chunk.data[chunk.at:]
                    # Narrow compatibility for legacy writers: one padding
                    # byte INSIDE the track length, never later MIDI events.
                    if payload or tail not in (b'',b'\x00'):raise ValueError('Invalid MIDI end-of-track')
                    if tail:warn('One zero padding byte after MIDI end-of-track ignored.')
                    ended=True;break
                if kind==3:names[track]=_name(payload)
                if kind==0x21:
                    if len(payload)!=1 or payload[0]>127:raise ValueError('Invalid MIDI port metadata')
                    port=payload[0]
                if kind==0x51:
                    if len(payload)!=3 or int.from_bytes(payload,'big')==0:raise ValueError('Invalid MIDI tempo')
                    events.append((tick,track,ordinal,'tempo',int.from_bytes(payload,'big')))
                if kind==0x58:
                    if len(payload)!=4 or not 1<=payload[0]<=32 or payload[1]>5:raise ValueError('Unsupported MIDI time signature')
                    events.append((tick,track,ordinal,'meter',(payload[0],2**payload[1])))
            elif status in (0xf0,0xf7):
                chunk.take(chunk.vlq());running=None;warn('MIDI SysEx sound commands are not applied.')
            elif 0x80<=status<=0xef:
                running=status;kind=status>>4;channel=status&15
                payload=chunk.take(1 if kind in (0xc,0xd) else 2)
                if any(v>=128 for v in payload):raise ValueError('Invalid MIDI channel data')
                events.append((tick,track,ordinal,'channel',(kind,port,channel,*payload)))
            else:raise ValueError('Unsupported MIDI system event')
            ordinal+=1
            if ordinal>MAX_EVENTS or len(events)>MAX_EVENTS:raise ValueError('Too many MIDI events')
        if not ended:warn('MIDI track has no end marker; trailing silence is unverified.',True)
        end=max(end,tick)
    if reader.at!=len(data):raise ValueError('Unexpected trailing MIDI chunks')
    events.sort(key=lambda e:e[:3])
    tempos={0:500000};meters={0:(4,4)};programs=defaultdict(int);pedal=defaultdict(bool)
    active=defaultdict(deque);sustained=defaultdict(list);notes=[];parts={};tempo_seen={};meter_seen={}
    def close(note,tick):
        if tick<=note.pop('_tick'):warn('Zero-length MIDI note omitted.');return
        note['duration']=pair(Fraction(tick,ppqn)-rational(note['onset']));notes.append(note)
        if len(notes)>100000:raise ValueError('Too many MIDI notes')
    for tick,track,ordinal,event,value in events:
        if event in ('tempo','meter'):
            target,seen=(tempos,tempo_seen) if event=='tempo' else (meters,meter_seen)
            if tick in seen and seen[tick]!=value:warn('Conflicting MIDI tempo/meter events; last file-order event used.',True)
            seen[tick]=value;target[tick]=value;continue
        kind,port,channel,*payload=value;stream=(port,channel)
        if kind==0xc:
            programs[stream]=payload[0];continue
        if kind==0x9 and payload[1]>0:
            pitch,velocity=payload;program=programs[stream];part_id=f'T{track+1}O{port}C{channel+1}P{program+1}'
            name=names.get(track) or f'Track {track+1}'
            parts.setdefault(part_id,{'id':part_id,'name':f'{name} · PORT {port+1} · CH {channel+1} · GM {program+1}',
                                     'midi_track':track,'midi_port':port,'midi_channel':channel,'midi_program':program,'percussion':channel==9})
            if len(parts)>1000:raise ValueError('Too many MIDI parts')
            if channel==9:warn('Channel 10 percussion is not played by the piano.');continue
            key=(port,track,channel,pitch)
            if active[key]:warn('Overlapping same MIDI pitch in one track/channel matched FIFO.',True)
            active[key].append({'id':f'{track}:{ordinal}','part_id':part_id,'voice':str(channel+1),'staff':'1',
                                'pitch':pitch,'velocity':velocity,'onset':pair(Fraction(tick,ppqn)), '_tick':tick})
        elif kind==0x8 or (kind==0x9 and payload[1]==0):
            if channel==9:continue
            key=(port,track,channel,payload[0])
            if not active[key]:
                # SMF tracks organise events, not separate MIDI channels.
                # A note-off may live in another track; only a unique live
                # note on this port/channel/pitch proves its intended target.
                candidates=[k for k,q in active.items() if q and (k[0],k[2],k[3])==(port,channel,payload[0])]
                if len(candidates)!=1 or len(active[candidates[0]])!=1:
                    warn('Unmatched or ambiguous cross-track MIDI note-off.',True);continue
                key=candidates[0]
            note=active[key].popleft()
            if pedal[stream]:sustained[stream].append(note)
            else:close(note,tick)
        elif kind==0xb:
            controller,v=payload
            if controller==64:
                pedal[stream]=v>=64
                if v<64:
                    for note in sustained.pop(stream,[]):close(note,tick)
            elif controller in (120,123):
                for key in list(active):
                    if (key[0],key[2])==stream:
                        while active[key]:
                            note=active[key].popleft()
                            if controller==123 and pedal[stream]:sustained[stream].append(note)
                            else:close(note,tick)
                if controller==120 or not pedal[stream]:
                    for note in sustained.pop(stream,[]):close(note,tick)
            elif controller==121:
                pedal[stream]=False
                for note in sustained.pop(stream,[]):close(note,tick)
            elif controller not in (0,32):warn('MIDI controller sound/expression changes are not applied.')
        elif kind==0xe and payload!=[0,64]:warn('MIDI pitch bend is unsupported; exact playback unavailable.',True)
        elif kind in (0xa,0xd):warn('MIDI aftertouch is not applied.')
    if any(active.values()) or any(sustained.values()):warn('Unclosed MIDI notes/pedal-held notes omitted; no durations guessed.',True)
    duration=Fraction(max(end,1),ppqn)
    if duration>1_000_000:raise ValueError('MIDI duration exceeds limit')
    measures=[];position=Fraction(0);changes=sorted(Fraction(t,ppqn) for t in meters)
    while position<duration:
        at=bisect_right(changes,position)-1;meter=meters[int(changes[at]*ppqn)]
        finish=min(duration,position+Fraction(meter[0]*4,meter[1]))
        if at+1<len(changes):finish=min(finish,changes[at+1])
        measures.append({'number':len(measures)+1,'onset':pair(position),'duration':pair(finish-position),
                         'beats':meter[0],'beat_type':meter[1]})
        if len(measures)>100000:raise ValueError('Too many MIDI measures')
        position=finish
    starts=[rational(m['onset']) for m in measures]
    for note in notes:note['measure']=bisect_right(starts,rational(note['onset']))
    warn('MIDI parts use the local piano sound; original GM instrument timbres are not synthesized.')
    score={'format':1,'exact':exact,'parts':list(parts.values()),'notes':sorted(notes,key=lambda n:(rational(n['onset']),n['id'])),
           'measures':measures,'duration':pair(duration),'tempos':[{'onset':pair(Fraction(t,ppqn)),'bpm':pair(Fraction(60_000_000,v))} for t,v in sorted(tempos.items())],
           'initial_tempo_explicit':0 in tempo_seen,'warnings':warnings}
    return validate_score(score)


def select_parts(score,ids,allow_approximate=False):
    if type(allow_approximate) is not bool:raise ValueError('Invalid approximate MIDI playback choice')
    ids=set(ids);available={p['id'] for p in score['parts'] if not p.get('percussion')}
    if not ids or not ids<=available:raise ValueError('Select at least one melodic MIDI part')
    selected=deepcopy(score);selected['parts']=[p for p in selected['parts'] if p['id'] in ids]
    selected['notes']=[n for n in selected['notes'] if n['part_id'] in ids]
    if not selected['notes']:raise ValueError('Selected MIDI parts contain no closed notes')
    # User consent applies only to replaying the imported CLOSED events on the
    # local piano. It does not change exactness or guess any missing note end.
    selected['midi_approximate_playback']=allow_approximate and not selected['exact']
    return validate_score(selected)
