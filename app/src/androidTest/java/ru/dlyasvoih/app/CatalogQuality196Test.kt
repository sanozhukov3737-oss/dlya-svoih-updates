package ru.dlyasvoih.app

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.Assert.*
import org.junit.runner.RunWith
import ru.dlyasvoih.app.data.local.*
import ru.dlyasvoih.app.data.update.ContentUpdater

/** The CI fixtures are the exact public 195 database and the actual release ZIP. */
@RunWith(AndroidJUnit4::class)
class CatalogQuality196Test {
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private val fixtures = InstrumentationRegistry.getInstrumentation().context.assets
    private val name = "quality196-upgrade.db"
    private lateinit var db: GuideDatabase
    private val withdrawn = "pptx-v166-tm-124"
    private val duplicateM430 = "ordnance-v27-m430a1-hedp"
    private val canonical = "eng-pdf-v7-119"

    @Before fun setup() {
        context.deleteDatabase(name)
        val file = context.getDatabasePath(name)
        file.parentFile!!.mkdirs()
        fixtures.open("quality196-baseline.db").use { input ->
            file.outputStream().use { input.copyTo(it) }
        }
        db = Room.databaseBuilder(context, GuideDatabase::class.java, name).build()
    }

    @After fun cleanup() {
        db.close()
        context.deleteDatabase(name)
    }

    private fun identities(): Map<String, Long> = db.openHelper.readableDatabase
        .query("SELECT id,rowid FROM cards WHERE archived=0").use { rows ->
            buildMap { while (rows.moveToNext()) put(rows.getString(0), rows.getLong(1)) }
        }

    private suspend fun importActualRelease() {
        assertEquals("195", db.guideDao().metadata("content_version"))
        val previous = identities()
        assertEquals(1697, previous.size)
        val version = ContentUpdater(context, db).importPack(fixtures.open("quality196-pack.zip"), 196L)
        assertEquals(196L, version)
        assertEquals("196", db.guideDao().metadata("content_version"))
        assertEquals(previous - setOf(withdrawn, duplicateM430), identities())
        assertEquals(2, db.guideDao().images(canonical).first().size)
        assertTrue(db.guideDao().images(canonical).first().any { it.id == "quality196-tm124-presentation" })
        db.openHelper.readableDatabase.query(
            "SELECT COUNT(*) FROM images i JOIN cards c ON c.id=i.cardId WHERE c.archived=0"
        ).use { rows -> assertTrue(rows.moveToFirst()); assertEquals(1596, rows.getInt(0)) }
        db.openHelper.readableDatabase.query("PRAGMA foreign_key_check").use { assertFalse(it.moveToFirst()) }
        val picture = db.guideDao().images("ordnance-v29-ga-0289").first().single()
        assertTrue(picture.localPath.endsWith("/images/quality196-tm28-448.webp"))
    }

    @Test fun savedWithdrawnCardAndReadingSurviveRealPackImportAndReopen() = runBlocking(Dispatchers.IO) {
        val dao = db.guideDao()
        dao.addFavorite(FavoriteEntity(withdrawn, 100))
        dao.saveReading(ReadingEntity(withdrawn, 2, 33, 200, 195))
        dao.addFavorite(FavoriteEntity(duplicateM430, 102))
        dao.saveReading(ReadingEntity(duplicateM430, 2, 29, 202, 195))
        dao.addFavorite(FavoriteEntity(canonical, 101))
        dao.saveReading(ReadingEntity(canonical, 1, 17, 201, 195))
        importActualRelease()
        db.close()
        db = Room.databaseBuilder(context, GuideDatabase::class.java, name).build()
        ContentUpdater(context, db).initialize()
        assertTrue(db.guideDao().isFavorite(withdrawn).first())
        assertTrue(db.guideDao().card(withdrawn).first()!!.archived)
        assertEquals(33, db.guideDao().reading(withdrawn)!!.offset)
        assertEquals(1, db.guideDao().images(withdrawn).first().size)
        assertTrue(db.guideDao().isFavorite(duplicateM430).first())
        assertTrue(db.guideDao().card(duplicateM430).first()!!.archived)
        assertEquals(29, db.guideDao().reading(duplicateM430)!!.offset)
        assertTrue(db.guideDao().isFavorite(canonical).first())
        assertEquals(17, db.guideDao().reading(canonical)!!.offset)
        assertFalse(db.guideDao().card(canonical).first()!!.archived)
    }

    @Test fun unsavedDuplicateIsPrunedByRealPackImporter() = runBlocking(Dispatchers.IO) {
        importActualRelease()
        assertNull(db.guideDao().card(withdrawn).first())
        assertTrue(db.guideDao().images(withdrawn).first().isEmpty())
        assertNull(db.guideDao().card(duplicateM430).first())
    }
}
