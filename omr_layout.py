"""Conservative straight-staff geometry; never creates musical symbols."""
from statistics import median


def _align_outer_staffs(binary,horizontal,left,right,upper,lower):
    """Use agreeing full-system barline ends to resolve a faded outer line.

    Three observed lines determine spacing, not whether the missing line is
    above or below them. Never shift from note heads or a single brace alone.
    """
    import cv2
    import numpy as np
    unit=median([b-a for staff in (upper,lower) for a,b in zip(staff,staff[1:])])
    top=max(0,round(upper[0]-1.4*unit));bottom=min(len(binary),round(lower[-1]+1.4*unit)+1)
    area=binary[top:bottom,left:right+1]
    closed=cv2.morphologyEx(area,cv2.MORPH_CLOSE,np.ones((max(1,round(.3*unit))|1,1),np.uint8))
    vertical=cv2.morphologyEx(closed,cv2.MORPH_OPEN,np.ones((max(3,round(lower[-1]-upper[0]-unit))|1,1),np.uint8))
    contours,_=cv2.findContours(vertical,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    ends=[]
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        if w>unit or h<lower[-1]-upper[0]-unit:continue
        if abs(y+top-upper[0])>1.3*unit or abs(y+top+h-1-lower[-1])>1.3*unit:continue
        ends.append((x+left,y+top,y+top+h-1))
    if len(ends)<2 or max(x for x,_,_ in ends)-min(x for x,_,_ in ends)<(right-left)*.25:return upper,lower
    starts=[y for _,y,_ in ends];stops=[y for _,_,y in ends]
    if max(starts)-min(starts)>.4*unit or max(stops)-min(stops)>.4*unit:return upper,lower
    result=[]
    for staff,anchor,outer in ((upper,median(starts),0),(lower,median(stops),-1)):
        step=(staff[-1]-staff[0])/4;shift=round((anchor-staff[outer])/step)
        if abs(shift)>1 or abs(anchor-staff[outer]-shift*step)>.35*unit:return upper,lower
        candidate=[y+shift*step for y in staff]
        # All actually observed horizontal rows in this cluster must still fit.
        a=max(0,round(staff[0]-1.2*unit));b=min(len(horizontal),round(staff[-1]+1.2*unit)+1)
        observed=np.flatnonzero((horizontal[a:b,left:right+1]>0).sum(axis=1)>(right-left)*.4)+a
        if any(min(abs(y-line) for line in candidate)>.35*unit for y in observed):return upper,lower
        result.append(candidate)
    return tuple(result)


def group_lines(centers):
    differences=[b-a for a,b in zip(centers,centers[1:]) if 3<=b-a<=12]
    if len(differences)<8:return []
    unit=median(differences)
    groups=[]
    for y in centers:
        if not groups or y-groups[-1][-1]>unit*2.6:groups.append([])
        groups[-1].append(y)
    staffs=[]
    for group in groups:
        if len(group)<3:continue
        if len(group)>5 or group[-1]-group[0]>unit*4.7:return []
        # Faded screenshot lines can disappear. Only accept a regular lattice
        # with at least three observed, long horizontal lines.
        slots=[round((group[-1]-y)/unit) for y in group]
        if len(set(slots))!=len(slots) or max(slots)>4:return []
        fitted=median([(group[-1]-y)/slot for y,slot in zip(group,slots) if slot])
        if not .8*unit<fitted<1.2*unit:return []
        if any(abs(group[-1]-y-slot*fitted)>fitted*.3 for y,slot in zip(group,slots)):return []
        staffs.append([group[-1]-fitted*i for i in range(4,-1,-1)])
    return staffs


def piano_systems(gray,align_outer=True):
    import cv2
    import numpy as np
    height,width=gray.shape
    if width<300 or height<100 or height*width>60_000_000:return []
    if width>1200:
        # Detection uses screenshot-scale coordinates. Keep the original
        # pixels for the music model; only scale this geometry probe.
        from math import ceil
        factor=ceil(width/1200)
        probe=cv2.resize(gray,(round(width/factor),round(height/factor)),interpolation=cv2.INTER_AREA)
        scale_x,scale_y=width/probe.shape[1],height/probe.shape[0]
        return [(round(left*scale_x),round(right*scale_x),[y*scale_y for y in ys])
                for left,right,ys in piano_systems(probe,align_outer=align_outer)]
    binary=cv2.threshold(gray,235,255,cv2.THRESH_BINARY_INV)[1]
    horizontal=cv2.morphologyEx(binary,cv2.MORPH_OPEN,np.ones((1,max(30,width//15)),np.uint8))
    rows=np.flatnonzero((horizontal>0).sum(axis=1)>width*.4)
    if not len(rows):return []
    runs=np.split(rows,np.where(np.diff(rows)>1)[0]+1)
    staffs=group_lines([float(np.mean(r)) for r in runs if len(r)])
    if len(staffs)<4 or len(staffs)%2:return []
    systems=[]
    for index in range(0,len(staffs),2):
        upper,lower=staffs[index:index+2]
        unit=(upper[-1]-upper[0])/4
        gap=lower[0]-upper[-1]
        if not 2*unit<gap<12*unit:return []
        if index+2<len(staffs) and staffs[index+2][0]-lower[-1]<gap*1.15:return []
        ys=upper+lower
        xs=np.flatnonzero(horizontal[max(0,round(upper[-1]))]>0)
        if len(xs)<width*.4:return []
        left,right=int(xs[0]),int(xs[-1])
        # Require a visible brace/vertical connector near the left staff edge.
        area=binary[max(0,round(upper[0])):round(lower[-1])+1,max(0,left-4*round(unit)):left+round(unit)+1]
        connected=cv2.morphologyEx(area,cv2.MORPH_CLOSE,np.ones((max(2,round(unit)),1),np.uint8))
        if not connected.size or np.max((connected>0).sum(axis=0))<len(area)*.65:return []
        if align_outer:upper,lower=_align_outer_staffs(binary,horizontal,left,right,upper,lower)
        ys=upper+lower
        systems.append((left,right,ys))
    return systems
