"""Read-only notation hints; MIDI articulation gaps are not written rests."""
from fractions import Fraction
from music_time import rational


def fraction_label(value):
    value=Fraction(value)
    return str(value.numerator) if value.denominator==1 else f'{value.numerator}/{value.denominator}'


def timing_tolerance(score):
    # Presentation only: two 480-PPQN ticks must not become tiny written rests.
    parts=score.get('parts',[]) if score else []
    return Fraction(1,240) if parts and all('midi_channel' in p for p in parts) else Fraction(0)


def display_fraction(value,tolerance=0):
    value=Fraction(value);nearest=value.limit_denominator(24)
    return nearest if abs(nearest-value)<=tolerance else value


def beat_label(value,tolerance=0):
    value=display_fraction(value,tolerance);whole=value.numerator//value.denominator
    remainder=value-whole
    suffix={Fraction(1,2):'½',Fraction(1,4):'¼',Fraction(3,4):'¾',Fraction(1,3):'⅓',Fraction(2,3):'⅔'}.get(remainder)
    return str(whole)+suffix if suffix else fraction_label(value)


def rest_symbols(duration,whole_measure=False):
    duration=Fraction(duration)
    if whole_measure:return [{'kind':'whole','dots':0}]
    bases=[(Fraction(4,2**i),kind) for i,kind in enumerate(('whole','half','quarter','eighth','sixteenth','thirtysecond','sixtyfourth'))]
    for value,kind in bases:
        for dots,factor in ((0,Fraction(1)),(1,Fraction(3,2)),(2,Fraction(7,4))):
            if duration==value*factor:return [{'kind':kind,'dots':dots}]
        if duration==value*Fraction(2,3):return [{'kind':kind,'dots':0,'tuplet':3}]
    # Exact binary durations may need several symbols; no arbitrary quantization.
    remaining=duration;result=[]
    for value,kind in bases:
        while remaining>=value and len(result)<32:
            result.append({'kind':kind,'dots':0});remaining-=value
    return result if remaining==0 else [{'kind':'quarter','dots':0,'approximate':True}]


def rhythm_hints(score,clock=None):
    if score is None or not score['exact']:return []
    tolerance=timing_tolerance(score)
    intervals=sorted((rational(n['onset']),rational(n['onset'])+rational(n['duration'])) for n in score['notes'])
    merged=[]
    for start,end in intervals:
        if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
        else:merged.append((start,end))
    gaps=[];cursor=Fraction(0)
    for start,end in merged:
        if start>cursor:gaps.append((cursor,start))
        cursor=max(cursor,end)
    end=rational(score['duration'])
    if cursor<end:gaps.append((cursor,end))
    result=[];gap_index=0
    for measure in score['measures']:
        start=rational(measure['onset']);end=start+rational(measure['duration']);rests=[]
        while gap_index<len(gaps) and gaps[gap_index][1]<=start:gap_index+=1
        i=gap_index
        while i<len(gaps) and gaps[i][0]<end:
            a,b=max(start,gaps[i][0]),min(end,gaps[i][1])
            if b-a>tolerance:
                duration=display_fraction(b-a,tolerance)
                rest={'onset':float(a),'beat':beat_label(a-start+1,tolerance),'duration':fraction_label(duration),
                      'symbols':rest_symbols(duration,a==start and b==end)}
                if clock is not None:rest.update(start=clock(a),end=clock(b))
                rests.append(rest)
            i+=1
        result.append({'measure':measure['number'],'beats':fraction_label(end-start),'rests':rests})
    return result
