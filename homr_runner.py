"""Child-runtime entry: recover piano systems and verify musical evidence.

No installed HOMR files are patched. Low-confidence/skewed/non-piano layouts
retain its original detector. Image-evidenced rhythm correction is separate
from geometry recovery. Repeated-pitch/head repairs are narrowly image gated;
no result is padded/trimmed to fit a guessed meter.
"""
import json
from pathlib import Path
import sys

from omr_layout import piano_systems
from omr_quality import prepare_result, rhythm_report
from omr_duration import verify_hollow_durations, verify_filled_durations, verify_polyphonic_staves,verify_triplet_durations
from omr_timing import retime_independent_staves
from omr_heads import verify_repeated_pitch, recover_repeated_bass_eighth
from omr_notation import verify_notation
from omr_meter import verify_first_meter,apply_meter_context,valid_meter_context


def verify_page(gray,systems,symbols,xml_path,meter_context=None):
    """One bounded evidence pass, with fresh XML before/after each repair."""
    import xml.etree.ElementTree as ET
    from homr.music_xml_generator import generate_xml,XmlGeneratorArguments
    generate_xml(XmlGeneratorArguments(False,None,None),[symbols],"").write(str(xml_path))
    tree=ET.parse(xml_path)
    meter=verify_first_meter(tree.getroot(),gray,systems,include_equal=True)
    carry=apply_meter_context(tree.getroot(),meter_context,meter)
    tree.write(xml_path,encoding='utf-8',xml_declaration=True)
    before=rhythm_report(tree.getroot())
    def read_with_meter():
        result=ET.parse(xml_path);apply_meter_context(result.getroot(),meter_context,meter);return result
    verified,corrections=verify_hollow_durations(gray,systems,symbols,before["suspectMeasures"])
    verified,filled=verify_filled_durations(gray,systems,verified,before["suspectMeasures"],limit=200-len(corrections))
    corrections+=filled;verified=verify_polyphonic_staves(gray,systems,verified)
    if corrections:generate_xml(XmlGeneratorArguments(False,None,None),[verified],"").write(str(xml_path))
    tree=read_with_meter();timing=retime_independent_staves(tree.getroot(),verified)
    findings=rhythm_report(tree.getroot())["suspectMeasures"]
    verified,pitches=verify_repeated_pitch(gray,systems,verified,findings)
    verified,hollow=verify_hollow_durations(gray,systems,verified,findings,limit=200-len(corrections))
    verified,filled=verify_filled_durations(gray,systems,verified,findings,limit=200-len(corrections)-len(hollow))
    verified,heads=recover_repeated_bass_eighth(gray,systems,verified,findings)
    corrections+=hollow+filled
    if pitches or hollow or filled or heads:
        verified=verify_polyphonic_staves(gray,systems,verified)
        generate_xml(XmlGeneratorArguments(False,None,None),[verified],"").write(str(xml_path))
        tree=read_with_meter();timing=retime_independent_staves(tree.getroot(),verified)
    verified,tuplets=verify_triplet_durations(gray,systems,verified)
    if tuplets:
        generate_xml(XmlGeneratorArguments(False,None,None),[verified],"").write(str(xml_path))
        tree=read_with_meter();timing=retime_independent_staves(tree.getroot(),verified)
    notation=verify_notation(tree.getroot(),gray,systems)
    tree.write(xml_path,encoding="utf-8",xml_declaration=True)
    quality=prepare_result(xml_path)
    quality.update(durationCorrections=corrections,tupletCorrections=tuplets,timingCorrections=timing,pitchCorrections=pitches,
                   recoveredNotes=heads,suspectCountBefore=before["suspectCount"],
                   durationHistogramBefore=before["durationHistogram"],unreferencedMeasuresBefore=before["unreferencedMeasures"])
    quality.update(notation)
    quality['meterCorrections']=meter
    quality['meterContext']=carry
    return quality,len(tree.getroot().findall("./part/measure/note/pitch"))


def accept_geometry_alternative(before,after):
    """Never select a prettier histogram by dropping notes/check coverage."""
    old,old_notes=before;new,new_notes=after
    return (new_notes>=old_notes and new["measureCount"]==old["measureCount"]
            and new["checkedMeasures"]>=old["checkedMeasures"] and new["suspectCount"]<old["suspectCount"]
            and bool(new["durationCorrections"] or new["pitchCorrections"] or new["recoveredNotes"]))


def replace_suspect_bars(symbols,system_bars,alternate,local_indices):
    """A retried crop must not replace its already-correct neighbouring bars."""
    from omr_duration import _symbol_bars
    alternative_bars=_symbol_bars(alternate)
    if len(alternative_bars)!=1 or len(alternative_bars[0])!=len(system_bars):return None
    replacements=[]
    for index in local_indices:
        old,new=system_bars[index],alternative_bars[0][index]
        metadata=lambda seq,bar:[(seq[i].rhythm,seq[i].pitch,seq[i].lift,seq[i].position) for i in bar
                                 if not seq[i].rhythm.startswith(("note_","rest_")) and seq[i].rhythm!="chord"]
        if metadata(symbols,old)!=metadata(alternate,new):return None
        replacements.append((min(old),max(old)+1,[alternate[i] for i in new]))
    candidate=list(symbols)
    for start,end,bar in sorted(replacements,reverse=True):candidate[start:end]=bar
    return candidate


