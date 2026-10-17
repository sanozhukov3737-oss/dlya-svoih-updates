package ru.dlyasvoih.app

import android.content.Context
import androidx.paging.PagingSource
import androidx.sqlite.db.SimpleSQLiteQuery
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.Assert.*
import ru.dlyasvoih.app.data.*
import ru.dlyasvoih.app.data.local.*

class SearchRegressionTest {
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private val databaseName = "search-regression.db"
    private val preferencesName = "search-regression"
    private lateinit var db: GuideDatabase
    private val target = "ref-v8-tm-46"

    @Before fun setup() {
        context.deleteDatabase(databaseName)
        context.getSharedPreferences(preferencesName, Context.MODE_PRIVATE).edit().clear().commit()
        db = GuideDatabase.create(context, databaseName)
    }
    @After fun cleanup() {
        db.close()
        context.deleteDatabase(databaseName)
        context.getSharedPreferences(preferencesName, Context.MODE_PRIVATE).edit().clear().commit()
    }
    private fun ids(filter: CatalogFilter): List<String> {
        val request = CatalogQuery.ids(filter)
        return db.openHelper.readableDatabase.query(request.sql, request.args.toTypedArray()).use { cursor ->
            buildList { while (cursor.moveToNext()) add(cursor.getString(0)) }
        }
    }
    @Test fun modelNamesWithEitherAlphabetAndMissingHyphensComeFirst() = runBlocking(Dispatchers.IO) {
        for (query in listOf("ТМ-46", "ТМ46", "TM-46", "TM46", "тм 46", "ТM‑46", "ТМ–46")) {
            assertEquals(query, target, ids(CatalogFilter(query = query)).firstOrNull())
        }
    }
    @Test fun numberQueryPutsTheActualModelAheadOfBodyMentions() = runBlocking(Dispatchers.IO) {
        assertEquals(target, ids(CatalogFilter(query = "46")).firstOrNull())
        val expected = ids(CatalogFilter(query = "46", category = "mines-antitank"))
        assertEquals(target, expected.firstOrNull())
        assertFalse(ids(CatalogFilter(query = "46", section = "ATGM")).contains(target))
        assertFalse(ids(CatalogFilter(query = "46", country = "us")).contains(target))
    }
    @Test fun numericTermsDoNotMatchDifferentModelNumbers() = runBlocking(Dispatchers.IO) {
        val original = db.guideDao().card(target).first()!!
        db.guideDao().putCard(original.copy(rowId = 2_000_001, id = "search-probe-460", title = "Probe-460",
            summary = "probe", body = "probe", tags = "", sortTitle = "probe-460", searchText = "probe 460"))
        assertFalse(ids(CatalogFilter(query = "46")).contains("search-probe-460"))
        assertTrue(ids(CatalogFilter(query = "460")).contains("search-probe-460"))
    }
    @Test fun titleFallbackAndBodySearchWorkWhenAnFtsEntryIsMissing() = runBlocking(Dispatchers.IO) {
        val row = db.guideDao().rowForId(target)!!
        db.openHelper.writableDatabase.execSQL("DELETE FROM cards_fts WHERE docid = ?", arrayOf(row))
        assertEquals(target, ids(CatalogFilter(query = "TM46")).firstOrNull())
        assertTrue(ids(CatalogFilter(query = "проточной")).contains("first-aid-burn"))
    }
    @Test fun existingInstallRepairsItsIndexWithoutReplacingSavedData() = runBlocking(Dispatchers.IO) {
        val dao = db.guideDao()
        val version = dao.metadata("content_version")!!
        val row = dao.rowForId(target)!!
        dao.addFavorite(FavoriteEntity(target, 120))
        dao.saveReading(ReadingEntity(target, 2, 37, 150, version.toLong()))
        db.openHelper.writableDatabase.execSQL("DELETE FROM cards_fts WHERE docid = ?", arrayOf(row))
        val expression = SearchQuery.match("ТМ-46")!!
        fun indexed() = db.openHelper.readableDatabase.query(
            "SELECT rowid FROM cards_fts WHERE cards_fts MATCH ? AND rowid = ?", arrayOf(expression, row)).use { it.moveToFirst() }
        assertFalse(indexed())
        val repo = GuideRepository(db, context.getSharedPreferences(preferencesName, Context.MODE_PRIVATE))
        repo.initialize()
        assertTrue(indexed())
        assertTrue(dao.isFavorite(target).first())
        assertEquals(37, dao.reading(target)!!.offset)
        assertEquals(version, dao.metadata("content_version"))
        assertEquals(target, ids(CatalogFilter(query = "46", favoritesOnly = true)).firstOrNull())
    }
    @Test fun firstPageAndBookUseTheSameRelevantOrder() = runBlocking(Dispatchers.IO) {
        val filter = CatalogFilter(query = "46")
        val expected = ids(filter)
        val request = CatalogQuery.build(filter)
        val page = db.guideDao().page(SimpleSQLiteQuery(request.sql, request.args.toTypedArray()))
            .load(PagingSource.LoadParams.Refresh(key = null, loadSize = 30, placeholdersEnabled = false))
        assertTrue(page.toString(), page is PagingSource.LoadResult.Page)
        if (page !is PagingSource.LoadResult.Page) error("Paging failed: $page")
        val firstPage = page.data
        assertEquals(target, firstPage.firstOrNull()?.id)
        assertEquals(expected.take(firstPage.size), firstPage.map { it.id })
    }
}
