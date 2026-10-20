#!/usr/bin/env python3
"""Repair the five malformed derived search fields found by actual Android upgrade QA.

Uses the production Java normalizer and reader projection. Does not alter article
text, permanent identifiers, metadata, media, compiled code or model assets.
"""
import argparse
import base64
import copy
import hashlib
import json
import sqlite3
import subprocess
import tempfile
import zipfile
from pathlib import Path

ORIGINAL_APK_SHA = '43ffc8b8d8ba2a632d3d13a5f287a4fb6a6a43bddf008122026186aa2a0197f4'
ORIGINAL_DB_SHA = '937b641c3296fb7ea381674d5854e514b7ea84d604060fcc6b52ee9890b4ed8b'
EXPECTED = {'eng-pdf-v7-116', 'ordnance-v27-m-6-vzryvatel',
            'ordnance-v27-m-12-vzryvatel', 'handbookref-pb-1u', 'handbookref-pni-1'}
DB_ASSET = 'assets/database/guide-v29.db'
JAVA = r'''import java.nio.file.*; import java.nio.charset.*; import java.util.*;
import ru.dlyasvoih.app.data.CatalogSearch;
import ru.dlyasvoih.app.ui.content.ReaderContent;
public class CheckSearch134 {
  public static void main(String[] args) throws Exception {
    for (String line : Files.readAllLines(Paths.get(args[0]))) {
      String[] fields = line.split("\t", -1);
      for (int i=0; i<fields.length; i++) fields[i] = new String(
          Base64.getDecoder().decode(fields[i]), StandardCharsets.UTF_8);
      String tags = fields[3].replace(" · ", " ");
      String legacy = CatalogSearch.normalize(String.join(" ", fields[0], fields[1], fields[2], tags));
      String reader = CatalogSearch.normalize(String.join(" ", fields[0], fields[1],
          ReaderContent.searchableBody(fields[2]), tags));
      System.out.println(Base64.getEncoder().encodeToString(legacy.getBytes(StandardCharsets.UTF_8))
          + "\t" + Base64.getEncoder().encodeToString(reader.getBytes(StandardCharsets.UTF_8)));
    }
  }
}'''


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def repair(apk, source_tree, output):
    assert sha(apk.read_bytes()) == ORIGINAL_APK_SHA, 'Original candidate changed'
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(apk) as original, tempfile.TemporaryDirectory(prefix='search134-') as tmp:
        work = Path(tmp)
        raw = original.read(DB_ASSET)
        assert sha(raw) == ORIGINAL_DB_SHA
        db_path = work/'guide.db'; db_path.write_bytes(raw)
        db = sqlite3.connect(db_path); db.row_factory = sqlite3.Row
        rows = db.execute('SELECT * FROM cards ORDER BY rowid').fetchall()
        assert len(rows) == 1697
        helper = work/'CheckSearch134.java'; helper.write_text(JAVA)
        production = source_tree/'app/src/main/java/ru/dlyasvoih/app'
        subprocess.run(['java', '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-d', str(work),
            str(production/'data/CatalogSearch.java'), str(production/'ui/content/ReferenceBodyParser.java'),
            str(production/'ui/content/ReaderContent.java'), str(helper)], check=True)
        payload = work/'cards.tsv'
        payload.write_text('\n'.join('\t'.join(base64.b64encode(r[k].encode()).decode()
            for k in ('title','summary','body','tags')) for r in rows)+'\n')
        checked = subprocess.run(['java','-cp',str(work),'CheckSearch134',str(payload)],
                                 capture_output=True,text=True,check=True)
        expected = [[base64.b64decode(x).decode() for x in line.split('\t')]
                    for line in checked.stdout.splitlines()]
        fixes = [(row['id'], pair[1]) for row,pair in zip(rows,expected,strict=True)
                 if row['searchText'] not in pair]
        assert {cid for cid,_ in fixes} == EXPECTED
        original_tables = {r[0]: db.execute('SELECT * FROM "'+r[0]+'" ORDER BY rowid').fetchall()
            for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'cards_fts%' AND name!='cards'").fetchall()}
        for cid, value in fixes:
            db.execute('UPDATE cards SET searchText=? WHERE id=?', (value,cid))
        db.commit()
        after = db.execute('SELECT * FROM cards ORDER BY rowid').fetchall()
        for before,new,pair in zip(rows,after,expected,strict=True):
            assert new['searchText'] in pair, new['id']
            assert all(before[k] == new[k] for k in before.keys() if k != 'searchText'), new['id']
        for table, values in original_tables.items():
            assert db.execute('SELECT * FROM "'+table+'" ORDER BY rowid').fetchall() == values, table
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        db.close()
        fixed = db_path.read_bytes()
        repaired = output/'DLYA_SVOIH_v0.3.134-search-fixed-unsigned.apk'
        with zipfile.ZipFile(repaired,'w') as target:
            for info in original.infolist():
                target.writestr(copy.copy(info), fixed if info.filename == DB_ASSET else original.read(info.filename))
        with zipfile.ZipFile(repaired) as target:
            assert target.namelist() == original.namelist()
            changed = [n for n in original.namelist() if original.read(n) != target.read(n)]
            assert changed == [DB_ASSET], changed
        (output/'guide-v29.db').write_bytes(fixed)
        report = {'originalUnsignedApkSha256':ORIGINAL_APK_SHA, 'originalDatabaseSha256':ORIGINAL_DB_SHA,
                  'repairedUnsignedApkSha256':sha(repaired.read_bytes()),'repairedDatabaseSha256':sha(fixed),
                  'validatedCardSearchFields':len(rows),'repairedCardIds':sorted(EXPECTED),
                  'rootCause':'Stored searchText retained middle-dot tag separators rejected by ContentUpdater.validate',
                  'onlyChangedApkEntry':DB_ASSET,'allOtherCardColumnsUnchanged':True,
                  'allOtherLogicalTablesUnchanged':True,'integrityCheck':'ok','foreignKeyViolations':0}
        (output/'search-repair-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk',type=Path,required=True)
    parser.add_argument('--source-tree',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    repair(args.apk,args.source_tree,args.out)
