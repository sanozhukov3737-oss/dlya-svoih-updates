"""Read-only host probes. These numbers are not Android transition timings."""
from pathlib import Path
import hashlib
import json
import platform
import random
import re
import shutil
import sqlite3
import statistics
import struct
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "app/src/main/java/ru/dlyasvoih/app"
DB = ROOT / "app/src/main/assets/database/guide-v29.db"
EXPECTED_DB = "a2cf495b7476e65a52d8f14b22fe737e812310c4c49ee4aa784afd27ab59e8b5"

JAVA = r'''
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import ru.dlyasvoih.app.data.CardFamilies;
import ru.dlyasvoih.app.ui.content.*;
public class TextProbe {
  static volatile int sink;
  static String read(DataInputStream in) throws IOException {
    return new String(in.readNBytes(in.readInt()), StandardCharsets.UTF_8);
  }
  static int prepare(List<String> raw, boolean mortar) {
    List<String> article = ReaderContent.article(raw, mortar);
    return article.size() + ReaderNavigation.sections(article).size()
        + ReaderNavigation.matchingParagraphs(article, "").size();
  }
  public static void main(String[] args) throws Exception {
    List<String> ids = new ArrayList<>();
    List<Boolean> mortar = new ArrayList<>();
    List<List<String>> paragraphs = new ArrayList<>();
    try (DataInputStream in = new DataInputStream(new FileInputStream(args[0]))) {
      int count = in.readInt();
      for (int i=0; i<count; i++) {
        ids.add(read(in)); mortar.add(read(in).equals("mortars"));
        // Splitting already happens off the UI thread in DetailViewModel.
        paragraphs.add(Arrays.asList(read(in).split("\n\n", -1)));
      }
    }
    List<Integer> order = new ArrayList<>();
    for (int i=0; i<ids.size(); i++) order.add(i);
    Random random = new Random(136);
    for (int round=0; round<8; round++) {
      Collections.shuffle(order, random);
      for (int i:order) sink = prepare(paragraphs.get(i), mortar.get(i));
    }
    long[][] samples = new long[ids.size()][15];
    for (int round=0; round<15; round++) {
      Collections.shuffle(order, random);
      for (int i:order) {
        long start = System.nanoTime();
        sink = prepare(paragraphs.get(i), mortar.get(i));
        samples[i][round] = System.nanoTime()-start;
      }
    }
    for (int i=0; i<ids.size(); i++) {
      Arrays.sort(samples[i]);
      System.out.println(ids.get(i)+"\t"+samples[i][7]+"\t"
          +String.join(",",CardFamilies.relatedIds(ids.get(i))));
    }
  }
}
'''


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[round((len(ordered)-1)*fraction)]


def summary(values):
    return {"medianMs": round(statistics.median(values), 6),
            "p95Ms": round(percentile(values, .95), 6),
            "maxMs": round(max(values), 6)}


