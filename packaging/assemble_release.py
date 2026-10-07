"""Assemble a new portable/source release, preserving prior review builds.

Notice contents are unchanged; long upstream paths are indexed and flattened
in the portable package so Windows extraction does not require long paths.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import zipfile


ROOT = Path(__file__).resolve().parent.parent
VERSION = '0.1.0-preview.1'


def native(path):
    resolved = str(path.absolute())
    return Path('\\\\?\\' + resolved) if os.name == 'nt' and not resolved.startswith('\\\\?\\') else Path(resolved)


def digest(path):
    with native(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def files(root):
    for folder, _, names in os.walk(native(root)):
        for name in names:
            yield Path(folder) / name


def copy_file(source, destination):
    native(destination.parent).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(native(source), native(destination))


def relative(path, root):
    return path.relative_to(native(root)).as_posix()


def archive(root, target):
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as out:
        for source in sorted(files(root)):
            out.write(source, root.name + '/' + relative(source, root))
    with zipfile.ZipFile(target) as check:
        broken = check.testzip()
        if broken:
            raise ValueError('ZIP CRC failure: ' + broken)
    if target.stat().st_size >= 2_000_000_000:
        raise ValueError('Release asset exceeds conservative GitHub size limit')
    return {'file': target.name, 'bytes': target.stat().st_size, 'sha256': digest(target)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'dist') or output.exists():
        raise ValueError('Use a new directory under project/dist')
    output.mkdir(parents=True)
    app = output / 'VirtualPianoArranger'
    candidate = ROOT / 'dist/release-candidate-2026-10-06-r4/VirtualPianoArranger'
    if digest(candidate / 'VirtualPianoArranger.exe') != 'a34d8f7c388e0afff60f64689ca0bf4d56fd7109b09779fd8de1ed6d1dec92b4':
        raise ValueError('Candidate EXE differs from verified r4')
    copied = []
    omitted = []
    for source in files(candidate):
        name = relative(source, candidate)
        if '__pycache__' in Path(name).parts or source.suffix == '.pyc':
            omitted.append(name)
            continue
        copy_file(source, app / name)
        if digest(source) != digest(app / name):
            raise ValueError('Copy mismatch: ' + name)
        copied.append(name)
    public = ROOT / 'packaging/public'
    for name in ['LICENSE', 'START_HERE.txt', 'DISTRIBUTION_NOTICES.md',
                 'LIBRARY_REPLACEMENT.md', 'MODEL_PROVENANCE.md', 'BUILDING.md',
                 'requirements-build.lock.txt', 'requirements-recognition.lock.txt',
                 'Guide-ru.html', 'Guide-de.html', 'Guide-en.html']:
        copy_file(public / name, app / name)
    for source in (public / 'assets').iterdir():
        if source.is_file():
            copy_file(source, app / 'assets' / source.name)
    notices = ROOT / 'dist/license-materials-2026-10-06'
    notice_index = []
    for source in files(notices):
        name = relative(source, notices)
        if source.name == 'notice-inventory.json' or name.startswith('upstream-source/'):
            continue
        sha = digest(source)
        destination = app / 'licenses' / (sha[:24] + '-' + source.name[:110])
        copy_file(source, destination)
        notice_index.append({'original_path': name, 'file': destination.relative_to(app).as_posix(), 'sha256': sha})
        if '/' not in name:
            copy_file(source, app / 'licenses' / source.name)
    (app / 'licenses/INDEX.json').write_text(json.dumps(notice_index, ensure_ascii=False, indent=2), encoding='utf-8')
    (app / 'VERSION.txt').write_text(VERSION + '\n', encoding='utf-8')
    sources = output / 'VirtualPianoArranger-corresponding-sources'
    sources.mkdir()
    source_names = ['pyside-setup-everywhere-src-6.11.2.tar.xz',
                    *[m + '-everywhere-src-6.11.2.tar.xz' for m in
                      ['qtbase', 'qtdeclarative', 'qtwebchannel', 'qtpositioning', 'qtsvg', 'qtserialport', 'qtwebengine']],
                    'Python-3.14.7.tar.xz', 'Python-3.11.9.tar.xz',
                    'homr-v0.7.0-source.tar', 'homr-training-308-source.tar', 'homr-training-396-source.tar',
                    'opencv-wrapper-414-source.tar', 'opencv-wrapper-500-source.tar',
                    'pytorch_model_396-f6feedb42ff90087d898b0941a55d040fa6b2903.zip',
                    'segnet_308-3296ccd40960f90ca6ab9c035cca945675d30a0f.zip',
                    'vpa-public-source.tar']
    source_index = []
    for source in [*[ROOT / 'dist' / name for name in source_names],
                   *sorted((ROOT / 'dist/package-sources-2026-10-06').glob('*.tar.gz'))]:
        print('Checking source', source.name, flush=True)
        if source.suffix == '.zip':
            with zipfile.ZipFile(source) as check:
                if check.testzip():
                    raise ValueError('Checkpoint ZIP CRC failure')
        else:
            with tarfile.open(source, 'r|*') as check:
                for member in check:
                    if member.name.startswith('/') or '..' in Path(member.name).parts:
                        raise ValueError('Unsafe source archive path')
                    basename = Path(member.name).name
                    lower = basename.lower()
                    if member.isfile() and (any(term in lower for term in
                        ('license', 'licence', 'notice', 'copyright', 'patents'))
                        or lower in ('readme.chromium', 'qt_attribution.json')):
                        # Google source archives have no top-level folder.
                        # Namespace provenance by archive to avoid overwriting
                        # distinct root LICENSE files while preserving bytes.
                        data = check.extractfile(member).read()
                        sha = hashlib.sha256(data).hexdigest()
                        destination = app / 'licenses' / (sha[:24] + '-' + basename[:110])
                        native(destination).write_bytes(data)
                        notice_index.append({'original_path': source.name + '/' + member.name,
                            'file': destination.relative_to(app).as_posix(), 'sha256': sha})
        copy_file(source, sources / source.name)
        source_index.append({'file': source.name, 'bytes': source.stat().st_size, 'sha256': digest(source)})
    for name in ['BUILDING.md', 'DISTRIBUTION_NOTICES.md', 'LIBRARY_REPLACEMENT.md', 'MODEL_PROVENANCE.md',
                 'requirements-build.lock.txt', 'requirements-recognition.lock.txt']:
        copy_file(public / name, sources / name)
    (sources / 'INDEX.json').write_text(json.dumps(source_index, indent=2), encoding='utf-8')
    (app / 'licenses/INDEX.json').write_text(json.dumps(notice_index, ensure_ascii=False, indent=2), encoding='utf-8')
    manifest = {'version': VERSION, 'candidate': 'review-r4', 'status': 'local-candidate',
                'copied_runtime_files': len(copied), 'omitted_python_caches': len(omitted),
                'notice_entries': len(notice_index), 'source_archives': len(source_index), 'assets': []}
    for root, suffix in [(app, 'windows-x64-portable'), (sources, 'corresponding-sources')]:
        print('Archiving', suffix, flush=True)
        manifest['assets'].append(archive(root, output / ('VirtualPianoArranger-' + VERSION + '-' + suffix + '.zip')))
    (output / 'release-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (output / 'SHA256SUMS.txt').write_text(''.join(a['sha256'] + '  ' + a['file'] + '\n' for a in manifest['assets']), encoding='ascii')
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == '__main__':
    main()
