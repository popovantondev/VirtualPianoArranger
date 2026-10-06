"""Read an explicit opening piano meter, never infer it from bar lengths.

Both engraved staves must independently agree at one header column. This
does not fit durations, insert rests, or guess a missing/change-of-meter sign.
"""
from pathlib import Path


def _local_reader():
    import rapidocr
    folder=Path(rapidocr.__file__).parent/'models'
    names={'Det':'PP-OCRv6_det_small.onnx','Cls':'ch_ppocr_mobile_v2.0_cls_mobile.onnx',
           'Rec':'PP-OCRv6_rec_small.onnx'}
    # Optional evidence must not trigger downloads on an incomplete runtime.
    if not all((folder/name).is_file() for name in names.values()):return None
    engine=rapidocr.RapidOCR(params={**{key+'.model_path':str(folder/name) for key,name in names.items()},'Global.log_level':'warning'})
    def read(crop):
        result=engine(crop,use_det=False,use_cls=False)
        return (result.txts[0],result.scores[0]) if result.txts and len(result.txts)==1 else ('',0)
    return read


def verify_first_meter(root,gray,systems,reader=None,include_equal=False):
    import numpy as np
    if len(root.findall('part'))!=1 or not systems:return []
    measure=root.find('./part/measure')
    if measure is None or measure.findtext('attributes/staves')!='2':return []
    times=measure.findall('attributes/time')
    if len(times)!=1 or times[0].find('senza-misura') is not None:return []
    time=times[0]
    if len(time.findall('beats'))!=1 or len(time.findall('beat-type'))!=1:return []
    old=(time.findtext('beats'),time.findtext('beat-type'))
    if not all(value and value.isdigit() for value in old):return []
    left,right,lines=systems[0]
    if len(lines)!=10:return []
    unit=float(np.median(np.diff(lines[:5])))
    a,b=round(left+3*unit),min(round(left+18*unit),right)
    if a<0 or b<=a or round(lines[-1])>=gray.shape[0]:return []
    top=round(lines[0]);ink=(gray[top:round(lines[4])+1,a:b]<210).copy()
    for y in lines[:5]:
        ink[max(0,round(y-top-.16*unit)):round(y-top+.16*unit)+1]=False
    columns=np.flatnonzero(ink.sum(axis=0)>.3*unit)
    groups=[group for group in np.split(columns,np.where(np.diff(columns)>2)[0]+1)
            if len(group) and .6*unit<=group[-1]-group[0]+1<=2.5*unit]
    if not groups or len(groups)>12:return []
    if reader is None:
        try:reader=_local_reader()
        except (ImportError,FileNotFoundError):return []
    if reader is None:return []
    candidates=[]
    for group in groups:
        x1,x2=max(0,round(a+group[0]-.15*unit)),min(gray.shape[1],round(a+group[-1]+.5*unit)+1)
        pairs=[]
        for staff in (lines[:5],lines[5:]):
            pair=[]
            for y1,y2 in ((staff[0],staff[2]),(staff[2],staff[4])):
                text,confidence=reader(gray[round(y1):round(y2)+1,x1:x2])
                if confidence<.99 or not text.isdigit():break
                pair.append(text)
            if len(pair)!=2:break
            pairs.append(tuple(pair))
        if len(pairs)==2 and pairs[0]==pairs[1] and 1<=int(pairs[0][0])<=12 and int(pairs[0][1]) in (2,4,8,16):
            candidates.append(pairs[0])
    # Even two plausible columns are ambiguous; do not choose the one that fits.
    if len(candidates)!=1 or (candidates[0]==old and not include_equal):return []
    new=candidates[0];time.find('beats').text=new[0];time.find('beat-type').text=new[1]
    return [{'measure':1,'before':list(old),'after':list(new),'reason':'matching-printed-meter-on-both-staves'}]


def valid_meter_context(value):
    return (isinstance(value,dict) and set(value)=={'beats','beatType'} and
            type(value['beats']) is int and 1<=value['beats']<=12 and
            type(value['beatType']) is int and value['beatType'] in (2,4,8,16))


def apply_meter_context(root,context,witness=None):
    """Fresh worker XML only: explicit page signs take precedence over carry.

    Return carry for the next page only while no later, unverified time sign
    invalidates the image-confirmed opening meter. Never inspect bar lengths.
    """
    import xml.etree.ElementTree as ET
    if len(root.findall('part'))!=1:return None
    first=root.find('./part/measure')
    if first is None or first.findtext('attributes/staves')!='2':return None
    times=first.findall('attributes/time')
    carry=None
    if witness and len(times)==1:
        after=witness[0]['after'];carry={'beats':int(after[0]),'beatType':int(after[1])}
        times[0].find('beats').text=after[0];times[0].find('beat-type').text=after[1]
    elif not times and valid_meter_context(context):
        attributes=first.find('attributes')
        if attributes is None:attributes=ET.Element('attributes');first.insert(0,attributes)
        time=ET.SubElement(attributes,'time')
        ET.SubElement(time,'beats').text=str(context['beats'])
        ET.SubElement(time,'beat-type').text=str(context['beatType'])
        carry=dict(context)
    # Even a model-provided different sign must stop inheritance until image
    # confirmation, rather than forcing the old meter over a genuine change.
    if any(m.findall('attributes/time') for m in root.findall('./part/measure')[1:]):return None
    return carry
