package ru.dlyasvoih.app

import android.content.Context
import android.graphics.BitmapFactory
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import ru.dlyasvoih.app.data.local.*
import ru.dlyasvoih.app.data.update.ContentUpdater

/** Imports the actual proposed ZIP over the unchanged public catalog 197. */
@RunWith(AndroidJUnit4::class)
class CatalogReview198Test {
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private val fixtures = InstrumentationRegistry.getInstrumentation().context.assets
    private val name = "review198-upgrade.db"
    private lateinit var db: GuideDatabase
    private val saved = listOf("eng-prb-m409" to 37, "grenade-f1-soviet" to 19)

    @Before fun setup() {
        context.deleteDatabase(name)
        val file = context.getDatabasePath(name)
        file.parentFile!!.mkdirs()
        fixtures.open("review198-baseline.db").use { input ->
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
        assertEquals("197", db.guideDao().metadata("content_version"))
        val previous = identities()
        assertEquals(1695, previous.size)
        val version = ContentUpdater(context, db).importPack(fixtures.open("review198-pack.zip"), 198L)
        assertEquals(198L, version)
        assertEquals("198", db.guideDao().metadata("content_version"))
        val current = identities()
        assertEquals(2855, current.size)
        previous.forEach { (id, row) -> assertEquals("Stable identity: $id", row, current[id]) }
        val dao = db.guideDao()
        val charge = dao.card("pdf198-school5-dm31-charge").first()!!
        assertEquals("charges", charge.categoryId)
        assertEquals("source_only", charge.contentStatus)
        assertEquals("B", charge.sourceGrade)
        assertNull(charge.verifiedAt)
        assertNotNull(dao.card("eng-dm-31-at").first())
        assertNotNull(dao.card("eng-pdf-v7-007").first())
        assertNotNull(dao.card("pdf198-school4-hl-sp-mi-4672").first())
        assertEquals("SVO", dao.card("pdf198-school5-fdg33").first()!!.section)
        val image = dao.images("eng-prb-m409").first().first()
        assertEquals(388, image.width)
        assertEquals(332, image.height)
        assertTrue(image.localPath.startsWith("packs/"))
        val actual = BitmapFactory.decodeFile(File(context.filesDir, image.localPath).path)
        assertNotNull(actual)
        actual!!.recycle()
        assertTrue(dao.images("ordnance-v27-rbk-500").first().isNotEmpty())
        val banner = dao.images("pdf198-8-ab3ec582c218").first().first()
        assertEquals(220, banner.height)
        assertTrue(banner.caption.length <= 600)
        db.openHelper.readableDatabase.query("SELECT COUNT(*) FROM images").use {
            assertTrue(it.moveToFirst()); assertEquals(2317, it.getInt(0))
        }
        db.openHelper.readableDatabase.query(
            "SELECT COUNT(*) FROM cards_fts WHERE cards_fts MATCH 'DM31' AND docid=${charge.rowId}"
        ).use { assertTrue(it.moveToFirst()); assertEquals(1, it.getInt(0)) }
        db.openHelper.readableDatabase.query("PRAGMA foreign_key_check").use { assertFalse(it.moveToFirst()) }
    }

    @Test fun favoritesReadingAndStableIdentitiesSurvivePackImportAndReopen() = runBlocking(Dispatchers.IO) {
        for ((id, offset) in saved) {
            db.guideDao().addFavorite(FavoriteEntity(id, 100))
            db.guideDao().saveReading(ReadingEntity(id, 1, offset, 200, 197))
        }
        importActualRelease()
        db.close()
        db = Room.databaseBuilder(context, GuideDatabase::class.java, name).build()
        ContentUpdater(context, db).initialize()
        for ((id, offset) in saved) {
            assertTrue(db.guideDao().isFavorite(id).first())
            assertFalse(db.guideDao().card(id).first()!!.archived)
            assertEquals(offset, db.guideDao().reading(id)!!.offset)
        }
        assertEquals(2855, identities().size)
    }

    @Test fun repeatedReleaseIsRejectedWithoutChangingInstalledContent() = runBlocking(Dispatchers.IO) {
        importActualRelease()
        val previous = identities()
        var rejected = false
        try {
            ContentUpdater(context, db).importPack(fixtures.open("review198-pack.zip"), 198L)
        } catch (expected: IllegalArgumentException) {
            rejected = true
        }
        assertTrue("Installing the same release twice must be rejected", rejected)
        assertEquals("198", db.guideDao().metadata("content_version"))
        assertEquals(previous, identities())
    }
}
