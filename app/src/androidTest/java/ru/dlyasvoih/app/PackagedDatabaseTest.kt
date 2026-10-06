package ru.dlyasvoih.app

import android.content.Context
import androidx.room.Room
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModelStore
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith
import ru.dlyasvoih.app.data.*
import ru.dlyasvoih.app.data.local.*
import ru.dlyasvoih.app.data.update.ContentUpdater
import ru.dlyasvoih.app.ui.*

@RunWith(AndroidJUnit4::class)
class PackagedDatabaseTest {
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private lateinit var db: GuideDatabase
    private val name = "packaged-validation.db"
    private val prefsName = "migration-test"

    @Before fun setup() {
        context.deleteDatabase(name)
        context.getSharedPreferences(prefsName, Context.MODE_PRIVATE).edit().clear().commit()
        db = GuideDatabase.create(context, name)
    }
    @After fun cleanup() {
        db.close()
        context.deleteDatabase(name)
        context.getSharedPreferences(prefsName, Context.MODE_PRIVATE).edit().clear().commit()
    }

    @Test fun packagedSchemaIsAcceptedByRoomAndFtsFindsRussianBodyText() = runBlocking(Dispatchers.IO) {
        // Opening this asset executes Room's generated schema validation, including FTS options.
        assertEquals("148", db.guideDao().metadata("content_version"))
        db.openHelper.readableDatabase.query("SELECT COUNT(*) FROM cards").use { cursor ->
            assertTrue(cursor.moveToFirst())
            assertEquals(1293L, cursor.getLong(0))
        }
        assertNotNull(db.guideDao().card("first-aid-burn").first())
        val request = CatalogQuery.build(CatalogFilter(query = "проточной"))
        db.openHelper.readableDatabase.query(request.sql, request.args.toTypedArray()).use { cursor ->
            val foundIds = buildSet {
                while (cursor.moveToNext()) add(cursor.getString(cursor.getColumnIndexOrThrow("id")))
            }
            assertTrue(foundIds.contains("first-aid-burn"))
        }
        assertEquals(53, db.guideDao().countries().first().size)
        assertEquals(2, db.guideDao().images("ammo-reference-scope").first().size)
    }

    @Test fun importedFavoritesSurviveReopenAndDoNotReappearAfterRemoval() = runBlocking(Dispatchers.IO) {
        val prefs = context.getSharedPreferences(prefsName, Context.MODE_PRIVATE)
        prefs.edit().putStringSet("favorites", setOf("first-aid-burn", "missing-id")).commit()
        var repo = GuideRepository(db, prefs)
        repo.initialize()
        assertTrue(db.guideDao().isFavorite("first-aid-burn").first())
        repo.toggleFavorite("first-aid-burn")
        db.close()
        db = GuideDatabase.create(context, name)
        repo = GuideRepository(db, prefs)
        repo.initialize()
        assertFalse(db.guideDao().isFavorite("first-aid-burn").first())
        assertEquals("1", db.guideDao().metadata("legacy_favorites_imported"))
        assertTrue(prefs.getStringSet("favorites", emptySet())!!.contains("first-aid-burn"))
    }

    @Test fun bundledCatalogUpdatePassesValidationAndPreservesUserData() = runBlocking(Dispatchers.IO) {
        val bundledVersion = context.assets.open("database/content-version.txt").bufferedReader().use { it.readText().trim().toLong() }
        val previousVersion = bundledVersion - 1
        db.guideDao().putMetadata(MetadataEntity("content_version", previousVersion.toString()))
        db.guideDao().addFavorite(FavoriteEntity("first-aid-burn", 100))
        db.guideDao().saveReading(ReadingEntity("first-aid-burn", 2, 33, 200, previousVersion))

        ContentUpdater(context, db).initialize()

        assertEquals(bundledVersion.toString(), db.guideDao().metadata("content_version"))
        assertTrue(db.guideDao().isFavorite("first-aid-burn").first())
        assertEquals(33, db.guideDao().reading("first-aid-burn")!!.offset)
        db.openHelper.readableDatabase.query("SELECT COUNT(*) FROM images WHERE position NOT BETWEEN 0 AND 11").use { cursor ->
            assertTrue(cursor.moveToFirst())
            assertEquals(0L, cursor.getLong(0))
        }
    }

    @Test fun freshRoomSchemaAndPackagedSchemaHaveMatchingColumns() = runBlocking(Dispatchers.IO) {
        val fresh = Room.inMemoryDatabaseBuilder(context, GuideDatabase::class.java).build()
        try {
            fresh.guideDao().metadata("open")
            db.guideDao().metadata("open")
            for (table in listOf("countries", "categories", "cards", "card_countries", "images", "sources", "favorites", "metadata", "reading")) {
                fun info(database: GuideDatabase): List<List<String?>> = database.openHelper.readableDatabase
                    .query("PRAGMA table_info(`$table`)").use { cursor ->
                        buildList { while (cursor.moveToNext()) add((1 until cursor.columnCount).map { cursor.getString(it) }) }
                    }
                assertEquals(table, info(fresh), info(db))
            }
        } finally { fresh.close() }
    }

    private fun expectedIds(sql: String, vararg args: Any): List<String> =
        db.openHelper.readableDatabase.query(sql, arrayOf(*args)).use { cursor ->
            buildList { while (cursor.moveToNext()) add(cursor.getString(0)) }
        }

