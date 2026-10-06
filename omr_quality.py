"""Check OMR timing without guessing notes, rests, meter or slur meaning."""
from collections import Counter
from fractions import Fraction
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET


def promote_notated_ties(root):
    """HOMR can emit engraving-only tied marks; make those audible too.

    Slurs are deliberately excluded: a phrase slur is not a held note.
    """
    added=0
    for note in root.findall("./part/measure/note"):
        if note.find("pitch") is None or note.find("grace") is not None:continue
        existing={tie.get("type") for tie in note.findall("tie")}
        kinds={tie.get("type") for tie in note.findall("./notations/tied")} & {"start","stop"}
        for kind in ("stop","start"):
            if kind not in kinds or kind in existing:continue
            duration=note.find("duration")
            if duration is None:continue
            index=list(note).index(duration)+1+len(note.findall("tie"))
            note.insert(index,ET.Element("tie",type=kind));added+=1
    return added


def rhythm_report(root):
    suspects=[];measure_count=0;histogram=Counter();checked=unreferenced=0
    for part_index,part in enumerate(root.findall("part"),1):
        divisions=Fraction(1);meter=None;free_time=False;records=[]
        for index,measure in enumerate(part.findall("measure"),1):
            cursor=extent=last=Fraction(0)
            for child in measure:
                if child.tag=="attributes":
                    if child.find("divisions") is not None:divisions=Fraction(child.findtext("divisions"))
                    time=child.find("time")
                    if time is not None:
                        meter=None;free_time=time.find("senza-misura") is not None
                        beats,units=time.findall("beats"),time.findall("beat-type")
                        if not free_time and beats and len(beats)==len(units):
                            meter=sum((sum(Fraction(b) for b in beat.text.split("+"))*4/Fraction(unit.text)
                                       for beat,unit in zip(beats,units)),Fraction(0))
                elif child.tag in ("backup","forward"):
                    delta=Fraction(child.findtext("duration"))/divisions
                    cursor+=delta if child.tag=="forward" else -delta
                    extent=max(extent,cursor)
                elif child.tag=="note" and child.find("grace") is None:
                    duration=Fraction(child.findtext("duration","0"))/divisions
                    chord=child.find("chord") is not None
                    onset=last if chord else cursor
                    if not chord:last=cursor;cursor+=duration
                    extent=max(extent,onset+duration,cursor)
            records.append((index,extent,meter,measure.get("implicit")=="yes",free_time))
        measure_count=max(measure_count,len(records))
        # A common duration is only a warning reference, never a guessed meter.
        unknown=[length for _,length,meter,pickup,free in records if meter is None and not pickup and not free and length>0]
        common=None
        if unknown:
            length,count=Counter(unknown).most_common(1)[0]
            if count>=4 and count/len(unknown)>=.75:common=length
        for index,length,meter,pickup,free in records:
            histogram[length]+=1
            expected=meter if meter is not None else common
            if pickup or free:continue
            if expected is None:unreferenced+=1;continue
            checked+=1
            if length==expected:continue
            suspects.append({"part":part_index,"measure":index,
                             "actual":[length.numerator,length.denominator],
                             "expected":[expected.numerator,expected.denominator],
                             "basis":"meter" if meter is not None else "common-duration"})
    return {"version":1,"measureCount":measure_count,"suspectCount":len(suspects),
            "suspectMeasures":suspects[:200],"checkedMeasures":checked,"unreferencedMeasures":unreferenced,
            "durationHistogram":[{"duration":[length.numerator,length.denominator],"count":count}
                                 for length,count in histogram.most_common(32)]}


def prepare_result(path):
    """Only called on a fresh worker-owned XML, never on an owner's source."""
    path=Path(path)
    with path.open("rb") as stream:raw=stream.read(16*1024*1024+1)
    if len(raw)>16*1024*1024 or b"<!ENTITY" in raw.upper():raise ValueError("Unsafe OMR XML")
    root=ET.fromstring(raw)
    if root.tag!="score-partwise":raise ValueError("Unsupported OMR XML")
    added=promote_notated_ties(root)
    report=rhythm_report(root);report["promotedTies"]=added
    if added:ET.ElementTree(root).write(path,encoding="utf-8",xml_declaration=True)
    return report


