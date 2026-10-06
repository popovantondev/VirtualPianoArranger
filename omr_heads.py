"""Narrow, image-confirmed OMR repairs; never fill a bar to a guessed meter."""
from collections import defaultdict
from copy import copy
from math import floor,ceil
import re

from omr_duration import _symbol_bars,_image_evidence,_filled_heads,_pitch_y


def _bars(gray,systems,symbols,targets):
    import numpy as np
    grouped=_symbol_bars(symbols);clefs={};key=None;number=0
    if len(grouped)!=len(systems):return
    for system,bars in zip(systems,grouped):
        holes,stems,boundaries=_image_evidence(gray,system,245,True);filled=_filled_heads(gray,system)
        unit=float(np.median(np.diff(system[2][:5])))
        for offset,bar in enumerate(bars):
            number+=1
            for index in bar:
                symbol=symbols[index]
                if symbol.rhythm.startswith("clef_"):clefs[symbol.position]=symbol.rhythm[5:]
                if re.fullmatch(r"keySignature_-?[0-7]",symbol.rhythm):key=int(symbol.rhythm.split("_")[1])
            if number not in targets or len(boundaries)!=len(bars)+1:continue
            if any(symbols[i].rhythm.startswith(("clef_","keySignature_")) for i in bar):continue
            if any(symbols[i].rhythm.startswith(("note_","rest_")) and not re.fullmatch(
                    r"(?:note|rest)_(?:1|2|4|8|16|32|64)\.*",symbols[i].rhythm) for i in bar):continue
            within=lambda h:boundaries[offset]+unit<h[0]<boundaries[offset+1]-unit
            yield number,bar,system,dict(clefs),key,unit,[h for h in filled if within(h)],[h for h in holes if within(h)],stems


