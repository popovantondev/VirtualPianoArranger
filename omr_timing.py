"""Serialize independently advancing piano staves in fresh OMR XML only.

No meter fitting, duration trimming, guessed rests, or changes to the common
MusicXML importer. Unsupported/contradictory token/XML data stays untouched.
"""
from collections import defaultdict,deque
from copy import deepcopy
from fractions import Fraction
import re
import xml.etree.ElementTree as ET

from omr_duration import _symbol_bars


def _staff_schedule(symbols,bar,_allow_split=True):
    groups=[];chord=False
    for index in bar:
        symbol=symbols[index]
        if symbol.rhythm=="chord":chord=True;continue
        if not symbol.rhythm.startswith(("note_","rest_")):chord=False;continue
        # Existing 3:2 kern durations are already exact musical evidence.
        # Rejecting their spelling left the two staves serialized in sequence.
        if not re.fullmatch(r"(?:note|rest)_(?:1|2|4|8|16|32|64|3|6|12|24|48|96)\.*",symbol.rhythm):return None
        if symbol.position not in ("upper","lower"):return None
        if chord and groups:groups[-1].append(symbol)
        else:groups.append([symbol])
        chord=False
    split={"upper"} if _allow_split and any(getattr(s,"_vpa_polyphonic",False) for g in groups for s in g if s.position=="upper") else set()
    fallback=lambda:_staff_schedule(symbols,bar,_allow_split=False) if split else None
    for staff in split:
        pitched=[s for g in groups for s in g if s.position==staff and re.fullmatch(r"[A-G][0-9]",s.pitch)]
        long=[s for s in pitched if s.get_duration().fraction*4>=2]
        short=[s for s in pitched if s.get_duration().fraction*4<2]
        ordinal=lambda s:int(s.pitch[1])*7+"CDEFGAB".index(s.pitch[0])
        # A held lower voice is distinct from the faster upper melody. Image
        # evidence must establish opposing stems before this partition is used.
        attacks=sum(any(s.position==staff and s.get_duration().fraction*4>=2 for s in g) for g in groups)
        if attacks<2 or len(short)<2 or max(map(ordinal,long))>min(map(ordinal,short)):return fallback()
        if any(s.position==staff and s.pitch=="_" and s.get_duration().fraction*4>=2 for g in groups for s in g):return fallback()
    stream=lambda s:(s.position,"held" if s.get_duration().fraction*4>=2 else "melody") if s.position in split else (s.position,"staff")
    clocks=defaultdict(Fraction);extents=defaultdict(Fraction);events=[];used=set()
    for group in groups:
        streams={stream(symbol) for symbol in group}
        if len(streams)>1 and len({clocks[key] for key in streams})!=1:return fallback()
        for key in streams:
            notes=[s for s in group if stream(s)==key];onset=clocks[key];durations=[];used.add(key[0])
            for symbol in notes:
                duration=symbol.get_duration().fraction*4
                if duration<=0:return None
                if symbol.rhythm.startswith("note_") and not re.fullmatch(r"[A-G][0-9]",symbol.pitch):return None
                voice=("2" if key[1]=="held" else "1") if key[0]=="upper" and key[0] in split else None
                events.append((symbol,onset,duration,voice));durations.append(duration)
                extents[key]=max(extents[key],onset+duration)
            clocks[key]+=min(durations)
    # A missing rest/attack cannot be filled in just to align the hands.
    if used!={"upper","lower"} or len(set(extents.values()))!=1:return fallback()
    return events,next(iter(extents.values()))


def _xml_notes(measure,divisions):
    cursor=Fraction(0);last=None;events=[]
    for child in measure:
        if child.tag in ("backup","forward"):
            delta=Fraction(child.findtext("duration"))/divisions
            cursor+=delta if child.tag=="forward" else -delta
        elif child.tag=="note":
            if any(child.find(tag) is not None for tag in ("grace","cue","unpitched")):return None
            duration=Fraction(child.findtext("duration"))/divisions
            if child.find("chord") is not None:
                if last is None:return None
                onset=last
            else:onset=cursor;last=onset;cursor+=duration
            pitch=child.find("pitch")
            if pitch is None and child.find("rest") is None:return None
            name=None if pitch is None else pitch.findtext("step","")+pitch.findtext("octave","")
            key=(child.findtext("staff","1"),name,duration)
            events.append((child,key,onset,duration))
    return events


