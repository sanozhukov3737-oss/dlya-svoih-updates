"""Package the full restored database; never rebuild it from the partial JSON."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import zipfile

from build_update_feed import describe_pack


def make_pack(assets, output, version, cards, images):
    if sqlite3.sqlite_version_info > (3, 45, 1):
        raise ValueError('Use SQLite 3.45.1 or older for the Android database')
    assets, output = Path(assets), Path(output)
    database = assets / 'database/guide-v29.db'
    if (assets / 'database/content-version.txt').read_text().strip() != str(version):
        raise ValueError('Wrong restored asset version')
    with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as db:
        if db.execute('PRAGMA user_version').fetchone() != (3,):
            raise ValueError('Wrong database schema')
        if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise ValueError('Database integrity failure')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Broken database relationships')
        if db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone() != (str(version),):
            raise ValueError('Database version mismatch')
        if db.execute('SELECT COUNT(*) FROM cards').fetchone() != (cards,):
            raise ValueError('Incomplete restored catalog')
        if db.execute('SELECT COUNT(*) FROM images').fetchone() != (images,):
            raise ValueError('Incomplete restored illustrations')
        if any(db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
               for table in ('favorites', 'reading')):
            raise ValueError('Release contains user data')
        media = sorted({row[0] for row in db.execute(
            'SELECT localPath FROM images UNION SELECT thumbnailPath FROM cards WHERE thumbnailPath IS NOT NULL')})
    # Thumbnail names are not derived from full image names. Keep the actual
    # restored thumbnail directory, including secondary-image thumbnails.
    media = sorted(set(media) | {path.relative_to(assets).as_posix()
                                for path in (assets / 'thumbs').iterdir() if path.is_file()})
    for name in media:
        if not re.fullmatch(r'(?:images|thumbs)/[a-zA-Z0-9_-]{1,96}\.(?:webp|png|jpg|jpeg)', name):
            raise ValueError('Invalid catalog media path: ' + name)
    files = [('guide.db', database)] + [(name, assets / name) for name in media]
    manifest = dict(formatVersion=1, contentVersion=version, files=[
        dict(path=name, bytes=path.stat().st_size,
             sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for name, path in files])
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, separators=(',', ':')))
            for name, path in files:
                archive.write(path, name)
        # Verify the actual ZIP against the importer's format before promotion.
        describe_pack(temporary, 'https://example.invalid/catalog.zip')
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(contentVersion=version, cards=cards, images=images,
                bytes=output.stat().st_size, sha256=hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--version', type=int, required=True)
    parser.add_argument('--cards', type=int, required=True)
    parser.add_argument('--images', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(make_pack(args.assets, args.output, args.version, args.cards, args.images)))
