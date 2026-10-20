"""Restore the immutable published catalog into APK assets before a CI build."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile
import urllib.request
import zipfile
from correct_upmo_origin import correct_database
from apply_uav_reference import apply_database as apply_uav, PAYLOAD as UAV_PAYLOAD
from apply_demz_catalog import apply_database as apply_demz, PAYLOAD as DEMZ_PAYLOAD
from apply_uav_handbook import apply_database as apply_handbook, PAYLOAD as HANDBOOK_PAYLOAD
from apply_handbook_images import apply_database as apply_handbook_images, PAYLOAD as HANDBOOK_IMAGES_PAYLOAD

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://github.com/sanozhukov3737-oss/dlya-svoih-updates/releases/download/catalog-190/catalog-190.zip'
SHA256 = '004f5493da6ed40fb984088ec1b41b2e2a503d1119717e81c53a27f802ea1a21'
SIZE = 82353859
VERSION = 190


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
            # The baseline archive deliberately remains immutable. Preserve the
            # checked-in exterior illustrations before replacing its asset dirs.
            overlay_assets = {}
            for payload_path in (UAV_PAYLOAD, DEMZ_PAYLOAD, HANDBOOK_PAYLOAD, HANDBOOK_IMAGES_PAYLOAD):
                overlay = json.loads(payload_path.read_text(encoding='utf-8'))
                for f in overlay['assetFiles']:
                    name = f['path']
                    parts = PurePosixPath(name).parts
                    if (len(parts) != 2 or parts[0] not in ('images', 'thumbs')
                            or not parts[1].startswith(('uavref-', 'demzref-', 'handbookref-'))
                            or not name.endswith('.webp') or '\\' in name):
                        raise ValueError('Unexpected reference asset')
                    value = (assets / name).read_bytes()
                    if len(value) != f['bytes'] or hashlib.sha256(value).hexdigest() != f['sha256']:
                        raise ValueError('Reference asset hash mismatch')
                    if name in overlay_assets and overlay_assets[name] != value:
                        raise ValueError('Reference asset path collision')
                    overlay_assets[name] = value
            correct_database(stage / 'guide.db')
            apply_uav(stage / 'guide.db')
            apply_demz(stage / 'guide.db')
            apply_handbook(stage / 'guide.db')
            corrected_version = apply_handbook_images(stage / 'guide.db')
            for directory in ('images', 'thumbs'):
                # Only packaged build assets; user data is never accessed by this tool.
                if (assets / directory).exists():
                    shutil.rmtree(assets / directory)
                shutil.copytree(stage / directory, assets / directory)
            for name, value in overlay_assets.items():
                (assets / name).write_bytes(value)
            shutil.copyfile(stage / 'guide.db', assets / 'database/guide-v29.db')
            (assets / 'database/content-version.txt').write_text(str(corrected_version) + '\n')
    print(f'Restored catalog {VERSION} with prepared reference additions as {corrected_version}: '
          f'{len(expected)} baseline assets, {len(overlay_assets)} reference images')


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
