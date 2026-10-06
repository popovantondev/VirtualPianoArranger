import unittest
from PySide6.QtGui import QImage,QColor
from pdf_raster import opaque_score_page


class PdfRasterTests(unittest.TestCase):
    def test_transparent_paper_is_white_and_visible_ink_survives(self):
        source=QImage(10,10,QImage.Format.Format_ARGB32)
        source.fill(QColor(0,0,0,0));source.setPixelColor(5,5,QColor(0,0,0,255))
        source.setPixelColor(2,2,QColor(0,0,0,128))
        result=opaque_score_page(source)
        self.assertFalse(result.hasAlphaChannel())
        self.assertEqual(result.pixelColor(0,0),QColor('white'))
        self.assertEqual(result.pixelColor(5,5),QColor('black'))
        self.assertIn(result.pixelColor(2,2).red(),(127,128))
        self.assertEqual(source.pixelColor(0,0).alpha(),0)

    def test_null_image_stays_null(self):
        self.assertTrue(opaque_score_page(QImage()).isNull())