    @Test fun newMenuScreensStartWithCachedDataWithoutAQueryLoadingState() = runBlocking(Dispatchers.IO) {
        val repo = GuideRepository(db, context.getSharedPreferences(prefsName, Context.MODE_PRIVATE))
        repo.initialize()
        val snapshot = (repo.menuData.value as CatalogMenuLoad.Ready).value
        withContext(Dispatchers.Main) {
            val store = ViewModelStore()
            try {
                for (category in snapshot.categories) {
                    val overview = OverviewViewModel(repo, category.section)
                    store.put("overview:${category.id}", overview)
                    assertFalse(overview.state.value.loading)
                    val args = mapOf("section" to category.section, "category" to category.id)
                    val countries = CountryMenuViewModel(repo, SavedStateHandle(args))
                    store.put("countries:${category.id}", countries)
                    assertFalse(countries.state.value.loading)
                    assertEquals(snapshot.categoryCounts[category.id] ?: 0, countries.state.value.total)
                    val list = CatalogViewModel(repo, SavedStateHandle(args), CatalogMode.CATALOG)
                    store.put("list:${category.id}", list)
                    assertTrue(list.options.value is DataState.Ready)
                }
            } finally { store.clear() }
        }
    }

    @Test fun sharedMenuCacheRefreshesAfterCatalogChanges() = runBlocking(Dispatchers.IO) {
        val repo = GuideRepository(db, context.getSharedPreferences(prefsName, Context.MODE_PRIVATE))
        repo.initialize()
        val before = (repo.menuData.value as CatalogMenuLoad.Ready).value
        val card = db.guideDao().card("first-aid-burn").first()!!
        db.guideDao().putCard(card.copy(archived = true))
        val expectedCountries = db.guideDao().countryChoices(card.section, card.categoryId).first()
        val after = withTimeout(5_000) {
            repo.menuData.first { load -> load is CatalogMenuLoad.Ready &&
                load.value.total(card.section, card.categoryId) == before.total(card.section, card.categoryId) - 1 &&
                load.value.countryChoices(card.section, card.categoryId) == expectedCountries }
        } as CatalogMenuLoad.Ready
        assertEquals(expectedCountries, after.value.countryChoices(card.section, card.categoryId))
        db.guideDao().putMetadata(MetadataEntity("content_version", "148"))
        withTimeout(5_000) {
            repo.menuData.first { it is CatalogMenuLoad.Ready && it.value.contentVersion == "148" }
        }
    }

    @Test fun readerContainsTheWholeCatalogBeyondThePagingWindow() = runBlocking(Dispatchers.IO) {
        val repo = GuideRepository(db, context.getSharedPreferences(prefsName, Context.MODE_PRIVATE))
        val ids = repo.cardIds(CatalogFilter())
        assertTrue(ids.size > 180)
        assertEquals(expectedIds("SELECT id FROM cards WHERE archived=0 ORDER BY sortTitle,rowid"), ids)
        val titles = repo.readerCards(CatalogFilter())
        assertEquals(ids, titles.map { it.id })
        assertTrue(titles.all { it.title.isNotBlank() })
    }

    @Test fun readerRespectsCategoryAndCountryWithoutDuplicateCards() = runBlocking(Dispatchers.IO) {
        val repo = GuideRepository(db, context.getSharedPreferences(prefsName, Context.MODE_PRIVATE))
        val filter = CatalogFilter(section = "AMMUNITION", category = "mines-antipersonnel")
        val all = repo.cardIds(filter)
        assertTrue(all.isNotEmpty())
        assertEquals(expectedIds("SELECT id FROM cards WHERE archived=0 AND section='AMMUNITION' AND categoryId='mines-antipersonnel' ORDER BY sortTitle,rowid"), all)
        for (country in listOf("ru", CountrySelection.USSR_AND_RUSSIA)) {
            val selected = repo.cardIds(filter.copy(country = country))
            val countries = if (country == "ru") "countryId='ru'" else "countryId IN ('ru','su')"
            assertEquals(expectedIds("SELECT id FROM cards c WHERE archived=0 AND section='AMMUNITION' AND categoryId='mines-antipersonnel' AND EXISTS (SELECT 1 FROM card_countries cc WHERE cc.cardId=c.id AND $countries) ORDER BY sortTitle,rowid"), selected)
            assertEquals(selected.size, selected.toSet().size)
            assertTrue(all.containsAll(selected))
        }
        assertTrue(repo.cardIds(filter.copy(country = "country-does-not-exist")).isEmpty())
    }

    @Test fun readerPhotoFiltersPartitionTheSelectedCategory() = runBlocking(Dispatchers.IO) {
        val repo = GuideRepository(db, context.getSharedPreferences(prefsName, Context.MODE_PRIVATE))
        val filter = CatalogFilter(section = "AMMUNITION", category = "mines-antipersonnel")
        val all = repo.cardIds(filter).toSet()
        val withPhoto = repo.cardIds(filter.copy(photo = PhotoSelection.WITH_PHOTO)).toSet()
        val withoutPhoto = repo.cardIds(filter.copy(photo = PhotoSelection.WITHOUT_PHOTO)).toSet()
        assertTrue(withPhoto.intersect(withoutPhoto).isEmpty())
        assertEquals(all, withPhoto + withoutPhoto)
    }
}
