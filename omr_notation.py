"""Image-evidenced pitch/held-note checks on fresh OMR XML only.

Never apply key defaults to imported MusicXML, join all slurs, stretch a
voice to a meter, or repair a head which cannot be mapped unambiguously.
"""
from collections import defaultdict
from copy import deepcopy
from fractions import Fraction
import re
import xml.etree.ElementTree as ET

from omr_duration import _image_evidence, _filled_heads, _pitch_y, _plain_filled_stem
from omr_timing import _xml_notes, _retime_measure


def _coalesce_holes(holes, unit):
    """A staff line can divide one hollow head into two bright contours.

    Both fragments must occupy virtually the same horizontal head outline;
    engraved adjacent seconds have offset outlines and must stay separate.
    """
    groups = []
    for head in sorted(holes):
        for group in groups:
            first = group[0]
            overlap = min(first[3], head[3])-max(first[2], head[2])+1
            narrow = min(first[3]-first[2]+1, head[3]-head[2]+1)
            if overlap >= .6*narrow and abs(first[0]-head[0]) < .45*unit and abs(first[1]-head[1]) <= .6*unit:
                group.append(head);break
        else:groups.append([head])
    return [(sum(h[0] for h in group)/len(group), sum(h[1] for h in group)/len(group),
             min(h[2] for h in group), max(h[3] for h in group)) for group in groups]


