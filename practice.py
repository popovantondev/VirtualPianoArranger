"""Optional practice view; never changes the imported musical score."""
from collections import defaultdict
from statistics import median
from music_time import rational

MODES = ("off", "normal", "single", "upper", "keyboard", "balanced", "musical")


def musical_groups(groups,shift=0):
    """Conservative reduction: melody + a consonant existing chord tone.

    Never invent a neighbouring pitch. Bass preference uses the original low
    voice, previous selected accompaniment and the next chord's candidates.
    This is a disclosed highest-note melody heuristic, not harmonic analysis
    of rhythm-free text or a claim to recover the composer's intention.
    """
    black=lambda n:(n['pitch']+shift)%12 in (1,3,6,8,10)
    candidates=[];melodies=[]
    for group in groups:
        melody=max(group,key=lambda n:(n.get('original_pitch',n['pitch']),n['pitch']))
        melodies.append(melody)
        candidates.append([n for n in group if n is not melody and black(n)==black(melody)
                           and n['pitch']<=melody['pitch']-3
                           and (melody['pitch']-n['pitch'])%12 in (0,3,4,7,8,9)])
    chosen=[];previous=None
    for index,(group,melody,pool) in enumerate(zip(groups,melodies,candidates)):
        chosen.append(melody)
        if not pool:continue
        low=min(n.get('original_pitch',n['pitch']) for n in group)
        next_pool=candidates[index+1] if index+1<len(groups) else []
        def cost(n):
            root=0 if n.get('original_pitch',n['pitch'])==low else 4
            leading=0 if previous is None else abs(n['pitch']-previous)/4
            future=min((abs(n['pitch']-v['pitch'])/8 for v in next_pool),default=0)
            return root+leading+future,n['pitch']
        bass=min(pool,key=cost);chosen.append(bass);previous=bass['pitch']
    return chosen


def fit_registers(notes,shift):
    """Move a complete part/staff/voice by octaves only, never single notes.

    A voice wider than 61 keys stays unresolved instead of introducing abrupt
    per-note folds. Original score/durations/IDs are unchanged by the caller.
    """
    streams=defaultdict(list)
    for n in notes:streams[(n['part_id'],n['staff'],n['voice'])].append(n)
    offsets={}
    for key,stream in streams.items():
        pitches=[n['pitch']+shift for n in stream]
        options=[k for k in range(-120,121,12) if all(36<=p+k<=96 for p in pitches)]
        offsets[key]=min(options,key=lambda k:(abs(k),k)) if options else 0
    return [{**n,'original_pitch':n.get('original_pitch',n['pitch']),'pitch':n['pitch']+offsets[(n['part_id'],n['staff'],n['voice'])]} for n in notes]


def accompaniment_fullness(notes, fullness):
    """Monotonic thinning of a preset, preserving its melody and real pitches.

    100 keeps the preset; 0 keeps each attack's highest original note. Add
    accompaniment from the lowest original chord tone upwards, never retune.
    This is chord density, not reconstruction of a composer's melody voice.
    """
    if type(fullness) is not int or not 0 <= fullness <= 100:
        raise ValueError("Invalid chord fullness")
    if fullness == 100:
        return notes
    groups = defaultdict(list)
    for note in notes:
        groups[(note['measure'], rational(note['onset']))].append(note)
    selected = set()
    for group in groups.values():
        ranked = sorted(group, key=lambda n: (n.get('original_pitch', n['pitch']), n['pitch']))
        melody = ranked[-1]['pitch']
        extras = list(dict.fromkeys(n['pitch'] for n in ranked if n['pitch'] != melody))
        slots = (len(extras) * fullness + 50) // 100
        pitches = {melody, *extras[:slots]}
        selected.update(n['id'] for n in group if n['pitch'] in pitches)
    return [n for n in notes if n['id'] in selected]


def practice_score(score, mode, shift=0, fullness=100):
    if mode not in MODES:raise ValueError("Invalid practice mode")
    if score is None or mode in ("off","normal"):return score
    notes = score["notes"]
    if mode=='musical':
        notes=fit_registers(notes,shift)
        groups=defaultdict(list)
        for n in notes:groups[(n['measure'],rational(n['onset']))].append(n)
        return {**score,'notes':accompaniment_fullness(musical_groups([g for _,g in sorted(groups.items())],shift),fullness)}
    if mode == "upper" and notes:
        # merge_scores gives continuation pages distinct part IDs. Choose within
        # each page, not one winner for the entire multi-page document.
        pages = defaultdict(lambda: defaultdict(list))
        for note in notes:
            prefix, separator, _ = note["part_id"].partition(":")
            page = prefix if separator and prefix.startswith("page") and prefix[4:].isdigit() else "score"
            pages[page][(note["part_id"], note["staff"])].append(note["pitch"])
        # Explicit upper-part heuristic, not a claim of automatic melody extraction.
        chosen_staffs = {max(staffs, key=lambda key: (median(staffs[key]), key)) for staffs in pages.values()}
        notes = [n for n in notes if (n["part_id"], n["staff"]) in chosen_staffs]
    attacks = defaultdict(list)
    for note in notes:attacks[(note["measure"], rational(note["onset"]))].append(note)
    if mode in ("keyboard","balanced"):
        # A PC keyboard cannot hold Shift for one letter but not its neighbour.
        # Preserve the melody's modifier group at each attack, never its timing;
        # this explicit mode removes accompaniment, not silently retunes notes.
        chosen=[]
        black=lambda n:(n["pitch"]+shift)%12 in (1,3,6,8,10)
        starts={m['number']:rational(m['onset']) for m in score['measures']}
        last_bass=None
        for (measure,onset),group in sorted(attacks.items()):
            melody=max(group,key=lambda n:(n["pitch"],rational(n["duration"])))
            compatible=[n for n in group if black(n)==black(melody)]
            if mode=='keyboard':chosen.extend(compatible);continue
            chosen.append(melody)
            # Keep a real low accompaniment note on strong two-beat anchors,
            # not a second note on every fast melodic attack. No added pitches
            # or altered durations, even when a bass is incompatible with Shift.
            bass=min(compatible,key=lambda n:n['pitch'])
            beat=onset-starts[measure]
            if bass['pitch']<=melody['pitch']-12 and beat%2==0 and (last_bass is None or onset-last_bass>=2):
                chosen.append(bass);last_bass=onset
    else:
        chosen = [max(group, key=lambda n: (n["pitch"], rational(n["duration"]))) for group in attacks.values()]
    return {**score, "notes":accompaniment_fullness(chosen,fullness) if mode in ('keyboard','balanced') else chosen}
