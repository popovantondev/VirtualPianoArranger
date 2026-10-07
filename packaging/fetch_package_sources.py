"""Download exact PyPI source distributions, never install or execute them."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
from urllib.parse import quote, urlsplit


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('inventory', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    seen = set()
    for package in json.loads(args.inventory.read_text(encoding='utf-8'))['packages']:
        key = (package['name'], package['version'])
        if key in seen:
            continue
        seen.add(key)
        with urllib.request.urlopen('https://pypi.org/pypi/' + quote(key[0]) + '/' + quote(key[1]) + '/json', timeout=30) as response:
            data = json.load(response)
        sdists = [item for item in data['urls'] if item['packagetype'] == 'sdist']
        record = {'name': key[0], 'version': key[1], 'project_urls': data['info'].get('project_urls'), 'sources': []}
        for item in sdists:
            name = item['filename']
            if Path(name).name != name or urlsplit(item['url']).hostname != 'files.pythonhosted.org':
                raise ValueError('Unexpected source distribution URL/path')
            target = args.output / name
            expected = item['digests']['sha256']
            complete = target.is_file() and digest(target) == expected
            if not complete:
                result = subprocess.run(['curl.exe', '-sS', '-L', '--fail', '--continue-at', '-',
                    '--connect-timeout', '15', '--max-time', '180', '--output', str(target), item['url']])
                complete = result.returncode == 0 and target.is_file() and digest(target) == expected
            record['sources'].append({'file': name, 'url': item['url'], 'sha256': expected, 'verified': complete})
        records.append(record)
        (args.output / 'package-source-downloads.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
        print(key[0], key[1], 'verified source' if sdists and all(x['verified'] for x in record['sources']) else 'NEEDS UPSTREAM SOURCE', flush=True)
    return 0 if all(r['sources'] and all(x['verified'] for x in r['sources']) for r in records) else 1


if __name__ == '__main__':
    raise SystemExit(main())
