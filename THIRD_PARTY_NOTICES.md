# Third-party notices

MIT in `LICENSE` applies only to the original Virtual Piano Arranger code and artwork. It does not relicense any dependency, sample, model, library or third-party asset. This educational project is not endorsed by their authors.

## Files in the public source snapshot

Salamander Grand Piano V3 recordings: copyright Alexander Holm, licensed under [Creative Commons Attribution 3.0 Unported](https://creativecommons.org/licenses/by/3.0/). Yamaha C5 piano samples were distributed as MP3 conversions by darosh / `@audio-samples/piano-mp3-velocity{3,8,13}` 1.0.5. The 90 included files are not modified by VPA; playback applies interpolation/pitch shifting, envelopes, reverb and limiting. Full attribution, original-library and distributor links: [ATTRIBUTION](assets/offline_piano/ATTRIBUTION.md). Per-file SHA-256 and package integrity: [sample manifest](assets/offline_piano/sample_manifest.json).

## Dependencies not included in this source snapshot

- PySide6/Shiboken6 and Qt: 6.11.2. Applicable open-source terms vary by component; Qt WebEngine includes Chromium and Qt PDF includes PDFium with separate third-party notices. The downloadable runtime package must carry its own complete notices, required sources and library-replacement instructions.
- HOMR 0.7.0 and its weights: AGPL, as confirmed by [the maintainer](https://github.com/liebharc/homr/discussions/155). Neither HOMR nor model/runtime binaries are included in this Git source snapshot. The recognition distribution materials are separate; MIT does not override AGPL obligations.
- CPython and PyInstaller: retain their respective licenses, including the PyInstaller bootloader exception. Runtime binaries are not included in this source snapshot.
- FFmpeg: external optional dependency, not included. Additional export formats depend on a user's separately available installation.

This document describes the source snapshot, not a certification that an unfinished executable distribution meets every third-party requirement. Binary release materials are being prepared separately.