def _retime_measure(measure,events,divisions):
    notes=[child for child in measure if child.tag=="note"]
    if not notes:return None
    first=list(measure).index(notes[0]);last=list(measure).index(notes[-1])
    # Mid-bar tempo/direction/attribute changes need explicit position mapping.
    if any(child.tag not in ("note","backup","forward") for child in list(measure)[first:last+1]):return None
    candidate=deepcopy(measure)
    for child in list(candidate)[first:last+1]:candidate.remove(child)
    cursor=Fraction(0);previous=None;offset=first
    ordered=sorted(events,key=lambda e:(e[1],e[0].findtext("staff","1"),e[0].findtext("voice","1"),e[2],e[3]))
    intervals=defaultdict(list)
    for note,onset,duration,index in ordered:
        stream=(note.findtext("staff","1"),note.findtext("voice","1"))
        if any(start!=onset or length!=duration for start,length in intervals[stream] if start<onset+duration and onset<start+length):return None
        intervals[stream].append((onset,duration))
        node=deepcopy(note)
        for chord in node.findall("chord"):node.remove(chord)
        same=(onset,stream,duration)
        if previous==same:node.insert(0,ET.Element("chord"))
        else:
            delta=onset-cursor;ticks=abs(delta)*divisions
            if ticks.denominator!=1:return None
            if delta:
                movement=ET.Element("forward" if delta>0 else "backup")
                ET.SubElement(movement,"duration").text=str(ticks.numerator)
                candidate.insert(offset,movement);offset+=1
            cursor=onset+duration
        candidate.insert(offset,node);offset+=1;previous=same
    return candidate


def retime_independent_staves(root,symbols):
    """Change a measure only after complete note/rest/token correspondence.

    Clocks come solely from each staff's recognized durations; no reference
    meter is used. Pitches, durations, ties, notation and rests survive. Only
    the image-verified split assigns stable held/melody voice numbers.
    """
    parts=root.findall("part");bars=[bar for system in _symbol_bars(symbols) for bar in system]
    if len(parts)!=1 or len(parts[0].findall("measure"))!=len(bars):return []
    part=parts[0];divisions=Fraction(1);audit=[]
    for number,(measure,bar) in enumerate(zip(part.findall("measure"),bars),1):
        for attribute in measure.findall("attributes"):
            if attribute.find("divisions") is not None:divisions=Fraction(attribute.findtext("divisions"))
        if divisions<=0:continue
        schedule=_staff_schedule(symbols,bar);original=_xml_notes(measure,divisions)
        if schedule is None or original is None:continue
        expected,extent=schedule
        if len(expected)!=len(original):continue
        lookup=defaultdict(deque)
        for index,(note,key,onset,duration) in enumerate(original):lookup[key].append((note,onset,duration,index))
        ordered=[];changes=0
        for symbol,onset,duration,voice in expected:
            # The generator uses the pitch, not the rhythm prefix, to decide
            # rest vs note (its model can emit rest_8 with a real pitch).
            key=("1" if symbol.position=="upper" else "2",symbol.pitch if re.fullmatch(r"[A-G][0-9]",symbol.pitch) else None,duration)
            if not lookup[key]:break
            note,previous,length,index=lookup[key].popleft()
            if voice is not None and note.findtext("voice")!=voice:
                note=deepcopy(note);node=note.find("voice")
                if node is None:node=ET.SubElement(note,"voice")
                node.text=voice
            ordered.append((note,onset,length,index));changes+=onset!=previous
        if len(ordered)!=len(original) or not changes or len(audit)>=200:continue
        candidate=_retime_measure(measure,ordered,divisions)
        if candidate is None:continue
        check=_xml_notes(candidate,divisions)
        if check is None or max(start+duration for _,_,start,duration in check)!=extent:continue
        position=list(part).index(measure);part.remove(measure);part.insert(position,candidate)
        audit.append({"measure":number,"movedNotes":changes,"duration":[extent.numerator,extent.denominator],
                      "reason":"independent-voice-clocks" if any(voice is not None for _,_,_,voice in expected) else "independent-staff-clocks"})
    return audit
