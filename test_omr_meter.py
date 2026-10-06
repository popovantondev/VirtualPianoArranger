import unittest
import xml.etree.ElementTree as ET
import numpy as np
from omr_meter import verify_first_meter,apply_meter_context,valid_meter_context


class MeterTests(unittest.TestCase):
    def test_carry_only_without_explicit_meter_and_stop_on_changes(self):
        context={'beats':4,'beatType':4}
        root=ET.fromstring('<score-partwise><part><measure><attributes><staves>2</staves></attributes><note><duration>99</duration></note></measure></part></score-partwise>')
        note=ET.tostring(root.find('.//note'))
        self.assertEqual(apply_meter_context(root,context),context)
        self.assertEqual(root.findtext('.//time/beats'),'4');self.assertEqual(ET.tostring(root.find('.//note')),note)
        # Once an explicit sign exists, it is not overwritten by inheritance.
        root.find('.//time/beats').text='3'
        self.assertIsNone(apply_meter_context(root,context));self.assertEqual(root.findtext('.//time/beats'),'3')
        second=ET.SubElement(root.find('part'),'measure');attrs=ET.SubElement(second,'attributes');ET.SubElement(attrs,'time')
        witness=[{'after':['4','4']}]
        self.assertIsNone(apply_meter_context(root,context,witness))
        for invalid in ({'beats':True,'beatType':4},{'beats':4,'beatType':3},{'beats':4,'beatType':4,'extra':1},None):
            self.assertFalse(valid_meter_context(invalid))

    def test_equal_printed_meter_can_prove_carry_without_a_change(self):
        self.root.find('.//beats').text='4'
        proof=verify_first_meter(self.root,self.gray,self.systems,self.read([('4',.999)]*4),include_equal=True)
        self.assertEqual(proof[0]['before'],proof[0]['after'])
        self.assertEqual(apply_meter_context(self.root,None,proof),{'beats':4,'beatType':4})

    def setUp(self):
        self.root=ET.fromstring('<score-partwise><part><measure><attributes><staves>2</staves></attributes><attributes><time><beats>6</beats><beat-type>4</beat-type></time></attributes><note><rest/><duration>6</duration></note></measure></part></score-partwise>')
        self.gray=np.full((240,300),255,np.uint8)
        self.systems=[(10,290,[30,40,50,60,70,140,150,160,170,180])]
        # One geometric column; the reader's four independent observations are
        # injected, not a private score or a mock of the consensus algorithm.
        self.gray[31:69,90:104]=0

    def read(self,values):
        iterator=iter(values)
        return lambda crop:next(iterator)

    def test_matching_both_staves_changes_only_printed_meter(self):
        note=ET.tostring(self.root.find('.//note'))
        result=verify_first_meter(self.root,self.gray,self.systems,self.read([('4',.999)]*4))
        self.assertEqual(result[0]['after'],['4','4'])
        self.assertEqual(ET.tostring(self.root.find('.//note')),note)

    def test_disagreement_low_confidence_non_digit_and_multiple_columns_are_unchanged(self):
        for values in ([('4',.999),('4',.999),('3',.999),('4',.999)],
                       [('4',.98)],[('sharp',.999)]):
            before=ET.tostring(self.root)
            self.assertEqual(verify_first_meter(self.root,self.gray,self.systems,self.read(values)),[])
            self.assertEqual(ET.tostring(self.root),before)
        self.gray[31:69,130:144]=0
        self.assertEqual(verify_first_meter(self.root,self.gray,self.systems,self.read([('4',.999)]*8)),[])

    def test_no_meter_or_free_time_is_not_guessed(self):
        time=self.root.find('.//time');time.remove(time.find('beats'))
        before=ET.tostring(self.root)
        self.assertEqual(verify_first_meter(self.root,self.gray,self.systems,lambda crop:('4',1)),[])
        self.assertEqual(ET.tostring(self.root),before)


if __name__=='__main__':unittest.main()
