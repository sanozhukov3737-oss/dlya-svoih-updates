"""Validate the third image batch, preserving distinct DM31 and TS/VS identities."""
from pathlib import Path
import json,hashlib,argparse,sqlite3
from PIL import Image
from build_catalog import validate
ROOT=Path(__file__).resolve().parents[1]
def verify(baseline,catalog,database):
    raw=Path(baseline).read_bytes();before=json.loads(raw);after=json.loads(Path(catalog).read_text());o=json.loads((ROOT/'content/overlays/school-images-b3-20261028.json').read_text());validate(after)
    assert hashlib.sha256(raw).hexdigest()==o['baseCatalogSha256']
    old={c['id']:c for c in before['cards']};new={c['id']:c for c in after['cards']};changes={c['cardId']:c for c in o['changes']}
    for cid,c in old.items():
        expected=dict(c)
        if cid in changes:expected.update(changes[cid]['after'])
        assert new[cid]==expected,cid
        assert new[cid]['rowid']==c['rowid']
    assert len(new)==len(old)+1 and len({c['rowid'] for c in after['cards']})==len(new)
    assert new['eng-pdf-v7-007']==old['eng-pdf-v7-007'] # AP DM31 is not the wide AT model.
    assert 'eng-dm-31-at' in changes
    assert new['eng-ts-50']==old['eng-ts-50'] and new['eng-vs-1-6-family']==old['eng-vs-1-6-family']
    assert new['grenade-f1-soviet']==old['grenade-f1-soviet']
    ts=new['pdf198-school3-ts-6-1'];assert ts['categoryId']=='mines-antitank' and ts['contentStatus']=='source_only' and ts['verifiedAt'] is None
    assert not old['pdf198-3-cf1a8ba4a02e']['images'] and new['pdf198-3-cf1a8ba4a02e']['images']
    assets={r['asset'][k] for r in o['review'] if 'asset' in r for k in ['localPath','thumbnailPath']}
    for name in assets:
        with Image.open(ROOT/'app/src/main/assets'/name) as im:im.load()
    for r in o['review']:
        if 'asset' in r:assert r['asset']['width']<=r['nativeSize'][0] and r['asset']['height']<=r['nativeSize'][1]
    assert not any(r.get('asset') for r in o['review'] if r['file'] in ['M67 для школы.pdf','DM51 для школы.pdf'] and r['figure']==1)
    db=sqlite3.connect(database);assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not db.execute('PRAGMA foreign_key_check').fetchall();db.execute("INSERT INTO cards_fts(cards_fts) VALUES ('integrity-check')")
    for cid in [*changes,ts['id']]:
        row=db.execute('SELECT rowid,searchText FROM cards WHERE id=?',(cid,)).fetchone();assert row and row[1].strip();assert db.execute('SELECT count(*) FROM cards_fts WHERE docid=?',(row[0],)).fetchone()[0]==1
    return {'integrity':'ok','foreignKeys':'ok','fts':'ok','previousCardIdsAndRowidsPreserved':len(old),'newCards':1,'decodedImageAndThumbnailFiles':len(assets),'replacedGalleryRows':o['summary']['replacedGalleryRows'],'addedGalleryRows':o['summary']['addedGalleryRows'],'cardCount':len(new),'imageCount':sum(len(c['images']) for c in after['cards']),'dm31AtSeparatedFromAp':True,'ts61SeparatedFromTs50AndVs16':True,'androidImportTested':False,'published':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--catalog',required=True);p.add_argument('--database',required=True);p.add_argument('--report',required=True);a=p.parse_args();r=verify(a.baseline,a.catalog,a.database);Path(a.report).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False,indent=2))
