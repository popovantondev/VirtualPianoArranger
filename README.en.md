<!-- ppk-readme:head:start -->
<a href="https://popovantondev.github.io/VirtualPianoArranger/index-en.html"><picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/header-en-dark.7dab4f8b.svg"><img src="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/header-en-light.049c38f3.svg" width="880" height="188" alt="Virtual Piano Arranger — Offline piano, letter notation and MIDI part import. Windows · x64, Preview 0.1.0-preview.1"></picture></a>
<!-- ppk-readme:head:end -->

# Virtual Piano Arranger

[Русский](README.ru.md) · [Deutsch](README.md) · **English**

<!-- ppk-readme:body:start -->
<p>
<a href="https://github.com/popovantondev/VirtualPianoArranger/releases/tag/v0.1.0-preview.1"><picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/btn-download-en-dark.52376e56.svg"><img src="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/btn-download-en-light.600b7179.svg" width="136" height="36" alt="Download"></picture></a>
<a href="https://popovantondev.github.io/VirtualPianoArranger/index-en.html"><picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/btn-website-en-dark.652b36ce.svg"><img src="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/btn-website-en-light.171c1f4a.svg" width="120" height="36" alt="Website"></picture></a>
<a href="https://popovantondev.github.io/VirtualPianoArranger/Guide-en.html"><picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/btn-guide-en-dark.3ac5fe2c.svg"><img src="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/btn-guide-en-light.29ab3edd.svg" width="141" height="36" alt="User guide"></picture></a>
<a href="https://popovantondev.github.io/VirtualPianoArranger/play-en.html"><picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/btn-demo-en-dark.cd2a5a34.svg"><img src="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/btn-demo-en-light.3f610306.svg" width="209" height="36" alt="Play in the browser"></picture></a>
<a href="https://github.com/popovantondev/VirtualPianoArranger/issues/new"><picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/btn-bug-en-dark.d0c593ea.svg"><img src="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/btn-bug-en-light.d7acd16e.svg" width="196" height="36" alt="Report a problem"></picture></a>
</p>

<p><a href="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/assets/surface-laptop-cutout-en.webp"><picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/preview-en-dark.04d3f0d4.webp"><img src="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/preview-en-light.24a63a71.webp" width="880" height="516" alt="Virtual Piano Arranger interface"></picture></a><br>
<sub><a href="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/assets/surface-laptop-cutout-en.webp">Full screenshot</a></sub></p>

<picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/divider-dark.4b41da9b.svg"><img src="https://raw.githubusercontent.com/popovantondev/VirtualPianoArranger/main/docs/readme/divider-light.ac096d32.svg" width="880" height="6" alt="Divider"></picture>
<!-- ppk-readme:body:end -->

An offline piano with letter notation, MIDI part selection and score adaptation for a 61-key computer keyboard.

**Windows x64 · English / Русский / Deutsch · 0.1.0-preview.1**

*Illustrative laptop mockup; not a device compatibility test.*

An educational, non-commercial demonstration project for exploring music software and its capabilities. The author is not selling this application. This describes the project's purpose, not a restriction on rights granted by MIT or third-party licenses. It does not imply affiliation with or endorsement by component authors.

## Features

| MIDI · part selection | Letter notation |
|---|---|
| Piano sound and WAV | Key preview |

[Download Windows portable](https://github.com/popovantondev/VirtualPianoArranger/releases/download/v0.1.0-preview.1/VirtualPianoArranger-0.1.0-preview.1-windows-x64-portable.zip) · [SHA-256](https://github.com/popovantondev/VirtualPianoArranger/releases/download/v0.1.0-preview.1/SHA256SUMS.txt) · [Corresponding sources](https://github.com/popovantondev/VirtualPianoArranger/releases/download/v0.1.0-preview.1/VirtualPianoArranger-0.1.0-preview.1-corresponding-sources.zip)

## First steps

Extract the entire portable folder and start `VirtualPianoArranger.exe`. Do not move the EXE away from its companion files. The portable package needs no Python installation or administrator access.

Open a MIDI file, audition parts and select the parts to import. MusicXML, VPA projects and letter TXT are also supported. PDF/image recognition requires the bundled recognition runtime and remains experimental: compare pitches and timing with the source.

Open **Key and simplification** above the letters. Preview transposition and chord fullness before applying. PC/balanced/musical presets reduce accompaniment using original notes. Single-note modes cannot reduce chords further. Original-pitch linking preserves the source sound; adapted letter registers may differ.

**Show rests** is available above the notation and in the key dialog. It displays real silence in the selected parts, not ordinary spacing or tiny MIDI articulation gaps. TXT has no timing; rests and automatic playback are not invented.

## Guides and limitations

[English guide](https://popovantondev.github.io/VirtualPianoArranger/Guide-en.html) · [Русское руководство](https://popovantondev.github.io/VirtualPianoArranger/Guide-ru.html) · [Deutsche Anleitung](https://popovantondev.github.io/VirtualPianoArranger/Guide-de.html)

MIDI parts currently sound as piano, not their original General MIDI instruments. Some files require explicit approximate-playback consent. WAV recording/export is local; other audio export formats need a separately available FFmpeg. Audio/video transcription and YouTube import are not available. Recognition accuracy, other PCs and long sessions still need review. The Windows EXE is unsigned.

## Rights and license

The application's original code is licensed under [MIT](LICENSE). Third-party code, piano samples and model files retain their own licenses; MIT does not relicense those components.

Keep the complete portable folder, license texts and notices. The release includes a companion source archive and SHA-256 file; read [distribution notices](DISTRIBUTION_NOTICES.md), [model provenance](MODEL_PROVENANCE.md) and [library replacement instructions](LIBRARY_REPLACEMENT.md). This is a Preview, not an assertion that every score or Windows PC has been tested.
