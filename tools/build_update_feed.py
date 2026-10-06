"""Describe a verified catalog ZIP for HTTPS delivery; never modifies the input package."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile
from urllib.parse import urlsplit
import zipfile

MAX_ARCHIVE = 256 * 1024 * 1024


def describe_pack(pack, url, changes='', min_app_code=116):
    pack = Path(pack)
    parsed = urlsplit(url)
    if (len(url) > 2048 or parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.fragment):
        raise ValueError('Use an absolute HTTPS package URL without credentials or fragment')
    if not 1 <= pack.stat().st_size <= MAX_ARCHIVE or len(changes) > 5000 or not 1 <= min_app_code <= 2147483647:
        raise ValueError('Invalid publication metadata')
    with zipfile.ZipFile(pack) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)) or 'manifest.json' not in names:
            raise ValueError('Invalid package entries')
        if archive.getinfo('manifest.json').file_size > 2 * 1024 * 1024:
            raise ValueError('Manifest too large')
        manifest = json.loads(archive.read('manifest.json'))
        version = manifest.get('contentVersion')
        if manifest.get('formatVersion') != 1 or not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ValueError('Unsupported package format')
        records = manifest['files']
        paths = [record['path'] for record in records]
        if len(paths) != len(set(paths)) or set(names) != {'manifest.json', *paths} or 'guide.db' not in paths:
            raise ValueError('Incomplete package manifest')
        if len(names) > 20002 or sum(info.file_size for info in infos) > 512 * 1024 * 1024:
            raise ValueError('Package exceeds limits')
        for record in records:
            name = record['path']
            maximum = 64 * 1024 * 1024 if name == 'guide.db' else 4 * 1024 * 1024
            if name != 'guide.db' and not re.fullmatch(r'(?:images|thumbs)/[a-zA-Z0-9_-]{1,96}\.(?:webp|png|jpg|jpeg)', name):
                raise ValueError('Invalid media path')
            info = archive.getinfo(name)
            if info.is_dir() or not 0 < info.file_size <= maximum or info.file_size != record['bytes']:
                raise ValueError('Invalid package file size')
            digest = hashlib.sha256()
            with archive.open(name) as stream:
                for chunk in iter(lambda: stream.read(65536), b''):
                    digest.update(chunk)
            if digest.hexdigest() != record['sha256']:
                raise ValueError('Package file checksum mismatch')
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'guide.db'
            with archive.open('guide.db') as source, database.open('wb') as destination:
                for chunk in iter(lambda: source.read(65536), b''):
                    destination.write(chunk)
            with sqlite3.connect(database) as db:
                installed = db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()
                if installed != (str(version),) or db.execute('PRAGMA user_version').fetchone() != (3,):
                    raise ValueError('Package and database versions differ')
                if any(db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] for table in ('favorites', 'reading')):
                    raise ValueError('Package contains user data')
                if db.execute('PRAGMA foreign_key_check').fetchall():
                    raise ValueError('Broken database relationships')
                media = {row[0] for row in db.execute("SELECT localPath FROM images UNION SELECT thumbnailPath FROM cards WHERE thumbnailPath IS NOT NULL")}
                if not media.issubset(set(paths)):
                    raise ValueError('Package is missing referenced media')
    digest = hashlib.sha256()
    with pack.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            digest.update(chunk)
    return dict(formatVersion=1, contentVersion=version, url=url, bytes=pack.stat().st_size,
                sha256=digest.hexdigest(), changes=changes, minAppCode=min_app_code)


def write_feed(pack, url, output, changes='', min_app_code=116, previous_feed=None):
    if Path(output).resolve() == Path(pack).resolve() or Path(output).with_suffix(Path(output).suffix + '.tmp').resolve() == Path(pack).resolve():
        raise ValueError('Feed output must not overwrite the package')
    result = describe_pack(pack, url, changes, min_app_code)
    if previous_feed is not None:
        from build_app_feed import validate_catalog_feed
        text = Path(previous_feed).read_text(encoding='utf-8')
        if len(text.encode('utf-8')) > 64 * 1024:
            raise ValueError('Previous feed too large')
        previous = validate_catalog_feed(json.loads(text))
        if 'app' in previous:
            result['app'] = previous['app']
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    try:
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pack', type=Path, required=True)
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--changes-file', type=Path)
    parser.add_argument('--min-app-code', type=int, default=116)
    parser.add_argument('--previous-feed', type=Path, help='Preserve the last published APK offer when updating the catalog')
    args = parser.parse_args()
    changes = args.changes_file.read_text(encoding='utf-8') if args.changes_file else ''
    print(json.dumps(write_feed(args.pack, args.url, args.output, changes, args.min_app_code, args.previous_feed), ensure_ascii=False))