def _whole_hollow_heads(gray, system):
    """Closed white interiors, including two fragments of a ledger head.

    This separate whole-chord probe never changes the duration detector.
    Keep area evidence: merging tiny letters/dots must not turn them into
    a note head. Adjacent seconds with offset outlines remain distinct.
    """
    import cv2
    import numpy as np
    left,right,lines=system;unit=float(np.median(np.diff(lines[:5])))
    top=max(0,round(lines[0]-4*unit));bottom=min(len(gray),round(lines[-1]+4*unit))
    binary=cv2.threshold(gray[top:bottom,left:right+1],210,255,cv2.THRESH_BINARY_INV)[1]
    contours,hierarchy=cv2.findContours(binary,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:return []
    holes=[]
    for index,contour in enumerate(contours):
        x,y,w,h=cv2.boundingRect(contour);area=cv2.contourArea(contour)
        if hierarchy[0][index][3]<0 or not (.45*unit<=w<=1.9*unit and .15*unit<=h<=1.4*unit):continue
        if area<.04*unit*unit:continue
        interior=gray[top+y:top+y+h,left+x:left+x+w]
        if (interior>=230).sum()<max(2,.1*w*h):continue
        holes.append((left+x+w/2,top+y+h/2,left+x,left+x+w-1,area))
    groups=[]
    grid_lines=[]
    for staff_lines in (lines[:5],lines[5:]):
        spacing=float(np.median(np.diff(staff_lines)))
        grid_lines+=list(staff_lines)+[staff_lines[0]-k*spacing for k in range(1,5)]+[staff_lines[-1]+k*spacing for k in range(1,5)]
    for head in sorted(holes):
        matches=[]
        for group in groups:
            if len(group)!=1:continue
            first=group[0]
            overlap=min(first[3],head[3])-max(first[2],head[2])+1
            narrow=min(first[3]-first[2]+1,head[3]-head[2]+1)
            # Only a known staff/ledger stroke may divide one head. Joining
            # across a SPACE instead would merge neighbouring chord pitches.
            split=any((first[1]-line)*(head[1]-line)<0 and abs((first[1]+head[1])/2-line)<.22*unit for line in grid_lines)
            if (overlap>=.6*narrow and abs(first[0]-head[0])<.3*unit
                    and abs(first[1]-head[1])<.85*unit and split):matches.append(group)
        if len(matches)==1:matches[0].append(head)
        elif not matches:groups.append([head])
        else:return []
    result=[]
    for group in groups:
        area=sum(h[4] for h in group);a=min(h[2] for h in group);b=max(h[3] for h in group)
        if area<.3*unit*unit or b-a+1<.8*unit:continue
        result.append((sum(h[0]*h[4] for h in group)/area,sum(h[1]*h[4] for h in group)/area,a,b))
    return result


def _whole_left_ink(gray, head, lines, left):
    """Accidentals reach above their note; dynamics below it do not.

    Require a completely empty upper/central sign region, not recognition
    of a guessed 'mp'. Ledger/staff strokes are the only removed pixels.
    """
    import numpy as np
    unit=float(np.median(np.diff(lines)));x,y,a,b=head
    l=max(round(x-2.6*unit),round(left+.7*unit));r=round(a-.6*unit)
    top,bottom=round(y-1.6*unit),round(y+.3*unit)+1
    if l<0 or top<0 or bottom>len(gray) or r-l<.5*unit:return True
    ink=gray[top:bottom,l:r]<245
    ink[ink.mean(axis=1)>.88]=False
    grid=list(lines)+[lines[0]-k*unit for k in range(1,5)]+[lines[-1]+k*unit for k in range(1,5)]
    for row in range(len(ink)):
        if min(abs(top+row-line) for line in grid)<.22*unit:ink[row]=False
    return bool(ink.any())


def _blank_whole_position(gray, x, pitch, clef, lines):
    """Positive blank pixels at a hallucinated pitch, not a detector miss."""
    import numpy as np
    unit=float(np.median(np.diff(lines)));y=_pitch_y(pitch,clef,lines)
    if y is None:return False
    a,b=round(x-.85*unit),round(x+.85*unit)+1
    top,bottom=round(y-.32*unit),round(y+.32*unit)+1
    if a<0 or b>gray.shape[1] or top<0 or bottom>len(gray):return False
    ink=gray[top:bottom,a:b]<245
    grid=list(lines)+[lines[0]-k*unit for k in range(1,5)]+[lines[-1]+k*unit for k in range(1,5)]
    kept=[]
    for row in range(len(ink)):
        if min(abs(top+row-line) for line in grid)>=.22*unit:kept.append(row)
    return len(kept)>=2 and not ink[kept].any()


def _whole_chord_repair(events, heads, gray, system, clefs, fifths, left, number):
    """One complete, aligned whole-chord attack on BOTH piano staves.

    An unchanged opposite chord and agreeing pitches anchor the column.
    Only one staff may change. Removed distant pitches require blank image
    pixels; the near-step case additionally requires two agreeing heads and
    an extra, closed oval. No meter, song identity or previous chord is used.
    """
    import numpy as np
    if fifths is None or clefs.get('1')!='G2' or clefs.get('2')!='F4':return events,[]
    by_staff={staff:[e for e in events if e[0].findtext('staff','1')==staff] for staff in ('1','2')}
    if sum(map(len,by_staff.values()))!=len(events) or any(not 2<=len(es)<=4 for es in by_staff.values()):return events,[]
    for es in by_staff.values():
        if len({_pitch(n) for n,s,d,i in es})!=len(es) or len({n.findtext('voice') for n,s,d,i in es})!=1:return events,[]
        for n,s,d,i in es:
            if (s!=0 or d!=4 or n.findtext('type')!='whole' or not re.fullmatch(r'[A-G][1-7]',_pitch(n) or '')
                    or any(n.find(tag) is not None for tag in ('dot','accidental','tie','time-modification'))
                    or any(child.tag!='fermata' for child in n.findall('notations/*'))):return events,[]
    grid={};units={}
    for staff,lines,other in (('1',system[2][:5],system[2][5:]),('2',system[2][5:],system[2][:5])):
        unit=float(np.median(np.diff(lines)));units[staff]=unit;grid[staff]=[]
        for h in heads:
            if not lines[0]-3*unit<=h[1]<=lines[-1]+3*unit:continue
            if min(abs(h[1]-v) for v in lines)>=min(abs(h[1]-v) for v in other):continue
            names=[f'{letter}{octave}' for octave in range(1,8) for letter in 'CDEFGAB'
                   if abs(_pitch_y(f'{letter}{octave}',clefs[staff],lines)-h[1])<.28*unit]
            if len(names)==1:grid[staff].append((h,names[0]))
    recognized={staff:{_pitch(n) for n,s,d,i in es} for staff,es in by_staff.items()}
    cohorts={}
    for anchor,name in grid['2']:
        if name not in recognized['2']:continue
        selected={staff:[(h,p) for h,p in grid[staff] if abs(h[0]-anchor[0])<.45*units[staff]] for staff in ('1','2')}
        if any(not 2<=len(hs)<=4 or len({p for h,p in hs})!=len(hs) for hs in selected.values()):continue
        detected={staff:{p for h,p in hs} for staff,hs in selected.items()}
        if any(not recognized[staff]&detected[staff] for staff in ('1','2')):continue
        if sum(len(recognized[s]&detected[s]) for s in ('1','2'))<3:continue
        if detected['2']!=recognized['2'] or detected['1']==recognized['1']:continue
        key=tuple(tuple(sorted((p,h[0],h[1]) for h,p in selected[s])) for s in ('1','2'))
        cohorts[key]=selected
    if len(cohorts)!=1:return events,[]
    selected=next(iter(cohorts.values()));target={p for h,p in selected['1']}
    for staff,hs in selected.items():
        low=min(h[1] for h,p in hs);high=max(h[1] for h,p in hs);unit=units[staff]
        staff_lines=system[2][:5] if staff=='1' else system[2][5:]
        staff_grid=list(staff_lines)+[staff_lines[0]-k*unit for k in range(1,5)]+[staff_lines[-1]+k*unit for k in range(1,5)]
        for h,p in hs:
            stem=_local_head_stem(gray,h,unit)
            # Joined chord rims are not stems. A real stem projects outside
            # the whole cohort as a narrow isolated column. Connected letters
            # of dynamics below a head must not be mistaken for that stem.
            if stem is None:continue
            sx,y0,y1=stem
            for top,bottom in ((round(y0),round(low-.9*unit)),(round(high+.9*unit),round(y1)+1)):
                if bottom-top<.75*unit:continue
                rows=[r for r in range(max(0,top),min(len(gray),bottom)) if min(abs(r-line) for line in staff_grid)>=.22*unit]
                if len(rows)<.6*unit:continue
                side_columns=[c for c in range(max(0,round(sx-.9*unit)),min(gray.shape[1],round(sx+.9*unit)+1))
                              if abs(c-sx)>=.4*unit]
                if not side_columns:continue
                centre=gray[rows,round(sx)]<245
                sides=gray[np.ix_(rows,side_columns)]<245
                if centre.mean()>=.9 and (sides.any(axis=1)).mean()<.2:return events,[]
    removed=recognized['1']-target;added=target-recognized['1']
    if not removed or not added or len(removed)>2 or len(added)>2 or abs(len(target)-len(recognized['1']))>1:return events,[]
    lines=system[2][:5];unit=units['1'];x=float(np.median([h[0] for h,p in selected['1']]))
    if any(_whole_left_ink(gray,h,lines,left) for h,p in selected['1'] if p in added):return events,[]
    blank=all(_blank_whole_position(gray,x,p,clefs['1'],lines) for p in removed)
    ordinal=lambda p:int(p[1])*7+'CDEFGAB'.index(p[0])
    near=(len(removed)==1 and len(recognized['1']&target)>=2 and len(target)==len(recognized['1'])+1
          and min(abs(ordinal(p)-ordinal(next(iter(removed)))) for p in added)==1)
    if not blank and not near:return events,[]
    kept=[e for e in events if not (e[0].findtext('staff','1')=='1' and _pitch(e[0]) in removed)]
    template=next(n for n,s,d,i in by_staff['1'] if _pitch(n) in removed)
    for p in sorted(added):
        n=deepcopy(template);n.attrib.pop('id',None)
        for tag in ('chord','notations','tie','accidental','beam'):
            for child in list(n.findall(tag)):n.remove(child)
        _set_pitch(n,p,_default_alter(p,fifths))
        kept.append((n,Fraction(0),Fraction(4),len(events)+len(kept)))
    audit={'measure':number,'staff':'1','removedPitches':sorted(removed),'addedPitches':sorted(added),
           'notesBefore':len(recognized['1']),'notesAfter':len(target),'reason':'aligned-whole-ovals-and-unchanged-opposite-chord'}
    return kept,[audit]


def _sign_near(gray, head, unit, left_limit=0, lines=(), stems=(), heads=(), head_margin=.6):
    """Absence of an accidental needs a legible, empty left-hand region.

    Use a higher threshold than the head detector so faint naturals/sharps
    also veto a repair. Staff lines are removed, never a short sign stroke.
    """
    import cv2
    import numpy as np
    x, y, _, _ = head
    left = max(round(x-2.6*unit), round(left_limit))
    right = min(round(x-.8*unit), round(head[2]-head_margin*unit))
    top, bottom = round(y-1.6*unit), round(y+1.6*unit)+1
    if left < 0 or top < 0 or bottom > len(gray) or right-left < .5*unit:return True
    area = cv2.threshold(gray[top:bottom, left:right], 245, 255, cv2.THRESH_BINARY_INV)[1]
    # A line crossing the entire crop is not an accidental. Thin vertical
    # strokes and adjacent note stems remain conservative vetoes.
    area[(area > 0).mean(axis=1) > .88] = 0
    # Ledger lines have the same spacing as the staff; a stroke across a
    # ledger head must not masquerade as a local accidental beside it.
    grid_lines = [line for line in lines]
    if lines:grid_lines += [lines[0]-k*unit for k in range(1, 4)]+[lines[-1]+k*unit for k in range(1, 4)]
    for line in grid_lines:
        for row in range(len(area)):
            if abs(top+row-line) < .22*unit:area[row] = 0
    for sx, sy0, sy1 in stems:
        a, b = max(0, round(sx-.18*unit)-left), min(area.shape[1], round(sx+.18*unit)-left+1)
        if a < b:area[max(0, round(sy0)-top):min(len(area), round(sy1)-top+1), a:b] = 0
    for hx,hy,ha,hb in heads:
        if hx>=x:continue
        a,b=max(0,round(ha-.15*unit)-left),min(area.shape[1],round(hb+.15*unit)-left+1)
        if a<b:area[max(0,round(hy-.55*unit)-top):min(len(area),round(hy+.55*unit)-top+1),a:b]=0
    for column in area.T:
        rows = np.flatnonzero(column)
        if len(rows) >= .4*unit and rows[-1]-rows[0] > .7*unit:return True
    contours, _ = cv2.findContours(area, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return any(h > .7*unit and cv2.contourArea(c) > .04*unit*unit
               for c in contours for _, _, w, h in [cv2.boundingRect(c)])


def _curve_between(gray, first, second, unit, lines):
    """A short bowed stroke ending at two adjacent equal-height heads.

    Require a continuous curved component, not staff/ledger lines, beams,
    stems or a mark merely located somewhere above a repeated pitch.
    """
    import cv2
    import numpy as np
    x1, y1, _, _ = first; x2, y2, _, _ = second
    if not 2.5*unit < x2-x1 < 16*unit or abs(y1-y2) > .35*unit:return False
    left, right = round(x1+1.1*unit), round(x2-.8*unit)
    if right-left < 1.2*unit:return False
    y = (y1+y2)/2
    for side in (-1, 1):
        a, b = sorted((y+side*.15*unit, y+side*1.9*unit))
        top, bottom = max(0, round(a)), min(len(gray), round(b)+1)
        area = cv2.threshold(gray[top:bottom, left:right+1], 210, 255, cv2.THRESH_BINARY_INV)[1]
        for line in lines:
            for row in range(len(area)):
                if abs(top+row-line) < .12*unit:area[row] = 0
        points = [(col, float(np.flatnonzero(area[:, col]).mean())+top)
                  for col in range(area.shape[1]) if area[:, col].any()]
        if len(points) < .55*area.shape[1]:continue
        edge_left = [v for col, v in points if col < .2*area.shape[1]]
        edge_right = [v for col, v in points if col > .8*area.shape[1]]
        if len(edge_left) < 2 or len(edge_right) < 2:continue
        xs, ys = np.array(points).T;coefficients = np.polyfit(xs, ys, 2)
        fit = np.polyval(coefficients, xs)
        if side*coefficients[0] >= 0 or float(np.max(np.abs(fit-ys))) > .4*unit:continue
        middle = float(np.polyval(coefficients, (area.shape[1]-1)/2))
        if side*(middle-np.median(edge_left+edge_right)) < .15*unit or side*(middle-y) < .45*unit:continue
        # A curve may cross a staff line. Missing columns are permitted ONLY
        # at that known line, not bridged through blank image pixels.
        absent = [col for col in range(area.shape[1]) if not area[:, col].any()]
        if any(min(abs(float(np.polyval(coefficients, col))-line) for line in lines) > .25*unit for col in absent):continue
        return True
    return False


def _pitch(note):
    p = note.find('pitch')
    return None if p is None else p.findtext('step', '')+p.findtext('octave', '')


def _local_head_stem(gray, head, unit):
    """A flag can widen a contour; verify the connected stem column itself."""
    import numpy as np
    x,y,a,b=head
    for edge,direction in ((b,-1),(a,1)):
        for column in range(max(0,round(edge-.35*unit)),min(gray.shape[1],round(edge+.35*unit)+1)):
            start,end=sorted((round(y),round(y+direction*2.5*unit)))
            if start < 0 or end >= len(gray):continue
            ink=gray[start:end+1,column]<245
            if ink.mean() >= .9 and np.max(np.convolve((~ink).astype(int),np.ones(3,dtype=int),'valid')) < 3:
                return (float(column),float(start),float(end))
    return None


def _default_alter(name, fifths):
    return 1 if fifths > 0 and name[0] in 'FCGDAEB'[:fifths] else -1 if fifths < 0 and name[0] in 'BEADGCF'[:-fifths] else 0


def _isolated_dotted_head(gray, head, next_head, lines, stems):
    """Positive single dot; no flag, beam, rest or other ink in the gap.

    Only ordinary in-staff, stem-up-range heads apply. A missing stem is not
    itself duration evidence; onset/end anchors are checked by the caller.
    """
    import cv2
    import numpy as np
    unit=float(np.median(np.diff(lines)));x,y,a,b=head
    if not lines[2]<y<lines[-1] or next_head[0]-x<4*unit:return False
    left,right=round(b+.2*unit),round(x+2.3*unit)+1
    top,bottom=round(y-.65*unit),round(y+.65*unit)+1
    if top<0 or bottom>len(gray):return False
    dot_area=(gray[top:bottom,left:right]<210).astype(np.uint8)
    for row in range(len(dot_area)):
        if min(abs(top+row-line) for line in lines)<.22*unit:dot_area[row]=0
    count,labels,stats,centres=cv2.connectedComponentsWithStats(dot_area,8)
    dots=[(sx+left,sy+top,w,h) for sx,sy,w,h,pixels in stats[1:]
          if 1<=w<=.65*unit and 1<=h<=.65*unit and pixels>=max(2,.06*unit*unit)
          and abs(sy+top+(h-1)/2-y)<.35*unit]
    if len(dots)!=1:return False
    dx,dy,dw,dh=dots[0]
    # Check both sides of the head for a flag, including a downward flag;
    # then the full staff-height gap for any printed rest.
    for l,r,t,bt in ((round(a-unit),round(b+2*unit)+1,round(y-3*unit),round(y+3*unit)+1),
                     (round(b+.2*unit),round(next_head[2]-.3*unit),round(lines[0]-1.6*unit),round(lines[-1]+1.6*unit)+1)):
        if l<0 or t<0 or r>gray.shape[1] or bt>len(gray) or r<=l:return False
        ink=gray[t:bt,l:r]<245
        ink[ink.mean(axis=1)>.88]=False
        for row in range(len(ink)):
            if min(abs(t+row-line) for line in lines)<.22*unit:ink[row]=False
        ink[max(0,round(y-.65*unit)-t):min(len(ink),round(y+.65*unit)-t+1),
            max(0,round(a-.2*unit)-l):min(ink.shape[1],round(b+.2*unit)-l+1)]=False
        ink[max(0,dy-1-t):min(len(ink),dy+dh+1-t),max(0,dx-1-l):min(ink.shape[1],dx+dw+1-l)]=False
        for sx,sy0,sy1 in stems:
            if abs(sx-b)<.55*unit and abs(sy1-y)<.9*unit:
                ink[max(0,round(sy0)-t):min(len(ink),round(sy1)-t+1),
                    max(0,round(sx-.18*unit)-l):min(ink.shape[1],round(sx+.18*unit)-l+1)]=False
        if ink.any():return False
    return True


def _sharp_header_end(gray, lines, left, before, fifths, clefs):
    """Require the complete ordered sharp pattern on BOTH piano staves.

    A lone accidental, clef stroke or an unrecognized header must never be
    erased from the local-sign probe. Only the usual G2/F4 engraving applies.
    """
    import numpy as np
    if not 2 <= fifths <= 7 or clefs.get('1') != 'G2' or clefs.get('2') != 'F4':return None
    results=[]
    for staff_lines,clef,names in ((lines[:5],'G2','F5 C5 G5 D5 A4 E5 B4'.split()),
                                   (lines[5:],'F4','F3 C3 G3 D3 A2 E3 B2'.split())):
        unit=float(np.median(np.diff(staff_lines)))
        a,b=round(left+3*unit),round(before-.6*unit)
        if b-a < fifths*.8*unit:return None
        choices=[]
        for name in names[:fifths]:
            y=_pitch_y(name,clef,staff_lines);top,bottom=round(y-1.7*unit),round(y+1.7*unit)+1
            if top<0 or bottom>len(gray):return None
            ink=gray[top:bottom,a:b]<245
            for row in range(len(ink)):
                if min(abs(top+row-line) for line in staff_lines)<.18*unit:ink[row]=False
            # Engraved crossbars slope slightly. A one-pixel vertical band
            # covers that slope without inventing a horizontal overhang.
            bar_ink=ink.copy();bar_ink[1:] |= ink[:-1];bar_ink[:-1] |= ink[1:]
            pairs=[]
            for x in range(ink.shape[1]):
                for dx in range(max(2,round(.3*unit)),round(.9*unit)+1):
                    if x+dx>=ink.shape[1] or min(ink[:,x].mean(),ink[:,x+dx].mean())<.32:continue
                    overhang=max(1,round(.2*unit))
                    if x<overhang or x+dx+overhang>=ink.shape[1]:continue
                    rows=bar_ink[:,x-overhang:x+dx+overhang+1].mean(axis=1)
                    bars=[top+r for r in range(len(ink)) if rows[r]>.8 and abs(top+r-y)<unit]
                    # Two crossbars straddling the expected sharp centre.
                    if bars and min(bars)<y-.2*unit and max(bars)>y+.2*unit:
                        pairs.append((a+x,a+x+dx))
            choices.append(pairs)
        paths=[()]
        for candidates in choices:
            paths=[path+(candidate,) for path in paths for candidate in candidates
                   if not path or .8*unit < candidate[0]-path[-1][0] < 2*unit]
            if not paths or len(paths)>500:return None
        # Stroke thickness may produce duplicate paths, but different glyph
        # sequences/positions remain ambiguous and must not unlock repairs.
        centres=[tuple((x+end)/2 for x,end in path) for path in paths]
        if any(max(v[i] for v in centres)-min(v[i] for v in centres)>.5*unit for i in range(fifths)):return None
        results.append((np.median(centres,axis=0),max(path[-1][1] for path in paths)+.45*unit))
    unit=float(np.median(np.diff(lines[:5])))
    if any(abs(a-b)>.6*unit for a,b in zip(results[0][0],results[1][0])):return None
    return max(result[1] for result in results)


def _set_pitch(note, name, alter):
    p = note.find('pitch');p.find('step').text = name[0];p.find('octave').text = name[1]
    node = p.find('alter')
    if node is None:
        node = ET.Element('alter');p.insert(list(p).index(p.find('step'))+1, node)
    node.text = str(alter)


def _tie(first, second):
    starts = first.findall("./notations/slur[@type='start']")
    stops = second.findall("./notations/slur[@type='stop']")
    shared = {s.get('number') for s in starts} & {s.get('number') for s in stops}
    if not stops and len(starts) == 1:shared = {starts[0].get('number')}
    for note, kind in ((first, 'start'), (second, 'stop')):
        if kind not in {t.get('type') for t in note.findall('tie')}:
            offset = list(note).index(note.find('duration'))+1
            note.insert(offset, ET.Element('tie', type=kind))
        notation = note.find('notations')
        if notation is None:notation = ET.SubElement(note, 'notations')
        if kind not in {t.get('type') for t in notation.findall('tied')}:
            ET.SubElement(notation, 'tied', type=kind)
        # Remove only the endpoint whose geometry was positively identified
        # as this tie; unrelated phrasing/articulations are not converted.
        for slur in list(notation.findall('slur')):
            if slur.get('type') == kind and slur.get('number') in shared:notation.remove(slur)


def verify_notation(root, gray, systems, limit=200):
    """Return bounded audits; every replacement is per-measure atomic.

    Existing clocks/durations survive. An isolated whole chord can have its
    membership repaired from closed ovals and an unchanged opposite chord;
    distant removed pitches additionally need blank source pixels.
    A new non-whole attack requires either the
    visible plain quarter of an image-confirmed tie, or an isolated dotted
    quarter between two independently mapped opposite-staff attacks. No bar
    is extended, and ambiguous flags/rests/glyphs remain review findings.
    """
    import numpy as np
    audits = {'headPitchCorrections': [], 'alterationCorrections': [], 'unresolvedAlterations': [], 'unmatchedSolidHeads': [], 'omittedAttackRecoveries': [], 'unresolvedHollowChords': [], 'chordCompositionCorrections': [],
              'tieCorrections': [], 'heldNoteRecoveries': []}
    parts = root.findall('part')
    if len(parts) != 1:return audits
    measures = parts[0].findall('measure');contexts = []
    for system in systems:
        holes, stems, bounds = _image_evidence(gray, system, 245, True, hole_width=1.9, allow_line_holes=True)
        holes = _coalesce_holes(holes, float(np.median(np.diff(system[2][:5]))))
        # Clef dots are round; a printed solid note head is a wider oval.
        # Do not change the duration detector's existing permissive default.
        filled = _filled_heads(gray, system, max_width=2.4, min_aspect=1.2)
        whole_heads = _whole_hollow_heads(gray,system)
        if not bounds:return audits
        unit = float(np.median(np.diff(system[2][:5])))
        # Two strokes of a final/repeat barline enclose no musical measure.
        groups = []
        for boundary in bounds:
            if groups and boundary-groups[-1][-1] < .9*unit:groups[-1].append(boundary)
            else:groups.append([boundary])
        bounds = [sum(group)/len(group) for group in groups]
        for left, right in zip(bounds, bounds[1:]):
            unit = float(np.median(np.diff(system[2][:5])))
            inside = lambda h:left+unit < h[0] < right-unit
            contexts.append((system, unit, [h for h in holes if inside(h)], [h for h in filled if inside(h)], stems, left,
                             [h for h in whole_heads if inside(h)]))
    if len(contexts) != len(measures):return audits
    divisions = Fraction(1);clefs = {};fifths = None
    for number, (original, context) in enumerate(zip(measures, contexts), 1):
        if sum(map(len, audits.values())) >= min(200, limit):break
        measure = deepcopy(original);system, unit, holes, filled, stems, left, whole_heads = context
        attributes = measure.findall('attributes')
        for attr in attributes:
            if attr.find('divisions') is not None:divisions = Fraction(attr.findtext('divisions'))
            for clef in attr.findall('clef'):
                clefs[clef.get('number', '1')] = clef.findtext('sign', '')+clef.findtext('line', '')
            if attr.find('key') is not None:
                key = attr.find('key');text = key.findtext('fifths', '')
                fifths = int(text) if re.fullmatch(r'-?[0-7]', text) and key.find('key-step') is None else None
        first_note = next((i for i, child in enumerate(measure) if child.tag == 'note'), len(measure))
        if divisions <= 0 or any(list(measure).index(attr) > first_note for attr in attributes):continue
        notes = _xml_notes(measure, divisions)
        if notes is None or any(n.find('time-modification') is not None for n, _, _, _ in notes):continue
        events = [(n, start, duration, index) for index, (n, _, start, duration) in enumerate(notes)]
        local = {field: [] for field in audits};recovered = False
        events,chord_audit=_whole_chord_repair(events,whole_heads,gray,system,clefs,fifths,left,number)
        if chord_audit:
            local['chordCompositionCorrections']=chord_audit;recovered=True
        uncertain_alters = set()
        attack_heads = {}
        # Match a complete monophonic solid-head sequence in time/x order.
        # Grouping only by the already-recognized pitch misses a singleton
        # wrong step or accidental among otherwise identical repeated notes.
        for staff, lines in (('1', system[2][:5]), ('2', system[2][5:])):
            sequence = sorted((e for e in events if e[0].findtext('staff','1') == staff
                               and _pitch(e[0]) and e[0].findtext('type') in ('quarter','eighth','16th','32nd')),
                              key=lambda e:(e[1],e[3]))
            if fifths is None or staff not in clefs or len(sequence) < 2:continue
            if len({e[1] for e in sequence}) != len(sequence) or len({e[0].findtext('voice') for e in sequence}) != 1:continue
            if any(n.find('accidental') is not None for n,_,_,_ in events
                   if n.findtext('staff','1') == staff):continue
            step = float(np.median(np.diff(lines)))
            # A head must be nearer this staff than the other staff. Ledger
            # notes beyond three line spaces are left for manual review.
            other_lines = system[2][5:] if staff == '1' else system[2][:5]
            heads = sorted(h for h in filled if lines[0]-3*step <= h[1] <= lines[-1]+3*step
                           and min(abs(h[1]-v) for v in lines) < min(abs(h[1]-v) for v in other_lines))
            if len(heads) != len(sequence) or any(b[0]-a[0] < 1.2*step for a,b in zip(heads,heads[1:])):continue
            header_end=_sharp_header_end(gray,system[2],left,heads[0][2],fifths,clefs) if abs(left-system[0])<step else None
            sign_left=max(left+.7*step,header_end+.3*step) if header_end is not None else left+.7*step
            head_stems=[]
            for head in heads:
                attached=[(sx,a,b) for sx,a,b in stems if (abs(sx-head[3])<.55*step and abs(b-head[1])<.9*step)
                          or (abs(sx-head[2])<.55*step and abs(a-head[1])<.9*step)]
                if not attached:
                    stem=_local_head_stem(gray,head,step)
                    if stem is not None:attached=[stem]
                head_stems.append(attached)
            source_stems=[stem for attached in head_stems for stem in attached]
            candidates = [];valid = True
            for (n,start,duration,index),head,attached in zip(sequence,heads,head_stems):
                old = _pitch(n)
                if not re.fullmatch(r'[A-G][0-9]',old):valid=False;break
                names = [f'{letter}{octave}' for octave in range(1,8) for letter in 'CDEFGAB']
                near = [name for name in names if _pitch_y(name,clefs[staff],lines) is not None
                        and abs(_pitch_y(name,clefs[staff],lines)-head[1]) < .28*step]
                ordinal = lambda name:int(name[1])*7+'CDEFGAB'.index(name[0])
                if len(near) != 1 or abs(ordinal(near[0])-ordinal(old)) > 1:valid=False;break
                # A damaged first stem can still have an isolated solid oval
                # in a complete one-voice sequence following a verified header.
                neighbour_stem=header_end is not None and head is heads[0] and any(
                    _local_head_stem(gray,h,step) is not None for h in heads[1:])
                safe=(bool(attached) or neighbour_stem) and not _sign_near(gray,head,step,sign_left,lines,source_stems,heads,.2)
                candidates.append((n,old,near[0],_default_alter(near[0],fifths),safe))
            if not valid:continue
            for event,head in zip(sequence,heads):attack_heads[(staff,event[1])]=head
            for n,old,new,alter,safe in candidates:
                if not safe:continue
                # An unreadable local sign may govern later repetitions in
                # this bar. Do not restore a key default past such evidence.
                uncertain_scope = any(not ok and candidate[0] == new[0] for _,_,candidate,_,ok in candidates)
                if uncertain_scope:
                    uncertain_alters.add((staff,new[0]))
                    if n.findtext('pitch/alter','0') != str(alter) and not any(
                            item['staff']==staff and item['pitch']==new for item in local['unresolvedAlterations']):
                        local['unresolvedAlterations'].append({'measure':number,'staff':staff,'pitch':new,
                            'reason':'unreadable-earlier-sign-or-stem'})
                if uncertain_scope and old == new:continue
                if n.find('tie') is not None or n.find('notations/tied') is not None or n.find('notations/slur') is not None:continue
                before=n.findtext('pitch/alter','0')
                # A visible step and the accidental scope are separate evidence.
                # With an unreadable earlier sign, preserve the existing alter
                # rather than invent a key default for the newly identified step.
                if uncertain_scope:
                    if not re.fullmatch(r'-?[0-2]',before):continue
                    alter=int(before)
                if old != new:
                    local['headPitchCorrections'].append({'measure':number,'from':old,'to':new,'alter':alter,'staff':staff,
                                                         'reason':'complete-solid-sequence-clef-grid'})
                elif before != str(alter):
                    local['alterationCorrections'].append({'measure':number,'pitch':new,'from':before,'to':alter,'staff':staff,
                                                          'reason':'complete-solid-sequence-no-local-sign'})
                if old != new or before != str(alter):_set_pitch(n,new,alter)
        # An independently complete opposite-staff sequence anchors the x
        # coordinate of a singleton attack. This identifies its existing head
        # without inventing the duration/onset of an extra, omitted head.
        for n,start,duration,index in events:
            staff=n.findtext('staff','1');name=_pitch(n)
            if fifths is None or staff not in clefs or not name or n.findtext('type') not in ('quarter','eighth','16th','32nd'):continue
            if n.find('tie') is not None or n.find('notations/tied') is not None or n.find('notations/slur') is not None:continue
            if any(e.find('accidental') is not None for e,_,_,_ in events if e.findtext('staff','1')==staff):continue
            anchor=attack_heads.get(('2' if staff=='1' else '1',start))
            if anchor is None:continue
            lines=system[2][:5] if staff=='1' else system[2][5:];step=float(np.median(np.diff(lines)))
            y=_pitch_y(name,clefs[staff],lines)
            if y is None:continue
            visible=sorted(h for h in filled if abs(h[1]-y)<.28*step)
            matched=[h for h in visible if abs(h[0]-anchor[0])<.65*step]
            if len(matched)!=1:continue
            head=matched[0];attached=_local_head_stem(gray,head,step)
            if attached is None:continue
            same=[e for e,s,d,i in events if e.findtext('staff','1')==staff and _pitch(e)==name
                  and e.findtext('type') in ('quarter','eighth','16th','32nd')]
            if len(same)==1 and len(visible)==2 and visible[0][0]<head[0]-1.2*step:
                local['unmatchedSolidHeads'].append({'measure':number,'staff':staff,'pitch':name,'count':1,
                    'reason':'visible-earlier-head-without-musical-attack'})
            alter=_default_alter(name,fifths);before=n.findtext('pitch/alter','0')
            if (staff,name[0]) in uncertain_alters:continue
            source_stems=[stem for h in visible for stem in [_local_head_stem(gray,h,step)] if stem is not None]
            if any(_sign_near(gray,h,step,left+.7*step,lines,source_stems,visible,.2) for h in visible if h[0]<=head[0]):continue
            if before!=str(alter):
                _set_pitch(n,name,alter)
                local['alterationCorrections'].append({'measure':number,'pitch':name,'from':before,'to':alter,'staff':staff,
                    'reason':'opposite-staff-attack-anchor-no-local-sign'})
            initial=attack_heads.get(('2' if staff=='1' else '1',Fraction(0)))
            earlier=[e for e,s,d,i in events if e.findtext('staff','1')==staff and e.findtext('voice')==n.findtext('voice') and s<start]
            if (staff=='2' and start==Fraction(3,2) and duration==Fraction(1,2) and n.findtext('type')=='eighth'
                    and not earlier and len(same)==1 and len(visible)==2 and head==visible[1] and initial is not None
                    and abs(initial[0]-visible[0][0])<.65*step
                    and _isolated_dotted_head(gray,visible[0],head,lines,stems)):
                ticks=Fraction(3,2)*divisions
                if ticks.denominator!=1:continue
                added=deepcopy(n)
                for tag in ('chord','tie','notations','accidental','beam','dot'):
                    for node in list(added.findall(tag)):added.remove(node)
                added.attrib.pop('id',None)
                added.find('type').text='quarter'
                added.find('duration').text=str(ticks.numerator)
                added.insert(list(added).index(added.find('type'))+1,ET.Element('dot'))
                events.append((added,Fraction(0),Fraction(3,2),len(events)))
                recovered=True
                local['unmatchedSolidHeads']=[item for item in local['unmatchedSolidHeads'] if not (item['staff']==staff and item['pitch']==name)]
                local['omittedAttackRecoveries'].append({'measure':number,'staff':staff,'pitch':name,'onset':'0','duration':'3/2',
                    'reason':'isolated-dot-and-two-opposite-staff-anchors'})
        # A single hollow chord can contain an isolated wrong accidental;
        # requiring repeated occurrences of each pitch would miss that case.
        chords=defaultdict(list)
        for n,start,duration,index in events:
            if _pitch(n) and n.findtext('type') in ('half','whole'):
                chords[(n.findtext('staff','1'),start,n.findtext('voice'))].append(n)
        for (staff,start,voice),chord in chords.items():
            if fifths is None or staff not in clefs or not 2<=len(chord)<=4:continue
            if len({_pitch(n) for n in chord}) != len(chord):continue
            # A bar can have the correct length while a whole chord contains
            # hallucinated pitches. Report positive image disagreement; never
            # synthesize its missing composition from key defaults or a fermata.
            if clefs[staff] in ('G2','F4') and all(n.findtext('type')=='whole' for n in chord):
                lines=system[2][:5] if staff=='1' else system[2][5:]
                step=float(np.median(np.diff(lines)))
                other_lines=system[2][5:] if staff=='1' else system[2][:5]
                visible=[h for h in holes if h[3]-h[2]+1>=.9*step
                         and min(abs(h[1]-v) for v in lines)<min(abs(h[1]-v) for v in other_lines)]
                names=[f'{letter}{octave}' for octave in range(1,8) for letter in 'CDEFGAB']
                grid=[(h,[p for p in names if abs(_pitch_y(p,clefs[staff],lines)-h[1])<.28*step]) for h in visible]
                grid=[(h,p[0]) for h,p in grid if len(p)==1]
                whole_staff=[n for n,s,d,i in events if n.findtext('staff','1')==staff]
                if grid and len(whole_staff)==len(chord) and max(h[0] for h,p in grid)-min(h[0] for h,p in grid)<.4*step:
                    detected={p for h,p in grid};recognized={_pitch(n) for n in chord}
                    # Missing detections alone are not disagreement evidence:
                    # ledger lines can split an otherwise correct head. Require
                    # two agreeing anchors plus an actually different head.
                    # Coalesced holes on ledger lines can shift their centre
                    # towards an adjacent pitch; do not use them as the extra
                    # conflicting head. Keep the positive witness in-staff.
                    # A white fragment below a staff stroke is not a complete
                    # conflicting head. Require agreement with the independent
                    # area/line-split whole-oval probe for the extra witness;
                    # replacing the entire grid could merge adjacent heads.
                    extra=[h for h,p in grid if p not in recognized and lines[0]<=h[1]<=lines[-1]+.28*step
                           and any(abs(h[0]-w[0])<.25*step and abs(h[1]-w[1])<.25*step for w in whole_heads)]
                    if len(recognized & detected)>=2 and extra:
                        local['unresolvedHollowChords'].append({'measure':number,'staff':staff,
                            'recognizedCount':len(recognized),'detectedCount':len(detected),
                            'reason':'whole-chord-pitches-disagree-with-visible-heads'})
            if any(n.find('accidental') is not None for n,_,_,_ in events if n.findtext('staff','1')==staff):continue
            if any(n.find('tie') is not None or n.find('notations/tied') is not None
                   or n.find('notations/slur') is not None for n in chord):continue
            lines=system[2][:5] if staff=='1' else system[2][5:]
            step=float(np.median(np.diff(lines)))
            candidates=[]
            for n in chord:
                y=_pitch_y(_pitch(n),clefs[staff],lines)
                candidates.append([h for h in holes if y is not None and abs(h[1]-y)<.28*step])
            matches=[]
            for anchor in candidates[0]:
                peers=[[h for h in group if abs(h[0]-anchor[0])<.65*step] for group in candidates[1:]]
                if not all(len(group)==1 for group in peers):continue
                match=[anchor]+[group[0] for group in peers]
                joined=[_local_head_stem(gray,h,step) for h in match]
                if all(stem is not None for stem in joined) and max(s[0] for s in joined)-min(s[0] for s in joined)<.4*step:
                    matches.append(match)
            if len(matches)!=1:continue
            match=matches[0]
            # Mask only stems attached to an actual solid oval or this chord,
            # not arbitrary long strokes of a sharp/natural elsewhere.
            attached=[(x,a,b) for x,a,b in stems if any(
                (abs(x-h[3])<.55*step and abs(b-h[1])<.9*step)
                or (abs(x-h[2])<.55*step and abs(a-h[1])<.9*step) for h in filled+match)]
            for n,head,possibilities in zip(chord,match,candidates):
                name=_pitch(n);alter=_default_alter(name,fifths);before=n.findtext('pitch/alter','0')
                if before==str(alter) or (staff,name[0]) in uncertain_alters:continue
                if any(h[0]<head[0]-.65*step for h in possibilities):continue
                if _sign_near(gray,head,step,left+.7*step,lines,attached):continue
                _set_pitch(n,name,alter)
                local['alterationCorrections'].append({'measure':number,'pitch':name,'from':before,'to':alter,
                    'staff':staff,'reason':'unique-hollow-chord-grid-no-local-sign'})
        groups = defaultdict(list)
        for n, start, duration, index in events:
            name = _pitch(n)
            if name and re.fullmatch(r'[A-G][0-9]', name):groups[(n.findtext('staff', '1'), name)].append((n, start, duration, index))
        for (staff, name), occurrences in groups.items():
            lines = system[2][:5] if staff == '1' else system[2][5:] if staff == '2' else None
            if lines is None or staff not in clefs:continue
            staff_unit = float(np.median(np.diff(lines)))
            attached_stems = [(sx, sy0, sy1) for sx, sy0, sy1 in stems
                              if any((abs(sx-h[3]) < .55*staff_unit and abs(sy1-h[1]) < .9*staff_unit)
                                     or (abs(sx-h[2]) < .55*staff_unit and abs(sy0-h[1]) < .9*staff_unit) for h in holes+filled)]
            sign_near = lambda head:_sign_near(gray, head, staff_unit, left+.7*staff_unit, lines, attached_stems)
            y = _pitch_y(name, clefs[staff], lines)
            if y is None:continue
            occurrence_order = sorted(occurrences, key=lambda e:(e[1], e[3]))
            half = [e for e in occurrence_order if e[0].findtext('type') == 'half' and e[2] == 2]
            linked = any(n.find('tie') is not None or n.find('notations/tied') is not None
                         or (start == 0 and n.find("notations/slur[@type='stop']") is not None)
                         or n.find('accidental') is not None for n, start, _, _ in occurrences)
            # Two repeated half heads can reveal a one-step diatonic error.
            # Do not assign a new height from a key signature alone.
            if len(half) == len(occurrences) >= 2 and fifths is not None and not linked:
                near = [h for h in holes if abs(h[1]-y) < 1.25*staff_unit]
                old = [h for h in near if abs(h[1]-y) < .28*staff_unit]
                other = [_pitch_y(p, clefs[staff], lines) for s, p in groups if s == staff and p != name]
                unused = [h for h in near if not any(v is not None and abs(h[1]-v) < .3*staff_unit for v in other)]
                ordinal = lambda p:int(p[1])*7+'CDEFGAB'.index(p[0])
                candidates = [f'{step}{octave}' for octave in range(1, 8) for step in 'CDEFGAB'
                              if 0 < abs(ordinal(f'{step}{octave}')-ordinal(name)) <= 2]
                candidates = [p for p in candidates if all(abs(h[1]-_pitch_y(p, clefs[staff], lines)) < .28*staff_unit for h in unused)]
                half_stems = all(any((abs(sx-h[3]) < .55*staff_unit and abs(sy1-h[1]) < .6*staff_unit)
                                    or (abs(sx-h[2]) < .55*staff_unit and abs(sy0-h[1]) < .6*staff_unit)
                                    for sx, sy0, sy1 in attached_stems) for h in unused)
                if not old and len(unused) == len(half) and len(candidates) == 1 and half_stems and not any(sign_near(h) for h in unused):
                    changed = candidates[0];alter = _default_alter(changed, fifths)
                    for n, start, duration, index in half:
                        _set_pitch(n, changed, alter)
                        local['headPitchCorrections'].append({'measure':number, 'from':name, 'to':changed, 'alter':alter, 'staff':staff,
                                                               'reason':'repeated-hollow-heads-on-clef-grid'})
                    name = changed;y = _pitch_y(name, clefs[staff], lines)
            hollow = sorted(h for h in holes if abs(h[1]-y) < .35*staff_unit)
            solid = sorted(h for h in filled if abs(h[1]-y) < .35*staff_unit)
            hollow_events = [e for e in occurrence_order if e[0].findtext('type') in ('half', 'whole')]
            solid_events = [e for e in occurrence_order if e[0].findtext('type') in ('quarter', 'eighth', '16th', '32nd', '64th')]
            mapping = {}
            if len(hollow) == len(hollow_events):mapping.update((id(e[0]), h) for e, h in zip(hollow_events, hollow))
            if len(solid) == len(solid_events):mapping.update((id(e[0]), h) for e, h in zip(solid_events, solid))
            # Repeated pitches with a complete head bijection and no printed
            # local accidental may disagree with the recognized key. A natural
            # glyph (including a faint one) vetoes this entire pitch group.
            if fifths is not None and not linked and (staff,name[0]) not in uncertain_alters and len(occurrences) >= 2 and len(mapping) == len(occurrences) and not any(sign_near(h) for h in mapping.values()):
                alter = _default_alter(name, fifths)
                for n, start, duration, index in occurrences:
                    before = n.findtext('pitch/alter', '0')
                    if before != str(alter):
                        _set_pitch(n, name, alter)
                        local['alterationCorrections'].append({'measure':number, 'pitch':name, 'from':before, 'to':alter, 'staff':staff,
                                                              'reason':'repeated-heads-key-no-local-sign'})
            # Recover exactly one missing tied quarter, not a guessed rest.
            if len(half) == 1 and len(solid_events) == 1 and len(occurrences) == 2 and len(hollow) == 1 and len(solid) == 2:
                first, last = half[0], solid_events[0];n1, start1, length1, _ = first;n2, start2, length2, _ = last
                if (length2 == 1 and start2 == start1+length1+1 and n1.findtext('voice') == n2.findtext('voice')
                        and n1.findtext('pitch/alter', '0') == n2.findtext('pitch/alter', '0')
                        and hollow[0][0] < solid[0][0] < solid[1][0]
                        and _plain_filled_stem(gray, (solid[0][0], solid[0][1], max(solid[0][2], solid[0][0]-.8*staff_unit),
                                                     min(solid[0][3], solid[0][0]+.8*staff_unit)), stems, staff_unit,
                                               endpoint_tolerance=.75,min_length=2.4,ink_threshold=245) is not None
                        and not any(sign_near(h) for h in (hollow[0], *solid))
                        and n1.find('notations/articulations') is None
                        and not any(n.findtext('staff', '1') == staff and n.findtext('voice') == n1.findtext('voice')
                                    and start == start1+length1 for n, start, _, _ in events)
                        and _curve_between(gray, hollow[0], solid[0], staff_unit, lines)):
                    added = deepcopy(n2)
                    added.attrib.pop('id', None)
                    for tag in ('chord', 'tie', 'notations', 'accidental'):
                        for node in list(added.findall(tag)):added.remove(node)
                    event = (added, start1+length1, Fraction(1), len(events))
                    events.append(event);occurrence_order.append(event);occurrence_order.sort(key=lambda e:(e[1], e[3]))
                    mapping.update({id(n1):hollow[0], id(added):solid[0], id(n2):solid[1]})
                    local['heldNoteRecoveries'].append({'measure':number, 'pitch':name, 'staff':staff, 'onset':str(start1+length1),
                                                       'reason':'visible-tied-quarter-head-stem'})
                    recovered = True
            for first, second in zip(occurrence_order, occurrence_order[1:]):
                n1, start1, length1, _ = first;n2, start2, _, _ = second
                h1, h2 = mapping.get(id(n1)), mapping.get(id(n2))
                if (h1 is None or h2 is None or start1+length1 != start2 or n1.findtext('voice') != n2.findtext('voice')
                        or n1.findtext('pitch/alter', '0') != n2.findtext('pitch/alter', '0')
                        or n1.find('notations/articulations') is not None or n2.find('notations/articulations') is not None):continue
                if any(h1[0] < h[0] < h2[0] for h in hollow+solid if h not in (h1, h2)):continue
                if {'start'} <= {t.get('type') for t in n1.findall('tie')} and {'stop'} <= {t.get('type') for t in n2.findall('tie')}:continue
                if sign_near(h2) or not _curve_between(gray, h1, h2, staff_unit, lines):continue
                _tie(n1, n2)
                local['tieCorrections'].append({'measure':number, 'pitch':name, 'staff':staff, 'onset':str(start1),
                                               'continuation':str(start2), 'reason':'bowed-curve-adjacent-equal-heads'})
        if sum(map(len, audits.values()))+sum(map(len, local.values())) > min(200, limit):continue
        if not any(local.values()):continue
        if recovered:
            candidate = _retime_measure(measure, events, divisions)
            if candidate is None:continue
            # Recovery is inside an already-known gap; never extend a bar.
            check = _xml_notes(candidate, divisions)
            if check is None or max(e[2]+e[3] for e in check) != max(e[2]+e[3] for e in notes):continue
            measure = candidate
        position = list(parts[0]).index(original);parts[0].remove(original);parts[0].insert(position, measure)
        for field in audits:audits[field].extend(local[field])
    return audits
