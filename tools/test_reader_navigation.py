"""Exercise real article navigation, literal search and Room's related-model queries."""
from pathlib import Path
import json
import re
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]


class ReaderNavigationTests(unittest.TestCase):
    def test_navigation_and_family_order(self):
        java = shutil.which('java')
        self.assertIsNotNone(java)
        source = r'''
import java.util.*;
import ru.dlyasvoih.app.ui.content.*;
import ru.dlyasvoih.app.data.CardFamilies;
public class NavigationChecks {
  static void check(boolean b) { if (!b) throw new AssertionError(); }
  public static void main(String[] args) {
    List<String> raw = Arrays.asList("## Описание", "ЗЕЛЁНЫЙ корпус; ПМН-2 [М]", "## Характеристики",
        "| Параметр | Значение |\n| --- | --- |\n| Материал | Зелёный пластик |",
        "## Служебные сведения", "секретное редакционное примечание");
    List<String> visible = ReaderContent.article(raw, false);
    check(ReaderNavigation.sections(visible).size() == 2);
    check(ReaderNavigation.sections(visible).get(1).paragraphIndex == 2);
    check(ReaderNavigation.matchingParagraphs(visible, " зелёный ").equals(Arrays.asList(1,3)));
    check(ReaderNavigation.matchingParagraphs(visible, "[м]").equals(Arrays.asList(1)));
    check(ReaderNavigation.matchingParagraphs(visible, ".*").isEmpty());
    check(ReaderNavigation.matchingParagraphs(visible, "секретное").isEmpty());
    check(ReaderNavigation.matchingParagraphs(visible, "---").isEmpty());
    check(ReaderNavigation.matchingParagraphs(visible, " ").isEmpty());
    int[] range = ReaderNavigation.ranges("ПМН пмн", "пмн").get(1);
    check(range[0] == 4 && range[1] == 7);
    check(CardFamilies.sameFamily("grenade-rgn", "grenade-rgo"));
    check(!CardFamilies.sameFamily("grenade-rgn", "grenade-rgn"));
    check(!CardFamilies.sameFamily("eng-pmn", "eng-mon-50"));
    check(CardFamilies.relatedIds("unknown").isEmpty());
    for (String id : args) System.out.println(id + "\t" + String.join(",",CardFamilies.relatedIds(id)));
  }
}
'''
        cards = json.loads((ROOT/'content/catalog.json').read_text())['cards']
        with tempfile.TemporaryDirectory() as directory:
            host = Path(directory)/'NavigationChecks.java'; host.write_text(source)
            files = [ROOT/f'app/src/main/java/ru/dlyasvoih/app/ui/content/{n}.java' for n in ('ReferenceBodyParser','ReaderContent','ReaderNavigation')]
            files += [ROOT/'app/src/main/java/ru/dlyasvoih/app/data/CardFamilies.java', host]
            compiled = subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-d',directory,*map(str,files)],capture_output=True,text=True,timeout=30)
            self.assertEqual(0, compiled.returncode, compiled.stderr)
            output = subprocess.run([java,'-cp',directory,'NavigationChecks',*[c['id'] for c in cards]],capture_output=True,text=True,timeout=30)
            self.assertEqual(0, output.returncode, output.stderr)
        families = {line.split('\t')[0]:line.split('\t')[1].split(',') if line.split('\t')[1] else [] for line in output.stdout.splitlines()}
        ids = set(families)
        for group in families.values(): self.assertTrue(set(group) <= ids)
        dao = (ROOT/'app/src/main/java/ru/dlyasvoih/app/data/local/GuideDao.kt').read_text()
        queries = re.findall(r'@Query\("""((?:(?!""").)*)"""\)\s*fun related(?:Cards|CardEntities)',dao,re.S)
        self.assertEqual(2,len(queries))
        with sqlite3.connect(ROOT/'app/src/main/assets/database/guide-v29.db') as db:
            for current in ('eng-pmn','ref-v8-tm-62p3','grenade-rgn','eng-pfm-1','eng-mon-50'):
                group = families[current]
                outputs = []
                for query in queries:
                    sql = query.replace(':familyIds',','.join('?' for _ in group) if group else 'NULL').replace(':id','?')
                    # Bind in SQL order, including repeated parameters.
                    params=[]
                    for match in re.finditer(r':id|:familyIds',query): params.extend([current] if match.group()==':id' else group)
                    rows = db.execute(sql,params).fetchall()
                    # Preview starts with id; CardEntity SELECT * starts with rowid.
                    outputs.append([r[0] if isinstance(r[0],str) else r[1] for r in rows])
                self.assertEqual(outputs[0],outputs[1])
                result=outputs[0]
                self.assertNotIn(current,result)
                self.assertEqual(len(result),len(set(result)))
                others=set(group)-{current}
                self.assertEqual(others,set(result[:len(others)]))

if __name__ == '__main__': unittest.main()
