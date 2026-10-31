package ru.dlyasvoih.app

import android.content.Context
import android.graphics.BitmapFactory
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.security.MessageDigest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import ru.dlyasvoih.app.data.local.*
import ru.dlyasvoih.app.data.update.ContentUpdater

/** Exercises the exact saved release ZIP through the production importer. */
@RunWith(AndroidJUnit4::class)
class CatalogReview199Test {
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private val fixtures = InstrumentationRegistry.getInstrumentation().context.assets
    private val name = "review199-upgrade.db"
    private lateinit var db: GuideDatabase
    private val saved = listOf("eng-prb-m409", "grenade-f1-soviet")

    @Before fun setup() {
        context.deleteDatabase(name)
        val file = context.getDatabasePath(name)
        file.parentFile!!.mkdirs()
        fixtures.open("review199-baseline.db").use { input -> file.outputStream().use { input.copyTo(it) } }
        db = Room.databaseBuilder(context, GuideDatabase::class.java, name).build()
    }
    @After fun cleanup() { db.close(); context.deleteDatabase(name) }

    private fun identities(): Map<String,Long> = db.openHelper.readableDatabase
        .query("SELECT id,rowid FROM cards WHERE archived=0").use { rows ->
            buildMap { while(rows.moveToNext()) put(rows.getString(0),rows.getLong(1)) }
        }

    private fun snapshot(): String {
        val hash = MessageDigest.getInstance("SHA-256")
        for (table in listOf("cards","images","sources","card_countries","metadata","favorites","reading")) {
            db.openHelper.readableDatabase.query("SELECT * FROM $table ORDER BY 1,2").use { rows ->
                while(rows.moveToNext()) for(column in 0 until rows.columnCount) {
                    val value = if(rows.isNull(column)) "<null>" else rows.getString(column)
                    hash.update(value.toByteArray()); hash.update(0.toByte())
                }
            }
        }
        return hash.digest().joinToString("") { "%02x".format(it) }
    }

    private suspend fun seedUserData() {
        for ((index,id) in saved.withIndex()) {
            db.guideDao().addFavorite(FavoriteEntity(id,100L+index))
            db.guideDao().saveReading(ReadingEntity(id,index+1,37+index,200L+index,198))
        }
    }

    private suspend fun assertUserData() {
        for ((index,id) in saved.withIndex()) {
            assertEquals(ReadingEntity(id,index+1,37+index,200L+index,198),db.guideDao().reading(id))
            assertTrue(db.guideDao().isFavorite(id).first())
            db.openHelper.readableDatabase.query("SELECT savedAt FROM favorites WHERE cardId=?",arrayOf(id)).use {
                assertTrue(it.moveToFirst()); assertEquals(100L+index,it.getLong(0))
            }
        }
    }

    private suspend fun importActual() {
        assertEquals("198",db.guideDao().metadata("content_version"))
        val before = identities()
        assertEquals(2855,before.size)
        assertEquals(199L,ContentUpdater(context,db).importPack(fixtures.open("review199-pack.zip"),199L))
        assertEquals("199",db.guideDao().metadata("content_version"))
        assertEquals(before,identities())
        for ((table,count) in listOf("cards" to 2855,"images" to 2403,"sources" to 6988)) {
            db.openHelper.readableDatabase.query("SELECT COUNT(*) FROM $table").use {
                assertTrue(it.moveToFirst()); assertEquals(count,it.getInt(0))
            }
        }
        val records = JSONObject(fixtures.open("review199-images.json").bufferedReader().use { it.readText() })
        val images = records.getJSONArray("newImages")
        assertEquals(86,images.length())
        val affected = mutableSetOf<String>()
        for (i in 0 until images.length()) {
            val expected = images.getJSONObject(i)
            val cardId = expected.getString("cardId")
            affected += cardId
            val image = db.guideDao().images(cardId).first().single { it.id == expected.getString("id") }
            assertTrue(image.localPath.startsWith("packs/"))
            assertTrue(image.localPath.endsWith("/"+expected.getString("localPath")))
            val bitmap = BitmapFactory.decodeFile(File(context.filesDir,image.localPath).path)
            assertNotNull("New image must decode: ${image.id}",bitmap)
            assertEquals(expected.getInt("width"),bitmap!!.width)
            assertEquals(expected.getInt("height"),bitmap.height)
            bitmap.recycle()
        }
        assertEquals(78,affected.size)
        val thumbnails = records.getJSONArray("changedThumbnails")
        for (i in 0 until thumbnails.length()) {
            val item = thumbnails.getJSONObject(i)
            val path = db.guideDao().card(item.getString("cardId")).first()!!.thumbnailPath!!
            assertTrue(path.startsWith("packs/")); assertTrue(path.endsWith("/"+item.getString("path")))
            val bitmap = BitmapFactory.decodeFile(File(context.filesDir,path).path)
            assertNotNull(bitmap); assertTrue(bitmap!!.width<=256 && bitmap.height<=256); bitmap.recycle()
        }
        db.openHelper.readableDatabase.query("PRAGMA foreign_key_check").use { assertFalse(it.moveToFirst()) }
    }

    @Test fun favoritesReadingAndStableIdentitiesSurvivePackImportAndReopen() = runBlocking(Dispatchers.IO) {
        seedUserData(); importActual()
        val expected = snapshot()
        db.close(); db = Room.databaseBuilder(context,GuideDatabase::class.java,name).build()
        ContentUpdater(context,db).initialize()
        assertUserData(); assertEquals(expected,snapshot())
    }

    @Test fun repeatedReleaseIsRejectedWithoutChangingInstalledContent() = runBlocking(Dispatchers.IO) {
        seedUserData(); importActual()
        val before = snapshot()
        var rejected = false
        try { ContentUpdater(context,db).importPack(fixtures.open("review199-pack.zip"),199L) }
        catch(expected: IllegalArgumentException) { rejected = true }
        assertTrue("Repeat installation must be rejected",rejected)
        assertUserData(); assertEquals(before,snapshot())
    }

    @Test fun mismatchedAnnouncedVersionIsRejectedWithoutChangingCatalog198() = runBlocking(Dispatchers.IO) {
        seedUserData()
        val before = snapshot()
        var rejected = false
        try { ContentUpdater(context,db).importPack(fixtures.open("review199-pack.zip"),200L) }
        catch(expected: IllegalArgumentException) { rejected = true }
        assertTrue("Mismatched announcement must be rejected",rejected)
        assertEquals("198",db.guideDao().metadata("content_version"))
        assertUserData(); assertEquals(before,snapshot())
    }
}
