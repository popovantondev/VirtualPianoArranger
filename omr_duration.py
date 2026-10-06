"""Conservative image evidence for a whole/half-note confusion in OMR.

Never fit a bar to a guessed meter. Only an isolated hollow head with an
attached stem can change an undotted whole-note token, before XML timing is
generated. Ambiguous pitch, engraving, bar alignment or clef stays untouched.
"""
from copy import copy
from fractions import Fraction
import re


def _symbol_bars(symbols):
    systems=[];bars=[];bar=[]
    for index,symbol in enumerate(symbols):
        rhythm=symbol.rhythm
        if rhythm=="newline":
            if any(symbols[i].rhythm.startswith(("note_","rest_")) for i in bar):bars.append(bar)
            systems.append(bars);bars=[];bar=[]
        elif "barline" in rhythm or "repeat" in rhythm:
            if any(symbols[i].rhythm.startswith(("note_","rest_")) for i in bar):bars.append(bar);bar=[]
        else:bar.append(index)
    # A missing system terminator must not silently shift image/bar mapping.
    if bars or any(symbols[i].rhythm.startswith(("note_","rest_")) for i in bar):return []
    return systems


def _image_evidence(gray,system,stem_threshold=210,voice_heads=False,hole_width=1.55,allow_line_holes=False):
    import cv2
    import numpy as np
    left,right,lines=system;unit=float(np.median(np.diff(lines[:5])))
    top=max(0,round(lines[0]-7*unit));bottom=min(len(gray),round(lines[-1]+7*unit))
    binary=cv2.threshold(gray[top:bottom,left:right+1],210,255,cv2.THRESH_BINARY_INV)[1]
    contours,hierarchy=cv2.findContours(binary,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
    holes=[]
    for index,contour in enumerate(contours):
        x,y,w,h=cv2.boundingRect(contour)
        if hierarchy[0][index][3]<0:continue
        if not (.45*unit<=w<=hole_width*unit and .15*unit<=h<=(1.2 if voice_heads else .9)*unit):continue
        if cv2.contourArea(contour)<.08*unit*unit:continue
        hx,hy=x+w/2+left,y+h/2+top
        if gray[min(len(gray)-1,round(hy)),min(gray.shape[1]-1,round(hx))]<(200 if voice_heads else 230):
            interior=gray[y+top:y+top+h,x+left:x+left+w]
            on_line=any(abs((hy-first)/step-round((hy-first)/step))<.2
                        for first,step in ((lines[0],unit),(lines[5],(lines[-1]-lines[5])/4)))
            if not allow_line_holes or not on_line or (interior>=230).sum()<max(2,.15*w*h):continue
        holes.append((hx,hy,x+left,x+w-1+left))
    stem_binary=cv2.threshold(gray[top:bottom,left:right+1],stem_threshold,255,cv2.THRESH_BINARY_INV)[1]
    minimum=2.4 if stem_threshold>210 else 2.6
    vertical=cv2.morphologyEx(stem_binary,cv2.MORPH_OPEN,np.ones((max(3,round(minimum*unit)),1),np.uint8))
    contours,_=cv2.findContours(vertical,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    stems=[]
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        if w<=.5*unit and minimum*unit<=h<=(8 if voice_heads else 6)*unit:stems.append((x+w/2+left,y+top,y+h-1+top))
    # A barline must span both staves, not just look like a note stem.
    bar_image=cv2.threshold(gray[round(lines[0]):round(lines[-1])+1,left:right+1],235,255,cv2.THRESH_BINARY_INV)[1]
    bar_image=cv2.morphologyEx(bar_image,cv2.MORPH_CLOSE,np.ones((max(1,round(.45*unit)),1),np.uint8))
    xs=np.flatnonzero((bar_image>0).mean(axis=0)>.9)
    boundaries=[float(group.mean())+left for group in np.split(xs,np.where(np.diff(xs)>max(2,.3*unit))[0]+1) if len(group)]
    if not boundaries or boundaries[0]-left>unit or right-boundaries[-1]>unit:boundaries=[]
    return holes,stems,boundaries


def _pitch_y(pitch,clef,lines):
    import numpy as np
    if not re.fullmatch(r"[A-G][0-9]",pitch):return None
    unit=float(np.median(np.diff(lines)))
    reference={"G2":("G4",lines[-2]),"F4":("F3",lines[1])}.get(clef)
    if reference is None:return None
    ordinal=lambda value:int(value[1])*7+"CDEFGAB".index(value[0])
    return reference[1]-(ordinal(pitch)-ordinal(reference[0]))*unit/2


def verify_hollow_durations(gray,systems,symbols,rhythm_findings,limit=200):
    """Return copied tokens + bounded audit; never mutate the model's tokens.

    Restrict to overfilled bars, exact image/model bar alignment and a unique
    pitch/head. Existing rests, dots, tuplets, voices, pitch and accidentals are
    not reconstructed. The final XML generator recalculates all onsets/backups.
    """
    import numpy as np
    targets={item["measure"] for item in rhythm_findings if item["part"]==1
             and Fraction(*item["actual"])>Fraction(*item["expected"])}
    grouped=_symbol_bars(symbols)
    if not targets or len(grouped)!=len(systems):return symbols,[]
    result=list(symbols);audit=[];clefs={};measure=0
    for system,bars in zip(systems,grouped):
        evidence=None
        for bar_index,bar in enumerate(bars):
            measure+=1
            for index in bar:
                symbol=symbols[index]
                if symbol.rhythm.startswith("clef_"):clefs[symbol.position]=symbol.rhythm[5:]
            if measure not in targets:continue
            # Clef loops are also hollow: do not classify an opening/changed
            # clef's engraving as a note head in the same image interval.
            if any(symbols[i].rhythm.startswith("clef_") for i in bar):continue
            if evidence is None:evidence=_image_evidence(gray,system)
            holes,stems,boundaries=evidence
            if len(boundaries)!=len(bars)+1:continue
            for index in bar:
                if len(audit)>=min(200,limit):continue
                symbol=symbols[index]
                if symbol.rhythm!="note_1" or symbol.position not in ("upper","lower"):continue
                if sum(symbols[i].pitch==symbol.pitch and symbols[i].position==symbol.position for i in bar)!=1:continue
                lines=system[2][:5] if symbol.position=="upper" else system[2][5:]
                unit=float(np.median(np.diff(lines)))
                target=_pitch_y(symbol.pitch,clefs.get(symbol.position),lines)
                if target is None:continue
                nearby=sorted(hole for hole in holes if boundaries[bar_index]+unit<hole[0]<boundaries[bar_index+1]-unit
                              and abs(hole[1]-target)<.45*unit)
                groups=[]
                for hole in nearby:
                    if groups and hole[0]-groups[-1][-1][0]<.6*unit:groups[-1].append(hole)
                    else:groups.append([hole])
                if len(groups)!=1:continue
                head=groups[0];hx,hy=np.mean([hole[:2] for hole in head],axis=0)
                if abs(hy-target)>.3*unit or max(hole[1] for hole in head)-min(hole[1] for hole in head)>.65*unit:continue
                edge_left=min(hole[2] for hole in head);edge_right=max(hole[3] for hole in head)
                connections=[]
                for x,y0,y1 in stems:
                    if .45*unit<x-hx<1.4*unit and -.15*unit<=x-edge_right<=.35*unit and abs(y1-hy)<.5*unit:connections.append((x,y0,y1,"up"))
                    if .45*unit<hx-x<1.4*unit and -.15*unit<=edge_left-x<=.35*unit and abs(y0-hy)<.5*unit:connections.append((x,y0,y1,"down"))
                if len(connections)!=1:continue
                replacement=copy(symbol);replacement.rhythm="note_2";replacement._duration=None
                result[index]=replacement
                if len(audit)<min(200,limit):audit.append({"measure":measure,"pitch":symbol.pitch,"staff":symbol.position,
                    "from":"note_1","to":"note_2","reason":"hollow-head-attached-stem",
                    "head":[round(float(hx),2),round(float(hy),2)],"stemDirection":connections[0][3]})
    return result,audit


def _triplet_beam(gray,heads,stems,unit,reader):
    """Three up-stem attacks under a complete beam and an engraved 3.

    A lone unbracketed 3 is also a possible fingering: callers require a
    second adjacent numbered beam in that case. No meter enters this test.
    """
    import cv2
    import numpy as np
    tips=[]
    for hx,hy,left,right in heads:
        matches=[(x,y0) for x,y0,y1 in stems if .45*unit<x-hx<1.4*unit
                 and abs(x-right)<.4*unit and abs(y1-hy)<.6*unit and hy-y0>2.4*unit]
        if len(matches)!=1:return None
        tips.append(matches[0])
    xs=[v[0] for v in tips];ys=[v[1] for v in tips]
    if any(b-a<.8*unit for a,b in zip(xs,xs[1:])) or max(ys)-min(ys)>.8*unit:return None
    # At both inter-stem midpoints the full beam count must agree. A staff
    # rule is excluded by the required clearance above every note head.
    top=max(0,round(min(ys)-.2*unit));bottom=min(round(max(ys)+1.2*unit),round(min(h[1] for h in heads)-.8*unit))
    if bottom<=top:return None
    counts=[]
    for a,b in zip(xs,xs[1:]):
        x=round((a+b)/2);column=(gray[top:bottom,x-1:x+2]<170).mean(axis=1)>.7
        rows=np.flatnonzero(column)
        groups=[g for g in np.split(rows,np.where(np.diff(rows)>1)[0]+1) if len(g)]
        if any(not .12*unit<=len(g)<=int(np.ceil(.6*unit)) for g in groups):return None
        counts.append(len(groups))
    if counts[0] not in (1,2) or counts[0]!=counts[1]:return None
    # Require a continuous primary beam, not two nearby unrelated flags.
    for x in range(round(xs[0]),round(xs[-1])+1):
        y=ys[0]+(ys[-1]-ys[0])*(x-xs[0])/(xs[-1]-xs[0])
        if not (gray[max(0,round(y-.2*unit)):round(y+.4*unit)+1,x]<170).any():return None
    x0=max(0,round(xs[0]-.35*unit));x1=min(gray.shape[1],round(xs[-1]+.35*unit))
    y0=max(0,round(min(ys)-2.4*unit));y1=max(0,round(min(ys)-.3*unit))
    ink=cv2.threshold(gray[y0:y1,x0:x1],170,255,cv2.THRESH_BINARY_INV)[1]
    contours,_=cv2.findContours(ink,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    numerals=[]
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        if not (.3*unit<=w<=1.2*unit and .55*unit<=h<=1.5*unit):continue
        cx=x0+x+w/2
        if abs(cx-(xs[0]+xs[-1])/2)>.7*unit:continue
        crop=gray[max(0,y0+y-2):y0+y+h+2,max(0,x0+x-2):x0+x+w+2]
        text,confidence=reader(crop)
        if text!='3' or confidence<.98:continue
        # Horizontal arms on BOTH sides at the numeral's top prove a bracket;
        # ordinary isolated fingering digits cannot satisfy this witness.
        row0=max(0,y0+y-round(.25*unit));row1=y0+y+round(.45*unit)+1
        arms=[]
        for a,b in ((xs[0]-.3*unit,x0+x-.1*unit),(x0+x+w+.1*unit,xs[-1]+.3*unit)):
            a=max(0,round(a));b=min(gray.shape[1],round(b))
            strip=gray[row0:row1,a:b]<170
            arms.append(b-a>.5*unit and strip.size>0 and bool((strip.mean(axis=1)>.65).any()))
        numerals.append({'bracket':all(arms),'beams':counts[0],'numberBox':[x0+x,y0+y,w,h]})
    return numerals[0] if len(numerals)==1 else None


def verify_triplet_durations(gray,systems,symbols,reader=None):
    """Read missing 3:2 groups from engraving, without duration fitting.

    Limited to three equal undotted eighths/sixteenths, up stems, unique
    pitch/head occurrence correspondence. Existing tuplets/chords/rests and
    ambiguous lone fingering numbers remain untouched.
    """
    import numpy as np
    from homr.transformer.vocabulary import SymbolDuration
    from omr_meter import _local_reader
    grouped=_symbol_bars(symbols)
    if len(grouped)!=len(systems):return symbols,[]
    if reader is None:
        try:reader=_local_reader()
        except (ImportError,FileNotFoundError):return symbols,[]
    if reader is None:return symbols,[]
    result=list(symbols);audit=[];clefs={};measure=0
    for system,bars in zip(systems,grouped):
        heads=_filled_heads(gray,system);_,stems,boundaries=_image_evidence(gray,system)
        for bi,bar in enumerate(bars):
            measure+=1
            for index in bar:
                if symbols[index].rhythm.startswith('clef_'):clefs[symbols[index].position]=symbols[index].rhythm[5:]
            if len(boundaries)!=len(bars)+1:continue
            # HOMR's chord marker also means simultaneous *different* staves.
            # Only same-staff chord attacks are outside this three-note reader.
            chord_members=set();previous=None;chord=False
            for i in bar:
                s=symbols[i]
                if s.rhythm=='chord':chord=True;continue
                if s.rhythm.startswith(('note_','rest_')):
                    if chord and previous is not None and symbols[previous].position==s.position:
                        chord_members.update((previous,i))
                    previous=i
                chord=False
            candidates=[]
            for position,lines in (('upper',system[2][:5]),('lower',system[2][5:])):
                unit=float(np.median(np.diff(lines)))
                tokens=[i for i in bar if symbols[i].position==position and symbols[i].rhythm.startswith(('note_','rest_'))]
                mapping={}
                for i in tokens:
                    s=symbols[i];target=_pitch_y(s.pitch,clefs.get(position),lines)
                    if target is None:continue
                    same=[j for j in tokens if symbols[j].pitch==s.pitch and symbols[j].rhythm.startswith('note_')]
                    matching=sorted(h for h in heads if boundaries[bi]+unit<h[0]<boundaries[bi+1]-unit and abs(h[1]-target)<.35*unit)
                    if len(same)==len(matching):mapping[i]=matching[same.index(i)]
                for offset in range(len(tokens)-2):
                    group=tokens[offset:offset+3];notes=[symbols[i] for i in group]
                    if chord_members.intersection(group):continue
                    rhythm=notes[0].rhythm
                    if rhythm not in ('note_8','note_16') or any(s.rhythm!=rhythm or s.get_duration().actual_notes!=s.get_duration().normal_notes for s in notes):continue
                    if any(i not in mapping for i in group):continue
                    evidence=_triplet_beam(gray,[mapping[i] for i in group],stems,unit,reader)
                    if evidence and evidence['beams']==(1 if rhythm=='note_8' else 2):candidates.append((position,offset,group,evidence))
            used=set()
            for position,offset,group,evidence in candidates:
                repeated=any(p==position and abs(o-offset)==3 for p,o,g,e in candidates)
                if (not evidence['bracket'] and not repeated) or used.intersection(group) or len(audit)>=100:continue
                for i in group:
                    replacement=copy(symbols[i]);base=8 if replacement.rhythm=='note_8' else 16
                    replacement._duration=SymbolDuration(Fraction(1,base),0,3,2,base);result[i]=replacement
                used.update(group)
                audit.append({'measure':measure,'staff':position,'pitches':[symbols[i].pitch for i in group],
                              'ratio':[3,2],'reason':'printed-triplet-number-and-beam','bracket':evidence['bracket'],
                              'numberBox':evidence['numberBox']})
    return result,audit


def verify_polyphonic_staves(gray,systems,symbols):
    """Permit two clocks only after opposed stems at a shared attack.

    The timing helper additionally requires separated pitch registers, two
    attacks in each layer, all explicit chord constraints and equal extents.
    These hints never create/change a musical token or set a time signature.
    """
    import numpy as np
    grouped=_symbol_bars(symbols)
    if len(grouped)!=len(systems):return symbols
    result=list(symbols);clefs={}
    for system,bars in zip(systems,grouped):
        holes,stems,boundaries=_image_evidence(gray,system,stem_threshold=245,voice_heads=True)
        filled=_filled_heads(gray,system)
        if len(boundaries)!=len(bars)+1:continue
        unit=float(np.median(np.diff(system[2][:5])))
        for bar_index,bar in enumerate(bars):
            groups=[];chord=False
            for index in bar:
                symbol=symbols[index]
                if symbol.rhythm.startswith("clef_"):clefs[symbol.position]=symbol.rhythm[5:]
                if symbol.rhythm=="chord":chord=True;continue
                if not symbol.rhythm.startswith(("note_","rest_")):chord=False;continue
                if chord and groups:groups[-1].append(index)
                else:groups.append([index])
                chord=False
            for group in groups:
                # Only upper-staff melody over a held lower voice is handled.
                notes=[i for i in group if symbols[i].position=="upper" and re.fullmatch(r"note_(?:1|2|4|8|16|32|64)\.*",symbols[i].rhythm)]
                long=[i for i in notes if symbols[i].get_duration().fraction*4>=2]
                short=[i for i in notes if symbols[i].get_duration().fraction*4<2]
                if not long or not short:continue
                evidence=[]
                for index in short+long:
                    symbol=symbols[index];target=_pitch_y(symbol.pitch,clefs.get("upper"),system[2][:5])
                    if target is None:continue
                    pool=filled if index in short else holes
                    near=sorted(h for h in pool if boundaries[bar_index]+unit<h[0]<boundaries[bar_index+1]-unit and abs(h[1]-target)<.55*unit)
                    # The hint is for the first shared attack, not a later head
                    # of this pitch or a neighbouring black note's stem.
                    if not near:continue
                    head=near[0];hx,hy,left,right=head;directions=set()
                    minimum_dx=(.45 if index in short else .15)*unit
                    minimum_edge=(-.15 if index in short else -.3)*unit
                    for x,y0,y1 in stems:
                        if not y0-.6*unit<=hy<=y1+.6*unit:continue
                        if minimum_dx<x-hx<1.4*unit and minimum_edge<=x-right<=.5*unit and hy-y0>=2.4*unit:directions.add("up")
                        if minimum_dx<hx-x<1.4*unit and minimum_edge<=left-x<=.5*unit and y1-hy>=2.4*unit:directions.add("down")
                    required="up" if index in short else "down"
                    if directions=={required}:evidence.append((head[0],required))
                ups=[x for x,d in evidence if d=="up"];downs=[x for x,d in evidence if d=="down"]
                if not ups or not downs or abs(min(ups)-min(downs))>1.2*unit:continue
                for index in bar:
                    if symbols[index].position=="upper" and symbols[index].rhythm.startswith(("note_","rest_")):
                        result[index]=copy(result[index]);result[index]._vpa_polyphonic=True
                break
    return result


def _filled_heads(gray,system,max_width=2.2,min_aspect=0):
    import cv2
    import numpy as np
    left,right,lines=system;unit=float(np.median(np.diff(lines[:5])))
    top=max(0,round(lines[0]-7*unit));bottom=min(len(gray),round(lines[-1]+7*unit))
    binary=cv2.threshold(gray[top:bottom,left:right+1],170,255,cv2.THRESH_BINARY_INV)[1]
    # Even morphology anchors shift a head toward the neighbouring staff step.
    kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(max(3,round(.8*unit))|1,max(3,round(.45*unit))|1))
    opened=cv2.morphologyEx(binary,cv2.MORPH_OPEN,kernel)
    contours,_=cv2.findContours(opened,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    heads=[]
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        if not (.9*unit<w<max_width*unit and .5*unit<h<1.6*unit):continue
        if w/h < min_aspect:continue
        if cv2.contourArea(contour)/(w*h)<.36:continue
        moments=cv2.moments(contour)
        if not moments["m00"]:continue
        hx,hy=moments["m10"]/moments["m00"]+left,moments["m01"]/moments["m00"]+top
        radius=max(1,round(.15*unit));cx,cy=round(hx),round(hy)
        interior=gray[max(0,cy-radius):cy+radius+1,max(0,cx-radius):cx+radius+1]
        if not interior.size or float(interior.mean())>=80:continue
        heads.append((hx,hy,x+left,x+w-1+left))
    return heads


def _plain_filled_stem(gray,head,stems,unit,endpoint_tolerance=.5,min_length=2.7,ink_threshold=170,staff_lines=None):
    """Reject flag/beam branches and duration dots, not just a solid head."""
    import cv2
    import numpy as np
    hx,hy,left,right=head;matches=[]
    for x,y0,y1 in stems:
        if .45*unit<x-hx<1.4*unit and -.25*unit<=x-right<=.35*unit and abs(y1-hy)<endpoint_tolerance*unit and hy-y0>=min_length*unit:
            matches.append((x,y0,"up"))
        if .45*unit<hx-x<1.4*unit and -.25*unit<=left-x<=.35*unit and abs(y0-hy)<endpoint_tolerance*unit and y1-hy>=min_length*unit:
            matches.append((x,y1,"down"))
    if len(matches)!=1:return None
    x,tip,direction=matches[0];margin=max(2,round(.3*unit));span=round(1.5*unit)
    # A flag can return below the old 1.5-space window. Inspect its whole
    # possible hook, stopping before the attached head, in both directions.
    start,end=(round(tip)-1,round(min(tip+3*unit,hy-.8*unit))) if direction=="up" else (round(max(tip-3*unit,hy+.8*unit)),round(tip)+2)
    start=max(0,start);end=min(len(gray),end)
    ink=gray[start:end]<ink_threshold
    if staff_lines is not None:
        # An attachment hidden exactly in a rule cannot prove a plain tip.
        if min(abs(tip-line) for line in staff_lines)<.25*unit:return None
        # Only positively measured thin, straight rules on BOTH remote sides
        # are exempted. Never erase a guessed entire staff band or hook.
        remote=[(round(x-3.5*unit),round(x-2.2*unit)),(round(x+2.2*unit),round(x+3.5*unit))]
        if any(a<0 or b>gray.shape[1] for a,b in remote):return None
        for line in staff_lines:
            candidates=[]
            for y in range(max(start,round(line-.2*unit)),min(end,round(line+.2*unit)+1)):
                if all((gray[y,a:b]<ink_threshold).mean()>=.55 for a,b in remote):candidates.append(y)
            if candidates:
                if len(candidates)>.2*unit or candidates[-1]-candidates[0]+1!=len(candidates):return None
                ink[[y-start for y in candidates]]=False
    branches=sum(int(ink[:,max(0,a):max(0,b)].sum()) for a,b in
                 ((round(x)-span,round(x)-margin),(round(x)+margin,round(x)+span)))
    if branches>.1*unit*unit:return None
    dots=gray[max(0,round(hy-.5*unit)):min(len(gray),round(hy+.5*unit)+1),
              max(0,round(hx+unit)):min(gray.shape[1],round(hx+2.2*unit))]
    if dots.size:
        binary=cv2.threshold(dots,ink_threshold,255,cv2.THRESH_BINARY_INV)[1]
        contours,_=cv2.findContours(binary,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            _,_,w,h=cv2.boundingRect(contour)
            if .15*unit<=w<=.75*unit and .15*unit<=h<=.75*unit and cv2.contourArea(contour)>=.03*unit*unit:return None
    return direction


def verify_filled_durations(gray,systems,symbols,rhythm_findings,limit=200):
    """Match all occurrences of a pitch by x before half→quarter correction.

    Repeated pitches cannot be matched by uniqueness alone: the first may be
    an unbeamed quarter and subsequent ones eighths. Require equal image/token
    head counts and order, then independently verify the selected plain stem.
    """
    import numpy as np
    targets={item["measure"] for item in rhythm_findings if item["part"]==1}
    grouped=_symbol_bars(symbols)
    if not targets or len(grouped)!=len(systems):return symbols,[]
    result=list(symbols);audit=[];clefs={};measure=0
    for system,bars in zip(systems,grouped):
        evidence=None;filled=None
        for bar_index,bar in enumerate(bars):
            measure+=1
            for index in bar:
                symbol=symbols[index]
                if symbol.rhythm.startswith("clef_"):clefs[symbol.position]=symbol.rhythm[5:]
            if measure not in targets or any(symbols[i].rhythm.startswith("clef_") for i in bar):continue
            if evidence is None:evidence=_image_evidence(gray,system);filled=_filled_heads(gray,system)
            holes,stems,boundaries=evidence
            if len(boundaries)!=len(bars)+1:continue
            for index in bar:
                symbol=symbols[index]
                if symbol.rhythm not in ("note_2","note_8","note_16") or symbol.position not in ("upper","lower") or len(audit)>=min(200,limit):continue
                lines=system[2][:5] if symbol.position=="upper" else system[2][5:]
                unit=float(np.median(np.diff(lines)));target=_pitch_y(symbol.pitch,clefs.get(symbol.position),lines)
                if target is None:continue
                within=lambda head:boundaries[bar_index]+unit<head[0]<boundaries[bar_index+1]-unit
                heads=[(head,"filled") for head in filled if within(head) and abs(head[1]-target)<.35*unit]
                hollow=sorted(head for head in holes if within(head) and abs(head[1]-target)<.45*unit);clusters=[]
                for head in hollow:
                    if clusters and head[0]-clusters[-1][-1][0]<.6*unit:clusters[-1].append(head)
                    else:clusters.append([head])
                for cluster in clusters:
                    hx,hy=np.mean([head[:2] for head in cluster],axis=0)
                    if abs(hy-target)>.3*unit:continue
                    heads.append(((float(hx),float(hy),min(h[2] for h in cluster),max(h[3] for h in cluster)),"hollow"))
                heads.sort(key=lambda item:item[0][0])
                tokens=[i for i in bar if symbols[i].rhythm.startswith("note_") and symbols[i].pitch==symbol.pitch and symbols[i].position==symbol.position]
                if len(heads)!=len(tokens) or any(b[0][0]-a[0][0]<.8*unit for a,b in zip(heads,heads[1:])):continue
                head,kind=heads[tokens.index(index)]
                if kind!="filled":continue
                direction=_plain_filled_stem(gray,head,stems,unit,staff_lines=lines)
                if direction is None:continue
                replacement=copy(symbol);replacement.rhythm="note_4";replacement._duration=None;result[index]=replacement
                audit.append({"measure":measure,"pitch":symbol.pitch,"staff":symbol.position,"from":symbol.rhythm,"to":"note_4",
                              "reason":"filled-head-unflagged-stem","head":[round(head[0],2),round(head[1],2)],"stemDirection":direction})
    return result,audit
