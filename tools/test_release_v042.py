"""Local release checks for v0.3.117."""

from pathlib import Path
import json
import sqlite3
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseV043Test(unittest.TestCase):
    def test_version_and_build_scripts(self):
        gradle = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        self.assertIn('versionName = "0.3.117"', gradle)
        self.assertIn("versionCode = 121", gradle)
        self.assertIn("DLYA_SVOIH_v0.3.117-debug.apk", (ROOT / "MAKE_APK.bat").read_text(encoding="utf-8"))

    def test_only_production_database_is_packaged(self):
        database = ROOT / "app/src/main/assets/database"
        self.assertEqual(["guide-v29.db"], sorted(path.name for path in database.glob("*.db")))
        writer_version = int.from_bytes((database / "guide-v29.db").read_bytes()[96:100], "big")
        self.assertLessEqual(writer_version, 3045001)
        with sqlite3.connect(database / "guide-v29.db") as db:
            self.assertEqual(("ok",), db.execute("PRAGMA integrity_check").fetchone())
            self.assertEqual([], db.execute("PRAGMA foreign_key_check").fetchall())

    def test_catalog_and_database_are_synchronized(self):
        catalog = json.loads((ROOT / "content/catalog.json").read_text(encoding="utf-8"))
        with sqlite3.connect(ROOT / "app/src/main/assets/database/guide-v29.db") as db:
            self.assertEqual(len(catalog["cards"]), db.execute("SELECT COUNT(*) FROM cards").fetchone()[0])
            self.assertEqual(sum(len(card["images"]) for card in catalog["cards"]),
                db.execute("SELECT COUNT(*) FROM images").fetchone()[0])
            self.assertEqual(str(catalog["contentVersion"]),
                db.execute("SELECT value FROM metadata WHERE key='content_version'").fetchone()[0])

    def test_android_compatible_database_validation_is_used(self):
        updater = (ROOT / "app/src/main/java/ru/dlyasvoih/app/data/update/ContentUpdater.kt").read_text(encoding="utf-8")
        self.assertIn('output.fd.sync()', updater)
        self.assertNotIn('rawQuery("PRAGMA integrity_check"', updater)
        self.assertNotIn('rawQuery("PRAGMA quick_check', updater)
        self.assertIn('SELECT * FROM cards', updater)

    def test_requested_navigation_features_are_present(self):
        query = (ROOT / "app/src/main/java/ru/dlyasvoih/app/data/SearchQuery.kt").read_text(encoding="utf-8")
        navigation = (ROOT / "app/src/main/java/ru/dlyasvoih/app/DlyaSvoihApp.kt").read_text(encoding="utf-8")
        detail = (ROOT / "app/src/main/java/ru/dlyasvoih/app/ui/screens/DetailScreen.kt").read_text(encoding="utf-8")
        for marker in ("WITH_PHOTO", "WITHOUT_PHOTO", "CatalogStatus.VERIFIED", "JOIN reading history"):
            self.assertIn(marker, query)
        self.assertIn('HISTORY("history_tab", "Недавние"', navigation)
        self.assertIn("comparisonFacts", detail)
        self.assertIn("imageRightsLabel", detail)

    def test_no_emergency_call_feature_was_added(self):
        manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertNotIn("CALL_PHONE", manifest)
        sources = "\n".join(path.read_text(encoding="utf-8") for path in
            (ROOT / "app/src/main/java").rglob("*.kt"))
        self.assertNotIn("ACTION_CALL", sources)


if __name__ == "__main__":
    unittest.main()