def _accidental_near(gray,head,unit):
    import cv2
    hx,hy,_,_=head
    area=gray[max(0,round(hy-1.4*unit)):round(hy+1.4*unit)+1,
              max(0,round(hx-2.1*unit)):max(0,round(hx-.8*unit))]
    if not area.size:return True
    binary=cv2.threshold(area,170,255,cv2.THRESH_BINARY_INV)[1]
    binary[(binary>0).mean(axis=1)>.8]=0
    contours,_=cv2.findContours(binary,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    return any(w>.3*unit and h>.9*unit for _,_,w,h in map(cv2.boundingRect,contours))


def verify_repeated_pitch(gray,systems,symbols,findings,limit=200):
    """Correct only a whole repeated run with zero heads at its model pitch.

    At least three unaltered tokens must match exactly one unused image-head
    cluster. Other pitches provide anchors; the new pitch is on the clef grid,
    and the recognized key signature supplies the implicit accidental. An
    explicit/ambiguous accidental, clef change or competing head is rejected.
    """
    targets={item["measure"] for item in findings if item["part"]==1};result=list(symbols);audit=[]
    for number,bar,system,clefs,key,unit,filled,holes,_ in _bars(gray,systems,symbols,targets):
        if key is None:continue
        for staff,lines in (("upper",system[2][:5]),("lower",system[2][5:])):
            tokens=defaultdict(list)
            for i in bar:
                s=symbols[i]
                if s.position==staff and s.rhythm.startswith("note_") and re.fullmatch(r"[A-G][0-9]",s.pitch):tokens[s.pitch].append(i)
            for pitch,indices in tokens.items():
                if len(indices)<3 or len(audit)+len(indices)>min(200,limit) or any(symbols[i].lift!="_" for i in indices):continue
                old_y=_pitch_y(pitch,clefs.get(staff),lines)
                if old_y is None or any(abs(h[1]-old_y)<.55*unit for h in filled+holes):continue
                known=[_pitch_y(p,clefs.get(staff),lines) for p in tokens if p!=pitch]
                remaining=[h for h in filled if lines[0]-3*unit<h[1]<lines[-1]+3*unit
                           and not any(y is not None and abs(h[1]-y)<.35*unit for y in known)]
                if len(remaining)!=len(indices):continue
                ordinal=lambda p:int(p[1])*7+"CDEFGAB".index(p[0])
                candidates=[f"{step}{octave}" for octave in range(1,8) for step in "CDEFGAB"
                            if 0<abs(ordinal(f"{step}{octave}")-ordinal(pitch))<=3]
                candidates=[p for p in candidates if all(abs(h[1]-_pitch_y(p,clefs.get(staff),lines))<.3*unit for h in remaining)]
                if len(candidates)!=1 or any(_accidental_near(gray,h,unit) for h in remaining):continue
                new=candidates[0]
                accidental="#" if key>0 and new[0] in "FCGDAEB"[:key] else "b" if key<0 and new[0] in "BEADGCF"[:-key] else "_"
                for index in indices:
                    s=copy(result[index]);s.pitch=new;s.lift=accidental;result[index]=s
                    audit.append({"measure":number,"from":pitch,"to":new,"lift":accidental,"staff":staff,
                                  "reason":"repeated-heads-on-clef-grid"})
    return result,audit


def _single_up_flag(gray,head,stems,unit):
    """A returning curved hook, not a horizontal beam or a second flag."""
    import cv2
    import numpy as np
    hx,hy,left,right=head
    matches=[(x,y0,y1) for x,y0,y1 in stems if .45*unit<x-hx<1.4*unit
             and -.25*unit<=x-right<=.35*unit and abs(y1-hy)<.5*unit and hy-y0>=2.7*unit]
    if len(matches)!=1:return False
    x,tip,_=matches[0]
    area=gray[max(0,round(tip)):round(min(tip+3*unit,hy-.5*unit))+1,
              round(x+.3*unit):round(x+1.8*unit)+1]
    if not area.size:return False
    binary=cv2.threshold(area,170,255,cv2.THRESH_BINARY_INV)[1]
    contours,_=cv2.findContours(binary,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    curves=[]
    for c in contours:
        a,b,w,h=cv2.boundingRect(c)
        if .45*unit<=w<=1.4*unit and 1.3*unit<=h<=2.4*unit and b<=.5*unit and cv2.contourArea(c)>.15*unit*unit:
            mask=np.zeros_like(binary);cv2.drawContours(mask,[c],-1,255,-1)
            edges=[float(np.flatnonzero(row).max()) for row in mask[b:b+h] if row.any()]
            # The tail turns back left; multiple broad hooks are not accepted.
            if edges and max(edges)-edges[-1]>=.15*unit:curves.append(c)
    return len(curves)==1


def recover_repeated_bass_eighth(gray,systems,symbols,findings,limit=200):
    """One missing, flagged repeat after an explicit dotted-quarter bass.

    This is not general note reconstruction. Require the same pitch on the
    same staff, exactly one extra head, a single visible hook, no accidental,
    and an unambiguous separate column between fully image-anchored groups.
    """
    targets={item["measure"] for item in findings if item["part"]==1};insertions=[];audit=[]
    for number,bar,system,clefs,_,unit,filled,holes,stems in _bars(gray,systems,symbols,targets):
        bass_unit=(system[2][-1]-system[2][5])/4
        tokens=defaultdict(list)
        for i in bar:
            s=symbols[i]
            if s.rhythm.startswith("note_") and re.fullmatch(r"[A-G][0-9]",s.pitch):tokens[(s.position,s.pitch)].append(i)
        matches={};possibilities=[]
        for (staff,pitch),indices in tokens.items():
            lines=system[2][:5] if staff=="upper" else system[2][5:];y=_pitch_y(pitch,clefs.get(staff),lines)
            if y is None:continue
            heads=sorted(h for h in filled if abs(h[1]-y)<.35*unit)
            if len(heads)==len(indices):matches.update(zip(indices,heads))
            if staff!="lower" or len(indices)!=1 or symbols[indices[0]].rhythm!="note_4." or len(heads)!=2:continue
            if any(abs(h[1]-y)<.55*unit for h in holes):continue
            first,extra=heads
            if _single_up_flag(gray,first,stems,bass_unit) or not _single_up_flag(gray,extra,stems,bass_unit) or _accidental_near(gray,extra,bass_unit):continue
            # The recognized dotted-quarter head needs its visible dot too.
            hx,hy,_,_=first
            dots=gray[max(0,floor(hy-.6*bass_unit)):ceil(hy+.6*bass_unit)+1,
                      round(hx+bass_unit):round(hx+2.2*bass_unit)]
            if not dots.size:continue
            import cv2
            contours,_=cv2.findContours(cv2.threshold(dots,170,255,cv2.THRESH_BINARY_INV)[1],cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            if not any(.15*bass_unit<=w<=.75*bass_unit and .15*bass_unit<=h<=.75*bass_unit and cv2.contourArea(c)>=.03*bass_unit*bass_unit
                       for c in contours for _,_,w,h in [cv2.boundingRect(c)]):continue
            matches[indices[0]]=first;possibilities.append((indices[0],extra))
        if len(possibilities)!=1 or len(audit)>=min(200,limit):continue
        groups=[];chord=False
        for index in bar:
            s=symbols[index]
            if s.rhythm=="chord":chord=True;continue
            if not s.rhythm.startswith(("note_","rest_")):chord=False;continue
            if chord and groups:groups[-1].append(index)
            else:groups.append([index])
            chord=False
        anchors=[]
        for group in groups:
            xs=[matches[i][0] for i in group if i in matches]
            if not xs or max(xs)-min(xs)>1.5*unit:break
            anchors.append((group[0],sum(xs)/len(xs)))
        if len(anchors)!=len(groups) or any(b[1]-a[1]<.8*unit for a,b in zip(anchors,anchors[1:])):continue
        index,head=possibilities[0];x=head[0]
        if any(abs(x-anchor)<1.5*unit for _,anchor in anchors) or not anchors[0][1]<x<anchors[-1][1]:continue
        before=next(i for i,anchor in anchors if anchor>x)
        replacement=copy(symbols[index]);replacement.rhythm="note_8";replacement._duration=None
        replacement.slur=replacement.articulation="_"
        from omr_timing import _staff_schedule
        candidate=[symbols[i] for i in bar];candidate.insert(bar.index(before),replacement)
        if _staff_schedule(candidate,list(range(len(candidate)))) is None:continue
        insertions.append((before,replacement));audit.append({"measure":number,"pitch":replacement.pitch,"staff":"lower",
            "rhythm":"note_8","reason":"extra-repeated-bass-head-single-flag","head":[round(head[0],2),round(head[1],2)]})
    result=list(symbols)
    for index,symbol in sorted(insertions,reverse=True):result.insert(index,symbol)
    return result,audit
