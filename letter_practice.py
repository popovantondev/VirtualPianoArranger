"""Untimed letter notation: no fabricated musical score or playback clock."""
import re
from arrangement import simplify_notes
from practice import musical_groups, accompaniment_fullness

PATTERN=re.compile(r'\[[^\]\r\n]*\]|\([^()\s]{2,}\)|[^\s]')


def parse_letters(text,labels):
    reverse={char:pitch for pitch,char in labels.items()};tokens=[];line=1;previous=0
    for match in PATTERN.finditer(text):
        raw=match.group();grouped=raw.startswith('[') or (raw.startswith('(') and raw.endswith(')') and len(raw)>3)
        chars=raw[1:-1] if grouped else raw
        if not chars or len(chars)>128 or any(c not in reverse for c in chars):
            raise ValueError('Unknown notation character or chord; choose the source letter layout')
        line+=text.count('\n',previous,match.start());previous=match.end()
        tokens.append({'start':match.start(),'end':match.end(),'notes':[reverse[c] for c in chars],'line':line})
        if len(tokens)>100000:raise ValueError('Too many letter attacks')
    return tokens


def text_events(tokens,mode,shift,fullness):
    groups=[[{'pitch':p,'id':f'{i}:{j}'} for j,p in enumerate(token['notes'])] for i,token in enumerate(tokens)]
    if mode in ('musical','balanced'):
        chosen=musical_groups(groups,shift);ids={n['id'] for n in chosen}
        groups=[[n for n in group if n['id'] in ids] for group in groups]
    events=[]
    for i,(token,group) in enumerate(zip(tokens,groups)):
        pitches=sorted(set(n['pitch'] for n in group))
        if mode in ('single','upper'):pitches=pitches[-1:]
        elif mode=='keyboard' and pitches:
            modifier=(max(pitches)+shift)%12 in (1,3,6,8,10)
            pitches=[p for p in pitches if ((p+shift)%12 in (1,3,6,8,10))==modifier]
        elif mode=='normal':pitches=simplify_notes(pitches,100-fullness)
        # Ordinal order for existing letter/follow adapters ONLY. duration0 and
        # absence of a Score explicitly prohibit automatic playback/beat hints.
        if mode in ('keyboard','balanced','musical'):
            notes=[{'id':str(j),'pitch':p,'measure':1,'onset':[0,1]} for j,p in enumerate(pitches)]
            pitches=[n['pitch'] for n in accompaniment_fullness(notes,fullness)]
        events.append({'notes':pitches,'measure':token['line'],'time':i,'duration':0})
    return events


def render_letters(text,tokens,events,labels,shift):
    pieces=[];previous=0
    for token,event in zip(tokens,events):
        pitches=[p+shift for p in event['notes']]
        if any(p not in labels for p in pitches):raise ValueError('Letter notes outside the 61-key range')
        chars=''.join(labels[p] for p in pitches)
        pieces.extend((text[previous:token['start']],chars if len(chars)==1 else '['+chars+']'))
        previous=token['end']
    pieces.append(text[previous:])
    return ''.join(pieces)
