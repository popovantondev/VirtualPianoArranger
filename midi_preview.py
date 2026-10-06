"""Non-destructive 30-second audition using original MIDI pitches/clock."""
from midi_import import select_parts
from arrangement import score_clock,playback_time_available
from music_time import rational,validate_score


def original_plan(score):
    """Full, untrimmed MIDI clock; sound range is not the letter-key range."""
    validate_score(score)
    if not all(all(key in part for key in ('midi_track','midi_port','midi_channel','midi_program')) for part in score['parts']):raise ValueError('MIDI score required')
    if not playback_time_available(score):return {'version':1,'error':'uncertain','notes':[],'duration':0}
    clock=score_clock(score)
    return {'version':1,'approximate':not score['exact'],'duration':clock(rational(score['duration'])),
            'outside':sum(not 21<=n['pitch']<=108 for n in score['notes']),
            'notes':sorted([{'id':n['id'],'midi':n['pitch'],'start':clock(rational(n['onset'])),
                      'end':clock(rational(n['onset'])+rational(n['duration'])),'velocity':n['velocity']}
                     for n in score['notes'] if 21<=n['pitch']<=108],key=lambda n:(n['start'],n['id']))}


def preview_plan(score,ids,approximate=False):
    selected=select_parts(score,ids,approximate)
    if not playback_time_available(selected):raise ValueError('approximate_consent_required')
    clock=score_clock(selected)
    notes=[{'id':n['id'],'midi':n['pitch'],'start':clock(rational(n['onset'])),
            'end':clock(rational(n['onset'])+rational(n['duration'])),'velocity':n['velocity']}
           for n in selected['notes'] if 21<=n['pitch']<=108]
    if not notes:raise ValueError('no_preview_notes')
    first=min(n['start'] for n in notes)
    duration=min(30.,max(n['end'] for n in notes)-first)
    return {'version':1,'approximate':not selected['exact'],'preview':True,'duration':duration,
            'outside':sum(not 21<=n['pitch']<=108 for n in selected['notes']),
            'notes':[{**n,'start':n['start']-first,'end':min(duration,n['end']-first)}
                     for n in notes if n['start']-first<duration]}
