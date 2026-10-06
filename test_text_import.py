import tempfile
from pathlib import Path
import unittest
from text_import import read_notation, EncodingChoiceNeeded, MAX_BYTES


class TextTests(unittest.TestCase):
    def test_bom_utf8_utf16_and_newlines(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"notation.txt"
            for encoding in ("utf-8","utf-8-sig","utf-16"):
                path.write_bytes("я (6г)\r\nо\rу".encode(encoding))
                self.assertEqual(read_notation(path),"я (6г)\nо\nу")
            path.write_bytes(b"\xfe\xff"+"я".encode("utf-16-be"))
            self.assertEqual(read_notation(path),"я")

    def test_legacy_windows_and_mac_need_explicit_choice(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"notation.txt"
            for encoding,text in (("cp1251","я (6г)"),("mac_cyrillic","я (6г)"),("cp1252","ä z"),("mac_roman","ä z"),("utf-16-le","я г")):
                path.write_bytes(text.encode(encoding))
                with self.assertRaises(EncodingChoiceNeeded):read_notation(path)
                self.assertEqual(read_notation(path,encoding),text)

    def test_size_binary_invalid_encoding(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"notation.txt"
            path.write_bytes(b"x"*(MAX_BYTES+1))
            with self.assertRaises(ValueError):read_notation(path)
            path.write_bytes(b"x\x01y")
            with self.assertRaises(ValueError):read_notation(path)
            with self.assertRaises(ValueError):read_notation(path,"fake-encoding")


if __name__=="__main__":unittest.main()