def main():
    digest = hashlib.sha256(DB.read_bytes()).hexdigest()
    if digest != EXPECTED_DB:
        raise SystemExit("This probe is pinned to the database shipped with 0.3.136")
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cards = db.execute("SELECT id,categoryId,body,section FROM cards WHERE archived=0 ORDER BY rowid").fetchall()
    java = shutil.which("java")
    if not java:
        raise SystemExit("A JDK with jdk.compiler is required")
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        fixture = temp / "cards.bin"
        with fixture.open("wb") as out:
            out.write(struct.pack(">i", len(cards)))
            for card in cards:
                for text in card[:3]:
                    encoded = text.encode("utf-8")
                    out.write(struct.pack(">i", len(encoded)))
                    out.write(encoded)
        host = temp / "TextProbe.java"
        host.write_text(JAVA)
        sources = [SOURCE / f"ui/content/{name}.java" for name in
                   ("ReferenceBodyParser", "ReaderContent", "ReaderNavigation")]
        sources += [SOURCE / "data/CardFamilies.java", host]
        subprocess.run([java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "-d", str(temp),
                        *map(str, sources)], check=True, capture_output=True, text=True, timeout=30)
        probe = subprocess.run([java, "-cp", str(temp), "TextProbe", str(fixture)],
                               check=True, capture_output=True, text=True, timeout=45)
    parsed = [line.split("\t") for line in probe.stdout.splitlines()]
    timings = {row[0]: int(row[1])/1e6 for row in parsed}
    families = {row[0]: row[2].split(",") if len(row)>2 and row[2] else [] for row in parsed}
    dao = (SOURCE / "data/local/GuideDao.kt").read_text()
    queries = {name: sql for sql, name in re.findall(r'@Query\("""(.*?)"""\)\s*fun\s+(\w+)', dao, re.S)
               if name in ("relatedCards", "comparisonCards")}
    assert set(queries) == {"relatedCards", "comparisonCards"}
    groups = {}
    for card in cards:
        groups.setdefault((card[3],card[1]),[]).append(card[0])
    probes = list(dict.fromkeys([v[0] for v in groups.values()] + ["eng-pmn", "eng-pmn-2", "eng-tm-46"]))
    probes = [id for id in probes if id in timings]
    query_results = []
    random.Random(136).shuffle(probes)
    for id in probes:
        for name, query in queries.items():
            params = []
            def bind(match):
                if match.group() == ":id":
                    params.append(id)
                    return "?"
                values = families[id]
                params.extend(values)
                return ",".join("?" for _ in values) if values else "NULL"
            sql = re.sub(r":id|:familyIds", bind, query)
            db.execute(sql, params).fetchall()  # Warm page cache and statement.
            samples = []
            for _ in range(25):
                start = time.perf_counter_ns()
                rows = db.execute(sql, params).fetchall()
                samples.append((time.perf_counter_ns()-start)/1e6)
            query_results.append({"id": id, "query": name, "rows": len(rows), **summary(samples)})
    largest = sorted(groups, key=lambda key:len(groups[key]), reverse=True)[:8]
    result = {
        "kind": "read-only host diagnostic, not Android frame or transition timings",
        "productSource": "c05e63305c53d0e4c92c9f8edd0a7c4076198ed7",
        "dbSha256": digest, "contentVersion": db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()[0],
        "environment": {"machine": platform.machine(), "sqliteVersion": sqlite3.sqlite_version,
                        "javaVersion": subprocess.run([java,"-version"],capture_output=True,text=True,check=True,timeout=10).stderr.splitlines()[0]},
        "activeCards": len(cards),
        "largestCategories": [{"section":key[0],"categoryId":key[1],"cards":len(groups[key]),"comparisonCandidates":len(groups[key])-1} for key in largest],
        "bodyChars": {"median":statistics.median(len(card[2]) for card in cards),"max":max(len(card[2]) for card in cards)},
        "textPreparation": {"method":"Actual Java article()+sections()+empty-query matchingParagraphs(); inputs pre-split; 8 shuffled warm-up passes, 15 timed passes; distribution of each card's median; excludes Android layout, text measurement, per-visible-block parsing and image work", **summary(list(timings.values())),
                            "slowestCardByMedian":max(timings,key=timings.get)},
        "imagesMetadata": dict(zip(("count","maxWidth","maxHeight","over2048"), db.execute("SELECT count(*),max(width),max(height),sum(CASE WHEN width>2048 OR height>2048 THEN 1 ELSE 0 END) FROM images").fetchone())),
        "sqlMethod":"Actual DAO SQL, actual Java CardFamilies.relatedIds(), one card per section/category plus named samples; Python fetchall mapping, warm host page cache, 25 repeats each; not Room/Android scheduling or cold storage latency",
        "queryProbes":query_results,
        "limits":["No APK changed or built; no emulator or physical phone run", "No rendering, decoding, memory-cache hit-rate or next-card time measured", "Warm host measurements cannot establish which operation dominates a phone transition or predict an improvement"]
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
