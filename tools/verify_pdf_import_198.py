"""Check source identities, native images, search, and catalog 197 preservation."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
from PIL import Image
from build_catalog import validate

ROOT=Path(__file__).resolve().parents[1]

def verify(catalog, database, baseline=None):
    baseline=Path(baseline) if baseline else ROOT/'content/catalog.json'
    old=json.loads(baseline.read_text())
    overlay=json.loads((ROOT/'content/overlays/pdf-import-20261028.json').read_text())
    assert old['contentVersion']==197
    assert hashlib.sha256(baseline.read_bytes()).hexdigest()==overlay['baseCatalogSha256']
    new=json.loads(Path(catalog).read_text())
    validate(new)
    before={c['id']:c for c in old['cards']}
    after={c['id']:c for c in new['cards']}
    assert len(new['cards'])==len(old['cards'])+len(overlay['cards'])
    for cid,c in before.items():
        for k,v in c.items():
            if k!='sources':assert after[cid][k]==v,(cid,k)
        assert all(s in after[cid]['sources'] for s in c['sources'])
    assert all(c['section']!='MEDICINE' for c in overlay['cards'])
    assert all(c['contentStatus']=='source_only' and c['verifiedAt'] is None for c in overlay['cards'])
    assert len({c['rowid'] for c in new['cards']})==len(new['cards'])
    assert sum(s['pages'] for s in overlay['sources'])==1517
    assert {s['id'] for s in overlay['sources']}==set(range(1,9))
    image_count=0
    for c in overlay['cards']:
        for im in c['images']:
            for key in ('localPath','thumbnailPath'):
                with Image.open(ROOT/'app/src/main/assets'/im[key]) as pic:
                    pic.load()
            assert 'инертн' not in c['title'] or not c['id'].startswith('pdf198-2-')
            image_count+=1
    db=sqlite3.connect(database)
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    db.execute("INSERT INTO cards_fts(cards_fts) VALUES ('integrity-check')")
    assert db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()[0]=='198'
    for c in overlay['cards']:
        row=db.execute('SELECT rowid,searchText FROM cards WHERE id=?',(c['id'],)).fetchone()
        assert row and row[0]==c['rowid'] and row[1].strip()
        # Every generated reference participates in the real FTS index.
        assert db.execute('SELECT count(*) FROM cards_fts WHERE docid=?',(row[0],)).fetchone()[0]==1
    # Previously confused identities stay separate: Australian F1 / Soviet F1;
    # SHARK / MiniShark; MON-100 / MON-100.1; MPM-E / TMK-2VZ.
    assert any('F1 (Австралия)'==c['title'] for c in overlay['cards'])
    assert after['grenade-f1-soviet']['title']==before['grenade-f1-soviet']['title']
    assert any('MiniShark' in c['title'] for c in overlay['cards'])
    assert any(c['title']=='ТМК-2ВЗ' and not c['images'] for c in overlay['cards'])
    assert any(c['title']=='МПМ-Э' for c in overlay['cards'])
    for e in overlay['enrichments']:
        if e['cardId']=='handbookref-mon-100-1':
            assert not any('PDF-стр. 131;' in s['title'] for s in e['sources'])
    result={'integrity':'ok','foreignKeys':'ok','fts':'ok','allNewReferencesIndexed':len(overlay['cards']),
        'oldCardIdsAndRowidsPreserved':len(before),'oldTextAndPhotos':'unchanged',
        'newImagesFullyDecoded':image_count,'existingPhotoReplacements':0,
        'independentTechnicalVerification':False,'androidImportTested':False,'published':False}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--catalog',required=True);p.add_argument('--database',required=True);p.add_argument('--report');p.add_argument('--baseline')
    a=p.parse_args();result=verify(a.catalog,a.database,a.baseline)
    if a.report:Path(a.report).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