def main():
    import os
    import cv2
    from homr.debug import Debug
    from homr.model import Staff,StaffPoint,MultiStaff
    from homr.staff_parsing import parse_staffs
    from homr.transformer.configs import Config
    image_path=Path(sys.argv[1])
    gray=cv2.imread(str(image_path),cv2.IMREAD_GRAYSCALE)
    if gray is None:raise ValueError("Image could not be decoded")
    systems=piano_systems(gray,align_outer=False)
    physical_systems=piano_systems(gray)
    try:meter_context=json.loads(os.environ.get('VPA_OMR_METER_CONTEXT','null'))
    except (ValueError,TypeError):meter_context=None
    if not valid_meter_context(meter_context):meter_context=None
    if not systems:
        from homr.main import main as original
        original()
        import xml.etree.ElementTree as ET
        xml_path=image_path.with_suffix(".musicxml")
        tree=ET.parse(xml_path)
        # The fallback still belongs to this sequential document. Carry only
        # into a two-staff page with no explicit time sign, never fit its notes.
        carry=apply_meter_context(tree.getroot(),meter_context)
        tree.write(xml_path,encoding='utf-8',xml_declaration=True)
        quality=prepare_result(xml_path)
        quality['meterContext']=carry
        image_path.with_suffix(".recognition.json").write_text(json.dumps({"strategy":"original-detector","quality":quality}),encoding="utf-8")
        return
    print(f"VPA piano layout: {len(systems)} systems, {2*len(systems)} staves",flush=True)
    def staff_for(system):
        left,right,ys=system
        staff=Staff([StaffPoint(x,ys,0) for x in range(left,right+1,max(1,(right-left)//200))])
        staff.is_grandstaff=True
        return MultiStaff([staff],[])
    staffs=[staff_for(system) for system in systems]
    config=Config();config.use_gpu_inference=False;config.use_coreml_encoder=False
    debug=Debug(gray,str(image_path),False)
    result=parse_staffs(debug,staffs,gray,config)
    if len(result)!=1 or sum(symbol.rhythm=="newline" for symbol in result[0])!=len(systems):
        raise RuntimeError("A piano system was not recognised. Previous document is unchanged.")
    print("Writing XML",flush=True)
    xml_path=image_path.with_suffix(".musicxml")
    symbols=result[0];checked=verify_page(gray,physical_systems,symbols,xml_path,meter_context);retries=[]
    # Changing the crop globally regressed otherwise correct systems. Retry
    # only a concrete suspect system with agreeing barline-end evidence.
    from omr_duration import _symbol_bars
    bars=_symbol_bars(symbols)
    offset=0
    for index,system_bars in enumerate(bars):
        start_measure=offset
        local={item["measure"]-offset-1 for item in checked[0]["suspectMeasures"] if offset<item["measure"]<=offset+len(system_bars)}
        offset+=len(system_bars)
        if not local or len(retries)>=2 or systems[index]==physical_systems[index]:continue
        print(f"Verifying faded staff boundary in system {index+1}",flush=True)
        alternate=parse_staffs(debug,[staff_for(physical_systems[index])],gray,config)
        alternate_bars=_symbol_bars(alternate[0]) if len(alternate)==1 else []
        if len(alternate)!=1 or len(alternate_bars)!=1 or len(alternate_bars[0])!=len(system_bars):
            retries.append({"system":index+1,"accepted":False});continue
        current_bars=_symbol_bars(symbols)[index]
        candidate=replace_suspect_bars(symbols,current_bars,alternate[0],local)
        if candidate is None:
            retries.append({"system":index+1,"accepted":False});continue
        candidate_path=image_path.with_suffix(".alternative.musicxml")
        candidate_check=verify_page(gray,physical_systems,candidate,candidate_path,meter_context)
        accepted=accept_geometry_alternative(checked,candidate_check)
        retries.append({"system":index+1,"measures":[start_measure+i+1 for i in sorted(local)],
                        "accepted":accepted,"notesBefore":checked[1],"notesAfter":candidate_check[1]})
        if accepted:
            symbols=candidate;checked=candidate_check;xml_path.write_bytes(candidate_path.read_bytes())
        candidate_path.unlink()
    quality=checked[0];quality["geometryAlternatives"]=retries
    print(f"Image-verified durations: {len(quality['durationCorrections'])}; independent timing: {len(quality['timingCorrections'])} bars",flush=True)
    image_path.with_suffix(".recognition.json").write_text(json.dumps({"strategy":"piano-systems","systems":len(systems),"staves":len(systems)*2,"quality":quality}),encoding="utf-8")
    print(f"Rhythm check: {quality['suspectCount']} findings, {quality['promotedTies']} explicit tie marks preserved",flush=True)
    print("Result was written",flush=True)


if __name__=="__main__":main()
