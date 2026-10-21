package ru.dlyasvoih.app

import android.content.Context
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModelStore
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import ru.dlyasvoih.app.data.GuideRepository
import ru.dlyasvoih.app.data.local.CardEntity
import ru.dlyasvoih.app.data.local.CardPreview
import ru.dlyasvoih.app.data.local.CategoryEntity
import ru.dlyasvoih.app.data.local.GuideDatabase
import ru.dlyasvoih.app.data.local.MetadataEntity
import ru.dlyasvoih.app.ui.DataState
import ru.dlyasvoih.app.ui.DetailState
import ru.dlyasvoih.app.ui.DetailViewModel
import androidx.lifecycle.viewModelScope
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.Executor

@RunWith(AndroidJUnit4::class)
class LazyComparisonTest {
    @Test fun detailFavoritesAndReadingDoNotQueryComparisonUntilItIsOpened() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val queries = ConcurrentLinkedQueue<String>()
        val db = Room.inMemoryDatabaseBuilder(context, GuideDatabase::class.java)
            .setQueryCallback({ sql, _ -> queries.add(sql.replace(Regex("\\s+"), " ")) }, Executor { it.run() })
            .build()
        val store = ViewModelStore()
        var vm: DetailViewModel? = null
        fun comparisonQueries() = queries.count { it.contains("AND c.section = (SELECT section FROM cards WHERE id =") }
        fun card(row: Long, id: String) = CardEntity(row, id, "S1", "C1", id,
            "Краткое описание", "## Описание\n\nТекст карточки.", "", id, "", null, "reviewed", null)
        try {
            val dao = db.guideDao()
            dao.putCategories(listOf(CategoryEntity("C1", "S1", "Категория", 0)))
            dao.putMetadata(MetadataEntity("content_version", "197"))
            dao.putCard(card(1, "A")); dao.putCard(card(2, "B"))
            val repo = GuideRepository(db, context.getSharedPreferences("lazy-comparison-test", Context.MODE_PRIVATE))
            val detail = withContext(Dispatchers.Main) {
                DetailViewModel(repo, SavedStateHandle(mapOf("id" to "A"))).also { vm = it; store.put("detail", it) }
            }
            val ready = withTimeout(10_000) { detail.state.first { it is DetailState.Ready } } as DetailState.Ready
            assertEquals("A", ready.value.card!!.id)
            assertEquals(listOf("## Описание", "Текст карточки."), ready.paragraphs)
            assertEquals("Opening a detail must not issue the candidates SQL", 0, comparisonQueries())

            repo.toggleFavorite("A")
            withTimeout(10_000) { detail.state.first { it is DetailState.Ready && it.value.favorite } }
            withContext(Dispatchers.Main) { detail.position(2, 14); detail.flushReading() }
            withTimeout(10_000) { while (repo.reading("A")?.offset != 14) delay(20) }
            assertEquals("Favorite and reading writes must not load candidates", 0, comparisonQueries())

            val first = withTimeout(10_000) { detail.comparisonOptions.first { it is DataState.Ready } } as DataState.Ready<List<CardPreview>>
            assertEquals(listOf("B"), first.value.map { it.id })
            assertTrue("The open sheet must execute the real candidates SQL", comparisonQueries() > 0)
            // first() releases the sheet's subscription. Wait for the explicit replay reset.
            withTimeout(10_000) { while (detail.comparisonOptions.value != DataState.Loading) delay(10) }
            val closedCount = comparisonQueries()
            dao.putCard(card(3, "C"))
            // Await an actual detail update, rather than assume invalidation has run after a sleep.
            withTimeout(10_000) { detail.state.first { it is DetailState.Ready && it.value.related.any { c -> c.id == "C" } } }
            assertEquals("A closed sheet must not keep observing catalog changes", closedCount, comparisonQueries())
            val reopened = withTimeout(10_000) { detail.comparisonOptions.first { it is DataState.Ready } } as DataState.Ready<List<CardPreview>>
            assertEquals(listOf("B", "C"), reopened.value.map { it.id })
        } finally {
            withContext(Dispatchers.Main) { store.clear() }
            vm?.viewModelScope?.coroutineContext?.get(Job)?.join()
            db.close()
        }
    }
}
