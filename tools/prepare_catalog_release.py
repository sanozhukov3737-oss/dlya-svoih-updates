"""Package the checked bundled database without changing SQLite compatibility."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile
from build_catalog import ROOT, ASSETS, normalize, validate
from build_update_feed import write_feed


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(request_path, previous_feed, output):
    request = json.loads(Path(request_path).read_text(encoding='utf-8'))
    source = ROOT / 'content/catalog.json'
    database = ASSETS / 'database/guide-v29.db'
    data = json.loads(source.read_text(encoding='utf-8'))
    version = request['contentVersion']
    if sha(source) != request['catalogSha256'] or sha(database) != request['databaseSha256']:
        raise ValueError('Release source differs from the approved snapshot')
    if data['contentVersion'] != version or data['catalogVersion'] != version:
        raise ValueError('Catalog version mismatch')
    previous = json.loads(Path(previous_feed).read_text(encoding='utf-8'))
    if previous['contentVersion'] >= version:
        raise ValueError('Publication must increase the offered catalog version')
    validate(data)
    with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        if tuple(db.execute('PRAGMA user_version').fetchone()) != (3,):
            raise ValueError('Unsupported database schema')
        if tuple(db.execute('PRAGMA integrity_check').fetchone()) != ('ok',) or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Database integrity failure')
        if tuple(db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()) != (str(version),):
            raise ValueError('Database content version mismatch')
        for table in ('favorites', 'reading'):
            if db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]:
                raise ValueError('Release contains user data')
        expected = []
        for c in data['cards']:
            row = {k: c[k] for k in ('rowid', 'id', 'section', 'categoryId', 'title', 'summary', 'body',
                'contentStatus', 'reviewedAt', 'modelStatus', 'sourceGrade', 'verifiedAt')}
            row.update(archived=0, tags=' · '.join(c['tags']), sortTitle=normalize(c['title']),
                searchText=normalize(' '.join([c['title'], c['summary'], c['body'].split('\n\n## Служебные сведения', 1)[0], *c['tags']])),
                thumbnailPath=c['images'][0]['thumbnailPath'] if c['images'] else None)
            expected.append(row)
        if sorted(expected, key=lambda x: x['id']) != sorted([dict(r) for r in db.execute('SELECT * FROM cards')], key=lambda x: x['id']):
            raise ValueError('Database cards differ from catalog')
        for table, rows, keys in (
            ('countries', data['countries'], ('id', 'name', 'sortOrder')),
            ('categories', data['categories'], ('id', 'section', 'title', 'sortOrder')),
            ('card_countries', [dict(cardId=c['id'], countryId=country) for c in data['cards'] for country in c['countries']], ('cardId', 'countryId')),
            ('images', [dict(image, cardId=c['id']) for c in data['cards'] for image in c['images']], ('id', 'cardId', 'localPath', 'caption', 'width', 'height', 'position')),
            ('sources', [dict(s, cardId=c['id']) for c in data['cards'] for s in c['sources']], ('id', 'cardId', 'title', 'url', 'accessedAt')),
        ):
            wanted = sorted(tuple(str(r[k]) for k in keys) for r in rows)
            actual = sorted(tuple(str(r[k]) for k in keys) for r in db.execute('SELECT * FROM ' + table))
            if wanted != actual:
                raise ValueError('Database differs from catalog: ' + table)
    media = sorted({image[k] for c in data['cards'] for image in c['images'] for k in ('localPath', 'thumbnailPath')})
    files = [('guide.db', database)] + [(name, ASSETS / name) for name in media]
    manifest = dict(formatVersion=1, contentVersion=version, files=[
        dict(path=name, bytes=path.stat().st_size, sha256=sha(path)) for name, path in files])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    pack = output / f'catalog-{version}.zip'
    temporary = pack.with_suffix('.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, separators=(',', ':')))
            for name, path in files:
                archive.write(path, name)
        temporary.replace(pack)
    finally:
        temporary.unlink(missing_ok=True)
    repository = 'https://github.com/sanozhukov3737-oss/dlya-svoih-updates'
    feed = write_feed(pack, f'{repository}/releases/download/catalog-{version}/{pack.name}',
        output / 'latest.json', request['changes'], request['minAppCode'], previous_feed)
    if feed.get('app') != previous.get('app'):
        raise ValueError('Existing APK offer changed')
    (output / 'notes.txt').write_text(request['changes'] + '\n', encoding='utf-8')
    print(json.dumps(dict(version=version, cards=len(data['cards']), bytes=feed['bytes'], sha256=feed['sha256'])))
    return feed


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--previous-feed', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.request, args.previous_feed, args.output)
