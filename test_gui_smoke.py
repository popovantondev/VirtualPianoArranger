"""Exercise the Qt interface without opening a desktop window or user files."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication  # noqa: E402

import main as piano  # noqa: E402


class MemorySettings:
    """Keep the smoke test independent of the user's saved UI settings."""

    def __init__(self, *_args):
        pass

    def value(self, _key, default=None):
        return default


def run_smoke_test():
    root = Path(__file__).resolve().parent
    pages = [str(root / "page-1.musicxml"), str(root / "page-2.musicxml")]
    app = QApplication([])
    with patch.object(piano, "QSettings", MemorySettings):
        window = piano.MainWindow()

    try:
        translations = {
            "Русский": ("Открыть проект", "Язык приложения"),
            "English": ("Open project", "App language"),
            "Deutsch": ("Projekt öffnen", "App-Sprache"),
        }
        for language, (project_text, language_text) in translations.items():
            window.ui_lang.setCurrentText(language)
            assert window.open_project_btn.text() == project_text, language
            assert window.ui_lang_label.text() == language_text, language

        with tempfile.TemporaryDirectory() as folder:
            fake_root = Path(folder).resolve()
            fake_project = fake_root / "VirtualPianoArranger"
            homr = fake_root / "0.3" / ".venv-omr" / "Scripts" / "homr.exe"
            homr.parent.mkdir(parents=True)
            homr.touch()
            with patch.object(piano, "__file__", str(fake_project / "main.py")):
                assert window.homr_exe() == homr
            frozen_exe = fake_project / "dist" / "VirtualPianoArranger" / "VirtualPianoArranger.exe"
            with patch.object(sys, "frozen", True, create=True), patch.object(
                sys, "executable", str(frozen_exe)
            ):
                assert window.homr_exe() == homr

        with patch.object(piano.QMessageBox, "critical", side_effect=AssertionError), patch.object(
            window, "confirm_discard", return_value=True
        ):
            for path, count in zip(pages, (158, 141)):
                window.load_musicxml(path)
                assert len(window.events) == count, path

            with patch.object(
                piano.QFileDialog, "getOpenFileNames", return_value=(pages, "")
            ):
                window.open_xml_multi()

        assert len(window.events) == 299
        assert max(event["measure"] for event in window.events) == 46
        assert window.musical_score is not None
        assert min(event["time"] for event in window.events if event["measure"] == 25) >= 99
        assert window.output.toPlainText()
        assert "46" in window.status.text()
        print("PASS: Qt window, RU/EN/DE, 2 MusicXML pages -> 299 events, 46 measures")
    finally:
        window.deleteLater()
        app.quit()


if __name__ == "__main__":
    run_smoke_test()
