"""Geometry regressions use synthetic staff coordinates, no owner material."""
import unittest
from omr_layout import group_lines, piano_systems


class LayoutTests(unittest.TestCase):
    def test_faded_lines_preserve_all_staves_with_small_spacing_variation(self):
        lines=[71,77,87.5,119,124.5,136,212.5,219.5,224.5,230,236,
               267,273,278.5,284,289.5,361,366.5,372.5,378,384]
        staffs=group_lines(lines)
        self.assertEqual(len(staffs),5)
        self.assertTrue(all(len(s)==5 for s in staffs))
        self.assertLess(staffs[0][0],71)
        self.assertEqual(staffs[0][-1],87.5)

    def test_ambiguous_clusters_do_not_create_staffs(self):
        self.assertEqual(group_lines([10,16]),[])
        self.assertEqual(group_lines([10,16,22,28,34,40,100,106,112,118,124]),[])

    def test_raster_geometry_is_scale_invariant_including_pdf_resolution(self):
        try:
            import cv2
            import numpy as np
        except ImportError:self.skipTest("Raster test requires the bundled recognition runtime")
        image=np.full((600,900),255,dtype=np.uint8)
        for top in (80,320):
            for staff_top in (top,top+70):
                for line in range(5):cv2.line(image,(40,staff_top+line*6),(840,staff_top+line*6),0,1)
            cv2.line(image,(40,top),(40,top+94),0,1)
        base=piano_systems(image);self.assertEqual(len(base),2)
        for width in (1800,2400,2700):
            factor=width/image.shape[1]
            enlarged=cv2.resize(image,(width,round(image.shape[0]*factor)),interpolation=cv2.INTER_NEAREST)
            systems=piano_systems(enlarged);self.assertEqual(len(systems),2)
            for (left,right,ys),(actual_left,actual_right,actual_ys) in zip(base,systems):
                self.assertAlmostEqual(actual_left/factor,left,delta=2)
                self.assertAlmostEqual(actual_right/factor,right,delta=2)
                for expected,actual in zip(ys,actual_ys):self.assertAlmostEqual(actual/factor,expected,delta=1)

    def test_missing_bottom_line_is_anchored_by_multiple_full_barlines(self):
        import cv2
        import numpy as np
        image=np.full((600,900),255,dtype=np.uint8)
        for top in (80,320):
            for staff_top in (top,top+70):
                for index in range(5):
                    if staff_top==top+70 and index in (2,4):continue
                    cv2.line(image,(40,staff_top+index*6),(840,staff_top+index*6),0,1)
            for x in (40,300,600,840):cv2.line(image,(x,top),(x,top+94),0,1)
        systems=piano_systems(image);self.assertEqual(len(systems),2)
        self.assertEqual(systems[0][2][5:],[150,156,162,168,174])
        self.assertEqual(systems[1][2][5:],[390,396,402,408,414])
        original=piano_systems(image,align_outer=False)
        self.assertEqual(len(original),len(systems));self.assertEqual(original[0][2][5:],[144,150,156,162,168])


if __name__=="__main__":unittest.main()
