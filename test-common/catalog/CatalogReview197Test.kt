package ru.dlyasvoih.app

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import android.content.Context
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
import ru.dlyasvoih.app.ui.content.ReaderContent

/** CI supplies the exact public 196 database and the actual proposed release ZIP. */
@RunWith(AndroidJUnit4::class)
class CatalogReview197Test {
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private val fixtures = InstrumentationRegistry.getInstrumentation().context.assets
    private val name = "review197-upgrade.db"
    private lateinit var db: GuideDatabase
    private val changed = "handbookref-pni-1"
    private val corrected = "ordnance-v27-p3-jumping-pakistan"

    @Before fun setup() {
        context.deleteDatabase(name)
        val file = context.getDatabasePath(name)
        file.parentFile!!.mkdirs()
        fixtures.open("review197-baseline.db").use { input ->
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
        assertEquals("196", db.guideDao().metadata("content_version"))
        val previous = identities()
        assertEquals(1695, previous.size)
        val version = ContentUpdater(context, db).importPack(fixtures.open("review197-pack.zip"), 197L)
        assertEquals(197L, version)
        assertEquals("197", db.guideDao().metadata("content_version"))
        assertEquals(previous, identities())
        val source = db.guideDao().card(changed).first()!!
        assertEquals("source_only", source.contentStatus)
        assertTrue(source.body.contains("17 мая 2001 года"))
        val article = ReaderContent.article(source.body.split("\n\n"), false)
        assertTrue(article.any { it.contains("17 мая 2001 года") })
        assertFalse(article.any { it.contains("Обозначение в исходной таблице") })
        assertEquals(2, db.guideDao().sources(changed).first().size)
        assertTrue(db.guideDao().images(corrected).first().isEmpty())
        assertNull(db.guideDao().card(corrected).first()!!.thumbnailPath)
        db.openHelper.readableDatabase.query(
            "SELECT COUNT(*) FROM images i JOIN cards c ON c.id=i.cardId WHERE c.archived=0"
        ).use { rows -> assertTrue(rows.moveToFirst()); assertEquals(1595, rows.getInt(0)) }
        db.openHelper.readableDatabase.query("PRAGMA foreign_key_check").use { assertFalse(it.moveToFirst()) }
    }

    @Test fun favoritesReadingAndStableIdentitiesSurvivePackImportAndReopen() = runBlocking(Dispatchers.IO) {
        val dao = db.guideDao()
        for ((id, offset) in listOf(changed to 37, corrected to 19)) {
            dao.addFavorite(FavoriteEntity(id, 100))
            dao.saveReading(ReadingEntity(id, 1, offset, 200, 196))
        }
        importActualRelease()
        db.close()
        db = Room.databaseBuilder(context, GuideDatabase::class.java, name).build()
        ContentUpdater(context, db).initialize()
        for ((id, offset) in listOf(changed to 37, corrected to 19)) {
            assertTrue(db.guideDao().isFavorite(id).first())
            assertFalse(db.guideDao().card(id).first()!!.archived)
            assertEquals(offset, db.guideDao().reading(id)!!.offset)
        }
        assertTrue(db.guideDao().images(corrected).first().isEmpty())
    }

    @Test fun repeatedReleaseIsRejectedWithoutChangingInstalledContent() = runBlocking(Dispatchers.IO) {
        importActualRelease()
        val previous = identities()
        var rejected = false
        try {
            ContentUpdater(context, db).importPack(fixtures.open("review197-pack.zip"), 197L)
        } catch (expected: IllegalArgumentException) {
            rejected = true
        }
        assertTrue("Installing the same release twice must be rejected", rejected)
        assertEquals("197", db.guideDao().metadata("content_version"))
        assertEquals(previous, identities())
    }
}