def result_warnings(path,page,language):
    """Read bounded diagnostics before the worker cleans up its temporary XML."""
    lang={"Русский":"ru","English":"en","Deutsch":"de"}.get(language,"en")
    missing={"ru":"Проверка ритма распознавания недоступна.","en":"Recognition rhythm diagnostics are unavailable.",
             "de":"Rhythmusprüfung der Erkennung ist nicht verfügbar."}
    target=Path(path).with_suffix(".recognition.json")
    if not target.is_file():return []
    try:
        if target.stat().st_size>65536:raise ValueError("Report too large")
        report=json.loads(target.read_text(encoding="utf-8")).get("quality")
        if report is None:return []
        if not isinstance(report,dict) or report.get("version")!=1:raise ValueError("Invalid report")
        issues=report["suspectMeasures"];count=report["suspectCount"]
        if type(count) is not int or not 0<=count<=100000 or not isinstance(issues,list) or len(issues)>200:raise ValueError("Invalid issues")
        if any(not isinstance(issue,dict) or type(issue.get("measure")) is not int or not 1<=issue["measure"]<=100000 for issue in issues):raise ValueError("Invalid measure")
        corrections=report.get("durationCorrections",[])
        if not isinstance(corrections,list) or len(corrections)>200 or any(not isinstance(item,dict)
                or type(item.get("measure")) is not int or not 1<=item["measure"]<=100000 for item in corrections):raise ValueError("Invalid corrections")
        notices=[]
        if corrections:
            changed=", ".join(str(n) for n in sorted({item["measure"] for item in corrections})[:12])
            kinds=Counter((item.get("from"),item.get("to")) for item in corrections)
            labels={"ru":{("note_1","note_2"):"целая → половинная",("note_2","note_4"):"половинная → четверть",("note_8","note_4"):"восьмая → четверть"},
                    "en":{("note_1","note_2"):"whole → half",("note_2","note_4"):"half → quarter",("note_8","note_4"):"eighth → quarter"},
                    "de":{("note_1","note_2"):"ganze → halbe",("note_2","note_4"):"halbe → Viertelnote",("note_8","note_4"):"Achtel- → Viertelnote"}}
            for code,label in [('ru','шестнадцатая → четверть'),('en','sixteenth → quarter'),('de','Sechzehntel- → Viertelnote')]:
                labels[code][('note_16','note_4')]=label
            if any(kind not in labels[lang] for kind in kinds):raise ValueError("Unsupported correction")
            detail="; ".join(f"{labels[lang][kind]}: {amount}" for kind,amount in kinds.items())
            messages={"ru":f"Распознавание, страница {page}: длительности сверены с головками и штилями нот в тактах {changed} ({detail}).",
                      "en":f"Recognition, page {page}: note-head/stem evidence corrected durations in bars {changed} ({detail}).",
                      "de":f"Erkennung, Seite {page}: Notenköpfe und Notenhälse bestätigen Dauerkorrekturen in Takten {changed} ({detail})."}
            notices.append(messages[lang])
        for field in ("pitchCorrections","recoveredNotes"):
            entries=report.get(field,[])
            if not isinstance(entries,list) or len(entries)>200 or any(not isinstance(item,dict)
                    or type(item.get("measure")) is not int or not 1<=item["measure"]<=100000 for item in entries):raise ValueError("Invalid image evidence")
            if not entries:continue
            bars=", ".join(str(n) for n in sorted({item["measure"] for item in entries})[:12])
            if field=="pitchCorrections":
                messages={"ru":f"Распознавание, страница {page}: высоты {len(entries)} повторяющихся нот сверены по головкам, ключу и знакам тональности (такты {bars}).",
                          "en":f"Recognition, page {page}: {len(entries)} repeated pitches corrected from head positions, clef and key signature (bars {bars}).",
                          "de":f"Erkennung, Seite {page}: {len(entries)} wiederholte Tonhöhen anhand von Notenköpfen, Schlüssel und Vorzeichen korrigiert (Takte {bars})."}
            else:
                messages={"ru":f"Распознавание, страница {page}: восстановлено {len(entries)} пропущенных повторных восьмых баса по видимым головкам и флажкам (такты {bars}); проверьте с оригиналом.",
                          "en":f"Recognition, page {page}: {len(entries)} missing repeated bass eighths recovered from visible heads and flags (bars {bars}); compare with the source.",
                          "de":f"Erkennung, Seite {page}: {len(entries)} fehlende wiederholte Bass-Achtel anhand sichtbarer Köpfe und Fähnchen ergänzt (Takte {bars}); mit der Vorlage vergleichen."}
            notices.append(messages[lang])
        for field in ("headPitchCorrections","alterationCorrections","tieCorrections","heldNoteRecoveries","omittedAttackRecoveries","chordCompositionCorrections"):
            entries=report.get(field,[])
            if not isinstance(entries,list) or len(entries)>200 or any(not isinstance(item,dict)
                    or type(item.get("measure")) is not int or not 1<=item["measure"]<=100000 for item in entries):raise ValueError("Invalid notation evidence")
            if not entries:continue
            if field=="chordCompositionCorrections" and any(
                    type(item.get("notesBefore")) is not int or not 2<=item["notesBefore"]<=4
                    or type(item.get("notesAfter")) is not int or not 2<=item["notesAfter"]<=4
                    or any(not isinstance(item.get(key),list) or not 1<=len(item[key])<=2
                           or any(not isinstance(p,str) or not re.fullmatch(r"[A-G][1-7]",p) for p in item[key])
                           for key in ("removedPitches","addedPitches")) for item in entries):raise ValueError("Invalid chord composition evidence")
            bars=", ".join(str(n) for n in sorted({item["measure"] for item in entries})[:12])
            labels={"ru":{"headPitchCorrections":"высоты по положению нотных головок", "alterationCorrections":"знаки альтерации", "tieCorrections":"связки удержания", "heldNoteRecoveries":"пропущенные продолжения удержанных нот", "omittedAttackRecoveries":"пропущенные атаки нот с точкой длительности", "chordCompositionCorrections":"составы целых аккордов"},
                    "en":{"headPitchCorrections":"note-head pitch positions", "alterationCorrections":"accidentals", "tieCorrections":"held-note ties", "heldNoteRecoveries":"missing held-note continuations", "omittedAttackRecoveries":"missing dotted-note attacks", "chordCompositionCorrections":"whole-note chord membership"},
                    "de":{"headPitchCorrections":"Tonhöhen von Notenköpfen", "alterationCorrections":"Versetzungszeichen", "tieCorrections":"Haltebögen", "heldNoteRecoveries":"fehlende Fortsetzungen gehaltener Noten", "omittedAttackRecoveries":"fehlende punktierte Notenanschläge", "chordCompositionCorrections":"Zusammensetzungen von Akkorden aus ganzen Noten"}}
            text=labels[lang][field]
            messages={"ru":f"Распознавание, страница {page}: по изображению исправлены {text}: {len(entries)} (такты {bars}); сверьте с оригиналом.",
                      "en":f"Recognition, page {page}: image evidence corrected {text}: {len(entries)} (bars {bars}); compare with the source.",
                      "de":f"Erkennung, Seite {page}: Bildabgleich korrigiert {text}: {len(entries)} (Takte {bars}); mit der Vorlage vergleichen."}
            notices.append(messages[lang])
        unresolved=report.get("unresolvedAlterations",[])
        if not isinstance(unresolved,list) or len(unresolved)>200 or any(not isinstance(item,dict)
                or type(item.get("measure")) is not int or not 1<=item["measure"]<=100000 for item in unresolved):raise ValueError("Invalid unresolved notation evidence")
        if unresolved:
            bars=", ".join(str(n) for n in sorted({item["measure"] for item in unresolved})[:12])
            messages={"ru":f"Распознавание, страница {page}: проверьте диезы/бемоли в тактах {bars}. Предыдущий знак или штиль не читается надёжно; альтерация не заменена догадкой.",
                      "en":f"Recognition, page {page}: check accidentals in bars {bars}. An earlier sign or stem is unclear; the alteration was not replaced by a guess.",
                      "de":f"Erkennung, Seite {page}: Vorzeichen in Takten {bars} prüfen. Ein früheres Zeichen oder ein Hals ist unklar; die Alteration wurde nicht durch eine Vermutung ersetzt."}
            notices.append(messages[lang])
        unmatched=report.get("unmatchedSolidHeads",[])
        if not isinstance(unmatched,list) or len(unmatched)>200 or any(not isinstance(item,dict)
                or type(item.get("measure")) is not int or not 1<=item["measure"]<=100000
                or type(item.get("count")) is not int or not 1<=item["count"]<=20 for item in unmatched):raise ValueError("Invalid unmatched head evidence")
        if unmatched:
            bars=", ".join(str(n) for n in sorted({item["measure"] for item in unmatched})[:12])
            messages={"ru":f"Распознавание, страница {page}: в тактах {bars} есть видимые головки без сопоставленной музыкальной атаки. Возможна пропущенная нота; начало и длительность не добавлены догадкой. Сверьте с оригиналом.",
                      "en":f"Recognition, page {page}: visible heads in bars {bars} lack a matched musical attack. A note may be missing; onset and duration were not guessed. Compare with the source.",
                      "de":f"Erkennung, Seite {page}: sichtbare Köpfe in Takten {bars} haben keinen zugeordneten musikalischen Anschlag. Eine Note kann fehlen; Beginn und Dauer wurden nicht geraten. Mit der Vorlage vergleichen."}
            notices.append(messages[lang])
        hollow=report.get("unresolvedHollowChords",[])
        if not isinstance(hollow,list) or len(hollow)>200 or any(not isinstance(item,dict)
                or type(item.get("measure")) is not int or not 1<=item["measure"]<=100000
                or type(item.get("recognizedCount")) is not int or not 2<=item["recognizedCount"]<=4
                or type(item.get("detectedCount")) is not int or not 1<=item["detectedCount"]<=20 for item in hollow):raise ValueError("Invalid hollow chord evidence")
        if hollow:
            bars=", ".join(str(n) for n in sorted({item["measure"] for item in hollow})[:12])
            messages={"ru":f"Распознавание, страница {page}: состав целых аккордов в тактах {bars} не совпадает с видимыми головками. Верная длина такта не подтверждает высоты; неоднозначный состав не заменён догадкой. Сверьте с оригиналом.",
                      "en":f"Recognition, page {page}: whole-note chords in bars {bars} disagree with visible heads. Correct bar duration does not confirm pitches; ambiguous chord composition was not guessed. Compare with the source.",
                      "de":f"Erkennung, Seite {page}: Akkorde aus ganzen Noten in Takten {bars} stimmen nicht mit sichtbaren Köpfen überein. Korrekte Taktdauer bestätigt keine Tonhöhen; unklare Akkorde wurden nicht geraten. Mit der Vorlage vergleichen."}
            notices.append(messages[lang])
        alternatives=report.get("geometryAlternatives",[])
        if not isinstance(alternatives,list) or len(alternatives)>2 or any(not isinstance(item,dict)
                or type(item.get("system")) is not int or not 1<=item["system"]<=100000
                or type(item.get("accepted")) is not bool for item in alternatives):raise ValueError("Invalid geometry audit")
        accepted=[item["system"] for item in alternatives if item["accepted"]]
        if accepted:
            systems=", ".join(map(str,accepted))
            messages={"ru":f"Распознавание, страница {page}: фрагменты {systems} повторно проверены по границам бледных линеек без уменьшения числа нот; сверка с оригиналом всё ещё нужна.",
                      "en":f"Recognition, page {page}: systems {systems} rechecked using faded staff boundaries without reducing note count; source comparison is still required.",
                      "de":f"Erkennung, Seite {page}: Systeme {systems} anhand blasser Liniengrenzen erneut geprüft, ohne die Notenzahl zu verringern; Vorlagenvergleich bleibt nötig."}
            notices.append(messages[lang])
        timing=report.get("timingCorrections",[])
        if not isinstance(timing,list) or len(timing)>200 or any(not isinstance(item,dict)
                or type(item.get("measure")) is not int or not 1<=item["measure"]<=100000
                or type(item.get("movedNotes")) is not int or not 1<=item["movedNotes"]<=100000 for item in timing):raise ValueError("Invalid timing correction")
        if timing:
            changed=", ".join(str(n) for n in sorted({item["measure"] for item in timing})[:12])
            messages={"ru":f"Распознавание, страница {page}: синхронизация голосов и станов пересчитана раздельно в тактах {changed}; высоты и длительности нот сохранены.",
                      "en":f"Recognition, page {page}: independent voice/staff clocks restored synchronization in bars {changed}; pitches and note durations are unchanged.",
                      "de":f"Erkennung, Seite {page}: unabhängige Stimmen/Systemzeiten korrigieren die Synchronisation in Takten {changed}; Tonhöhen und Notendauern bleiben erhalten."}
            notices.append(messages[lang])
        unreferenced=report.get("unreferencedMeasures",0)
        if type(unreferenced) is not int or not 0<=unreferenced<=100000:raise ValueError("Invalid rhythm coverage")
        if unreferenced:
            messages={"ru":f"Распознавание, страница {page}: для {unreferenced} тактов нет надёжного размера/обычной длины. Ноль замечаний не подтверждает правильный ритм — нужна сверка с оригиналом.",
                      "en":f"Recognition, page {page}: {unreferenced} bars lack a reliable meter/common duration. Zero findings do not confirm correct rhythm; compare with the source.",
                      "de":f"Erkennung, Seite {page}: für {unreferenced} Takte fehlt eine zuverlässige Taktart/übliche Dauer. Null Hinweise bestätigen keinen korrekten Rhythmus; mit der Vorlage vergleichen."}
            notices.append(messages[lang])
        if not count:return notices
        bars=", ".join(str(n) for n in sorted({issue["measure"] for issue in issues})[:12])
        if count>12:bars+=", …"
        messages={"ru":f"Распознавание, страница {page}: проверьте ритм тактов {bars} ({count} замечаний). Длина отличается от размера или большинства тактов. Подозрительные такты не подгонялись под размер.",
                  "en":f"Recognition, page {page}: check rhythm in bars {bars} ({count} findings). Duration differs from the meter or most bars. Suspect bars were not forced to fit a meter.",
                  "de":f"Erkennung, Seite {page}: Rhythmus in Takten {bars} prüfen ({count} Hinweise). Dauer weicht von der Taktart oder den meisten Takten ab. Verdächtige Takte wurden nicht an eine Taktart angepasst."}
        return notices+[messages[lang]]
    except (OSError,ValueError,TypeError,KeyError,AttributeError):return [missing[lang]]
