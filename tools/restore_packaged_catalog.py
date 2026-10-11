"""Restore the immutable published catalog into APK assets before a CI build."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://github.com/sanozhukov3737-oss/dlya-svoih-updates/releases/download/catalog-188/catalog-188.zip'
SHA256 = 'e5bfa1d9fea163f5119ee200f5729c991d55231c0950178a85d469aae2e0001f'
SIZE = 85957620
VERSION = 188


def restore(archive):
    archive = Path(archive)
    if archive.stat().st_size != SIZE or hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError('Published catalog hash/size mismatch')
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('manifest.json'))
        if manifest['formatVersion'] != 1 or manifest['contentVersion'] != VERSION:
            raise ValueError('Wrong catalog version')
        expected = {f['path'] for f in manifest['files']}
        if len(expected) != len(manifest['files']) or set(z.namelist()) != expected | {'manifest.json'}:
            raise ValueError('Catalog file list mismatch')
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            for f in manifest['files']:
                name = f['path']
                parts = PurePosixPath(name).parts
                if name != 'guide.db' and not (len(parts) == 2 and parts[0] in ('images', 'thumbs')
                                              and name.endswith('.webp') and '\\' not in name):
                    raise ValueError('Unexpected catalog asset')
                value = z.read(name)
                if len(value) != f['bytes'] or hashlib.sha256(value).hexdigest() != f['sha256']:
                    raise ValueError('Catalog asset hash mismatch')
                dest = stage / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(value)
            with sqlite3.connect(stage / 'guide.db') as db:
                version = db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()[0]
                if version != str(VERSION) or db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Catalog database validation failed')
            assets = ROOT / 'app/src/main/assets'
            for directory in ('images', 'thumbs'):
                # Only packaged build assets; user data is never accessed by this tool.
                if (assets / directory).exists():
                    shutil.rmtree(assets / directory)
                shutil.copytree(stage / directory, assets / directory)
            shutil.copyfile(stage / 'guide.db', assets / 'database/guide-v29.db')
            (assets / 'database/content-version.txt').write_text(str(VERSION) + '\n')
    print(f'Restored catalog {VERSION}: {len(expected)} validated assets')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    if args.archive:
        restore(args.archive)
    else:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'catalog.zip'
            with urllib.request.urlopen(URL, timeout=60) as response, target.open('wb') as out:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > SIZE:
                        raise ValueError('Catalog download exceeds expected size')
                    out.write(chunk)
            restore(target)
