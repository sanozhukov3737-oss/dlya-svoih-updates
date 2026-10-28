"""Verify identity separation, exact allowed edits, exterior assets and real FTS."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from PIL import Image
from build_catalog import validate
ROOT=Path(__file__).resolve().parents[1]

def verify(baseline,catalog,database):
    raw=Path(baseline).read_bytes();before=json.loads(raw);after=json.loads(Path(catalog).read_text());o=json.loads((ROOT/'content/overlays/school-images-20261028.json').read_text());validate(after)
    assert hashlib.sha256(raw).hexdigest()==o['baseCatalogSha256']
    old={c['id']:c for c in before['cards']};new={c['id']:c for c in after['cards']};changes={c['cardId']:c for c in o['changes']}
    for cid,c in old.items():
        expected=dict(c)
        if cid in changes:expected.update(changes[cid]['after'])
        assert new[cid]==expected,cid
        assert new[cid]['rowid']==c['rowid']
    assert len(after['cards'])==len(before['cards'])+1
    assert len({c['rowid'] for c in after['cards']})==len(after['cards'])
    assert new['atlas-mib']['categoryId']=='target-sensors-boards'
    assert new['pdf198-school-mib-engineering']['categoryId']=='mines-special'
    assert 'плата' in new['atlas-mib']['body'].lower()
    assert not any('Информационно-справочный материал 2025.pdf' in s['title'] and 'PDF-стр. 140;' in s['title'] for s in new['atlas-mib']['sources'])
    assert any('PDF-стр. 140;' in s['title'] for s in new['pdf198-school-mib-engineering']['sources'])
    for cid in ('ordnance-v27-vog-17-vog-17m','ordnance-v27-vog-25'):
        assert all('grenade-vog17-vog25-sesu-ccby4' not in im['localPath'] for im in new[cid]['images'])
    assets=set()
    for row in o['review']:
        for k in ('localPath','thumbnailPath'):
            path=row['asset'][k];assets.add(path)
            with Image.open(ROOT/'app/src/main/assets'/path) as im:im.load()
    for s in o['sources']:
        assert s['storedSize'][0]<=s['figureNativeSize'][0] and s['storedSize'][1]<=s['figureNativeSize'][1]
    assert o['sources'][0]['exteriorCrop']==[0,0,949,250]
    db=sqlite3.connect(database);assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not db.execute('PRAGMA foreign_key_check').fetchall();db.execute("INSERT INTO cards_fts(cards_fts) VALUES ('integrity-check')")
    for cid in [*changes,'pdf198-school-mib-engineering']:
        row=db.execute('SELECT rowid,searchText FROM cards WHERE id=?',(cid,)).fetchone();assert row and row[1].strip();assert db.execute('SELECT count(*) FROM cards_fts WHERE docid=?',(row[0],)).fetchone()[0]==1
    result={'integrity':'ok','foreignKeys':'ok','fts':'ok','previousCardIdsAndRowidsPreserved':len(old),'newCards':1,'newNativeFigures':len(o['sources']),'decodedImageAndThumbnailFiles':len(assets),'replacedGalleryRows':o['summary']['replacedImageRows'],'addedGalleryRows':o['summary']['addedImageRows'],'cardCount':len(after['cards']),'imageCount':sum(len(c['images']) for c in after['cards']),'mibBoardSeparatedFromEngineeringMunition':True,'coverImagesReplaced':True,'androidImportTested':False,'published':False}
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--catalog',required=True);p.add_argument('--database',required=True);p.add_argument('--report',required=True);a=p.parse_args();r=verify(a.baseline,a.catalog,a.database);Path(a.report).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False,indent=2))
