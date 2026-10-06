"""Strict notation-text decoding; ambiguous legacy encodings need a choice."""
from pathlib import Path

MAX_BYTES = 2_000_000
LEGACY_ENCODINGS = ("cp1251", "cp1252", "mac_cyrillic", "mac_roman", "utf-16-le", "utf-16-be")


class EncodingChoiceNeeded(ValueError):
    pass


def read_notation(path, encoding=None):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Text exceeds the 2 MB limit")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Text exceeds the 2 MB limit")
    if encoding is not None and encoding not in LEGACY_ENCODINGS + ("utf-8-sig",):
        raise ValueError("Unsupported text encoding")
    if encoding is None:
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            encoding = "utf-16"
        else:
            encoding = "utf-8-sig"
    try:
        text = raw.decode(encoding, errors="strict")
    except UnicodeDecodeError as error:
        if encoding == "utf-8-sig":
            raise EncodingChoiceNeeded("Choose the source text encoding") from error
        raise ValueError("The file cannot be decoded with this encoding") from error
    if "\x00" in text:
        if encoding == "utf-8-sig":
            raise EncodingChoiceNeeded("UTF-16 without BOM needs an explicit choice")
        raise ValueError("Binary data is not letter notation")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in text):
        raise ValueError("Binary data is not letter notation")
    return text.replace("\r\n", "\n").replace("\r", "\n")
