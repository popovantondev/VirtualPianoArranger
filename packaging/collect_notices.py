"""Collect original installed notices without modifying an installed runtime.

Output is evidence/staging, not a completeness or legal certification.
"""
import argparse
import hashlib
from importlib.metadata import distributions
import json
import os
from pathlib import Path
import shutil
import tarfile


def checksum(path):
    with native(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def native(path):
    return Path('\\\\?\\' + str(path.resolve())) if os.name == 'nt' else path


def safe_relative(name):
    parts = name.replace('\\', '/').split('/')
    if any(p in ('', '.', '..') or ':' in p for p in parts):
        raise ValueError('Unsafe notice path: ' + name)
    return Path(*parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--archives', type=Path, nargs='*', default=[])
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = args.output.resolve()
    if not output.is_relative_to(root / 'dist'):
        raise ValueError('Notice staging must be under project/dist')
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for scope, folder in [('build', '.venv/Lib/site-packages'),
                          ('recognition', 'runtimes/recognition/win-x64/site-packages')]:
        for dist in sorted(distributions(path=[str(root / folder)]),
                           key=lambda d: d.metadata.get('Name', '').lower()):
            notices = []
            for relative in dist.files or []:
                if not any(term in relative.name.lower() for term in ('license', 'licence', 'notice', 'copying')):
                    continue
                source = Path(dist.locate_file(relative))
                if not source.is_file():
                    continue
                # RECORD may use ../ for script locations; don't use those
                # paths as output locations or copy executable scripts.
                if '..' in relative.parts:
                    continue
                rel = safe_relative(str(relative))
                dest = output / scope / safe_relative(dist.metadata['Name'] + '-' + dist.version) / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, dest)
                notices.append({'file': dest.relative_to(output).as_posix(), 'sha256': checksum(dest)})
            records.append({'scope': scope, 'name': dist.metadata['Name'], 'version': dist.version,
                            'license_expression': dist.metadata.get('License-Expression'),
                            'declared_license': dist.metadata.get('License'),
                            'project_urls': dist.metadata.get_all('Project-URL', []),
                            'notices': notices})
    inventory_file = output / 'notice-inventory.json'
    archives = json.loads(inventory_file.read_text(encoding='utf-8')).get('archives', []) if inventory_file.exists() else []
    for archive in args.archives:
        count = 0
        with tarfile.open(archive, 'r:*') as tar:
            for member in tar:
                if not member.isfile():
                    continue
                basename = Path(member.name).name.lower()
                if not (basename.startswith(('license', 'licence', 'copying', 'notice', 'copyright'))
                        or basename in ('readme.chromium', 'qt_attribution.json')
                        or '/LICENSES/' in member.name):
                    continue
                rel = safe_relative(member.name)
                dest = output / 'upstream-source' / rel
                native(dest.parent).mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as stream, native(dest).open('wb') as writer:
                    shutil.copyfileobj(stream, writer)
                count += 1
        archives = [record for record in archives if record['file'] != archive.name]
        archives.append({'file': archive.name, 'sha256': checksum(archive), 'notice_files': count})
    python_license = root / 'runtimes/recognition/win-x64/python/LICENSE.txt'
    shutil.copyfile(python_license, output / 'CPython-3.11.9-LICENSE.txt')
    shutil.copyfile(root / 'dist/homr-source-v0.7.0/LICENSE', output / 'HOMR-0.7.0-AGPL.txt')
    shutil.copyfile(root / 'assets/offline_piano/ATTRIBUTION.md', output / 'Salamander-ATTRIBUTION.md')
    (output / 'notice-inventory.json').write_text(json.dumps(
        {'status': 'evidence-not-certification', 'packages': records, 'archives': archives},
        ensure_ascii=False, indent=2), encoding='utf-8')
    print('Collected', len(records), 'package inventories;', sum(len(r['notices']) for r in records),
          'installed notices;', sum(a['notice_files'] for a in archives), 'source notices')
    missing = [r['name'] for r in records if not r['notices']]
    print('Packages without installed notice files:', ', '.join(missing))


if __name__ == '__main__':
    main()
