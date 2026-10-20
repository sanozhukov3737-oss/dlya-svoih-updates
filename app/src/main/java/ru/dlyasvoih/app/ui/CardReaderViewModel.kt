package ru.dlyasvoih.app.ui

import android.util.Log
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import ru.dlyasvoih.app.data.CatalogFilter
import ru.dlyasvoih.app.data.CatalogMenuLoad
import ru.dlyasvoih.app.data.CountrySelection
import ru.dlyasvoih.app.data.GuideRepository
import ru.dlyasvoih.app.data.MainSection
import ru.dlyasvoih.app.data.local.ReaderCard

sealed interface CardReaderState {
    data object Loading : CardReaderState
    data object Error : CardReaderState
    data class Ready(val ids: List<String>, val title: String, val country: String,
        val cards: List<ReaderCard>) : CardReaderState
}

class CardReaderViewModel(private val repo: GuideRepository, private val saved: SavedStateHandle) : ViewModel() {
    val filter = CatalogFilter(section = saved.get<String>("section").orEmpty(),
        category = saved.get<String>("category").orEmpty(), country = saved.get<String>("country").orEmpty(),
        query = saved.get<String>("query").orEmpty(), status = saved.get<String>("status").orEmpty(),
        photo = saved.get<String>("photo").orEmpty())
    val initialId = saved.get<String>("currentId") ?: saved.get<String>("id").orEmpty()
    private val mutableState = MutableStateFlow<CardReaderState>(CardReaderState.Loading)
    val state = mutableState.asStateFlow()
    private var running = false

    init { retry() }
    fun retry() {
        if (running) return
        running = true
        mutableState.value = CardReaderState.Loading
        viewModelScope.launch {
            try {
                // Snapshot IDs once. Reading/favorite writes must not reorder the book mid-swipe.
                // Bodies and images are loaded only by the visible page and nearby prefetch.
                val cards = repo.readerCards(filter)
                val ids = cards.map { it.id }
                val menus = (repo.menuData.value as? CatalogMenuLoad.Ready)?.value
                val categories = menus?.categoriesFor(filter.section) ?: repo.dao.categories(filter.section).first()
                val title = categories.firstOrNull { it.id == filter.category }?.title
                    ?: MainSection.fromId(filter.section)?.title ?: "Каталог"
                val country = when (filter.country) {
                    "" -> "Все страны / контексты"
                    CountrySelection.USSR_AND_RUSSIA -> "СССР / Россия"
                    else -> (menus?.countries ?: repo.dao.countries().first())
                        .firstOrNull { it.id == filter.country }?.name ?: filter.country
                }
                mutableState.value = CardReaderState.Ready(ids, title, country, cards)
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { Log.e("Guide", "Card reader load failed", e); mutableState.value = CardReaderState.Error }
            finally { running = false }
        }
    }

    fun rememberCard(id: String) { saved["currentId"] = id }
}
