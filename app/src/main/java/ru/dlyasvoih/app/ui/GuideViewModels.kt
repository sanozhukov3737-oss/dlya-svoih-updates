package ru.dlyasvoih.app.ui

import android.util.Log
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.paging.PagingData
import androidx.paging.cachedIn
import androidx.paging.map
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import ru.dlyasvoih.app.data.*
import ru.dlyasvoih.app.data.local.*

sealed interface BootState {
    data object Loading : BootState
    data object Ready : BootState
    data class Error(val detail: String) : BootState
}
class BootstrapViewModel(private val repo: GuideRepository) : ViewModel() {
    private val mutableState = MutableStateFlow<BootState>(BootState.Loading)
    val state = mutableState.asStateFlow()
    private var running = false
    init { retry() }
    fun retry() {
        if (running) return
        running = true
        mutableState.value = BootState.Loading
        viewModelScope.launch {
            try { repo.initialize(); mutableState.value = BootState.Ready }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                Log.e("Guide", "Database initialization failed", e)
                val cause = generateSequence(e as Throwable) { it.cause }.last()
                mutableState.value = BootState.Error("${cause.javaClass.simpleName}: ${cause.message.orEmpty()}".take(400))
            }
            finally { running = false }
        }
    }
}

sealed interface DataState<out T> {
    data object Loading : DataState<Nothing>
    data object Error : DataState<Nothing>
    data class Ready<T>(val value: T) : DataState<T>
}
private fun <T> Flow<T>.asDataState(label: String, loading: Boolean = true): Flow<DataState<T>> = map<T, DataState<T>> { DataState.Ready(it) }
    .onStart { if (loading) emit(DataState.Loading) }
    .catch { e ->
        if (e is CancellationException) throw e
        Log.e("Guide", label, e)
        emit(DataState.Error)
    }

data class OverviewState(val loading: Boolean = true, val error: Boolean = false,
    val counts: Map<String, Int> = emptyMap(), val categoryCounts: Map<String, Int> = emptyMap(), val categories: List<CategoryEntity> = emptyList(),
    val favoriteCards: List<CardPreview> = emptyList(), val contentVersion: String = "")
@OptIn(ExperimentalCoroutinesApi::class)
class OverviewViewModel(private val repo: GuideRepository, private val section: String) : ViewModel() {
    val remoteUpdates = repo.remoteUpdateState
    val appUpdates = repo.appUpdater?.state ?: MutableStateFlow<ru.dlyasvoih.app.data.update.AppUpdateState>(ru.dlyasvoih.app.data.update.AppUpdateState.Idle)
    private fun menuState(load: CatalogMenuLoad): OverviewState = when (load) {
        CatalogMenuLoad.Loading -> OverviewState()
        CatalogMenuLoad.Error -> OverviewState(loading = false, error = true)
        is CatalogMenuLoad.Ready -> OverviewState(loading = false,
            counts = load.value.sectionCounts, categoryCounts = load.value.categoryCounts,
            categories = load.value.categoriesFor(section).filter { CatalogHierarchy.isVisibleCategory(it.id) },
            contentVersion = load.value.contentVersion)
    }
    private val favorites = if (section.isEmpty()) repo.dao.favoritePreviews()
        .onStart { emit(emptyList()) }.catch { e ->
            if (e is CancellationException) throw e
            Log.e("Guide", "Favorite previews query failed", e)
            emit(emptyList())
        } else flowOf(emptyList<CardPreview>())
    val state = combine(repo.menuData, favorites) { menus, cards ->
        menuState(menus).copy(favoriteCards = cards)
    }.stateIn(viewModelScope, SharingStarted.Eagerly, menuState(repo.menuData.value))
    fun retry() { repo.retryMenus() }
}

data class CountryMenuState(val loading: Boolean = true, val error: Boolean = false,
    val title: String = "", val total: Int = 0, val countries: List<CountryCount> = emptyList())

@OptIn(ExperimentalCoroutinesApi::class)
class CountryMenuViewModel(private val repo: GuideRepository, saved: SavedStateHandle) : ViewModel() {
    val section = saved.get<String>("section").orEmpty()
    val category = saved.get<String>("category").orEmpty()
    private fun menuState(load: CatalogMenuLoad): CountryMenuState = when (load) {
        CatalogMenuLoad.Loading -> CountryMenuState()
        CatalogMenuLoad.Error -> CountryMenuState(loading = false, error = true)
        is CatalogMenuLoad.Ready -> CountryMenuState(loading = false,
                title = load.value.categoriesFor(section).firstOrNull { it.id == category }?.title
                    ?: MainSection.fromId(section)?.title ?: "Каталог",
                total = load.value.total(section, category), countries = load.value.countryChoices(section, category))
    }
    val state = repo.menuData.map(::menuState)
        .stateIn(viewModelScope, SharingStarted.Eagerly, menuState(repo.menuData.value))
    fun retry() { repo.retryMenus() }
}

enum class CatalogMode { CATALOG, SEARCH, FAVORITES, HISTORY }
data class FilterKey(val search: String, val country: String, val category: String,
    val status: String, val photo: String)
data class ListedCard(val card: CardPreview, val key: FilterKey)
data class FavoriteStatuses(val selected: Set<String>, val knownIds: Set<String>)
data class FilterOptions(val countries: List<CountryCount>, val categories: List<CategoryEntity>)

@OptIn(ExperimentalCoroutinesApi::class, FlowPreview::class)
class CatalogViewModel(private val repo: GuideRepository, private val saved: SavedStateHandle,
    val mode: CatalogMode) : ViewModel() {
    val section = saved.get<String>("section").orEmpty()
    val category = saved.get<String>("category").orEmpty()
    val query = saved.getStateFlow("query", "")
    val country = saved.getStateFlow("country", "")
    val selectedCategory = saved.getStateFlow("selectedCategory", category)
    val status = saved.getStateFlow("status", "")
    val photo = saved.getStateFlow("photo", "")
    private val reload = MutableStateFlow(0)
    private fun menuOptions(load: CatalogMenuLoad, selected: String): DataState<FilterOptions> = when (load) {
        CatalogMenuLoad.Loading -> DataState.Loading
        CatalogMenuLoad.Error -> DataState.Error
        is CatalogMenuLoad.Ready -> DataState.Ready(FilterOptions(load.value.countryChoices(section, selected),
            load.value.categoriesFor(section).filter { CatalogHierarchy.isVisibleCategory(it.id) }))
    }
    val options = combine(selectedCategory, reload) { selected, _ -> selected }.flatMapLatest { selected ->
        if (mode == CatalogMode.CATALOG || mode == CatalogMode.SEARCH) {
            repo.menuData.map { menuOptions(it, selected) }
        } else combine(repo.dao.countryChoices(section, selected, mode == CatalogMode.FAVORITES, mode == CatalogMode.HISTORY),
            repo.dao.categories(section).map { categories -> categories.filter { CatalogHierarchy.isVisibleCategory(it.id) } },
            ::FilterOptions).asDataState("Filter query failed")
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000),
        if (mode == CatalogMode.CATALOG || mode == CatalogMode.SEARCH) menuOptions(repo.menuData.value, selectedCategory.value)
        else DataState.Loading)
    private val mutableError = MutableStateFlow<String?>(null)
    val error = mutableError.asStateFlow()
    private val mutablePending = MutableStateFlow<Set<String>>(emptySet())
    val pending = mutablePending.asStateFlow()
    private val visibleIds = MutableStateFlow<List<String>>(emptyList())
    val favorites = combine(visibleIds, reload) { ids, _ -> ids }.flatMapLatest { ids ->
        (if (ids.isEmpty()) flowOf(emptyList()) else repo.dao.favoritesFor(ids))
            .map { FavoriteStatuses(it.toSet(), ids.toSet()) }.asDataState("Favorite status query failed", loading = false)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), DataState.Loading)
    private val mutableApplied = MutableStateFlow<FilterKey?>(null)
    val applied = mutableApplied.asStateFlow()

    private val filters = combine(query, country, selectedCategory, status, photo) { text, selectedCountry, selected, selectedStatus, selectedPhoto ->
        CatalogFilter(section = section, category = selected, country = selectedCountry, query = text,
            favoritesOnly = mode == CatalogMode.FAVORITES, historyOnly = mode == CatalogMode.HISTORY,
            status = selectedStatus, photo = selectedPhoto)
    }.distinctUntilChangedBy { FilterKey(SearchQuery.key(it.query), it.country, it.category, it.status, it.photo) }

    val pages = filters.flatMapLatest { filter ->
        flow {
            if (mode == CatalogMode.SEARCH && filter.query.isNotBlank()) delay(180)
            val key = FilterKey(SearchQuery.key(filter.query), filter.country, filter.category, filter.status, filter.photo)
            mutableApplied.value = key
            val source = if (mode == CatalogMode.SEARCH && SearchQuery.match(filter.query) == null)
                flowOf(PagingData.empty<CardPreview>()) else repo.cards(filter)
            emitAll(source.map { paging -> paging.map { ListedCard(it, key) } })
        }
    }.cachedIn(viewModelScope)

    // At most 180 IDs from the bounded Paging window. One query, not one per row.
    fun observeFavorites(ids: List<String>) { visibleIds.value = ids.distinct().take(180).sorted() }
    fun retryOptions() { repo.retryMenus(); reload.value++ }
    fun currentFilter() = CatalogFilter(section = section, category = selectedCategory.value,
        country = country.value, query = query.value, status = status.value, photo = photo.value,
        favoritesOnly = mode == CatalogMode.FAVORITES, historyOnly = mode == CatalogMode.HISTORY)
    fun setQuery(value: String) { saved["query"] = value.take(SearchQuery.MAX_LENGTH) }
    fun setCountry(value: String) { saved["country"] = value }
    fun setCategory(value: String) { if (category.isEmpty()) saved["selectedCategory"] = value }
    fun setStatus(value: String) { saved["status"] = value }
    fun setPhoto(value: String) { saved["photo"] = value }
    fun clearFilters() {
        saved["country"] = ""
        if (category.isEmpty()) saved["selectedCategory"] = ""
        saved["status"] = ""
        saved["photo"] = ""
    }
    fun clearError() { mutableError.value = null }
    fun toggleFavorite(id: String) {
        if (id in mutablePending.value) return
        mutablePending.value += id
        viewModelScope.launch {
            try { repo.toggleFavorite(id) }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { Log.e("Guide", "Favorite save failed", e); mutableError.value = "Не удалось сохранить избранное. Попробуйте ещё раз." }
            finally { mutablePending.value -= id }
        }
    }
}

sealed interface DetailState {
    data object Loading : DetailState
    data object Missing : DetailState
    data object Error : DetailState
    data class Ready(val value: CardDetails, val paragraphs: List<String>, val reading: ReadingEntity?) : DetailState
}
@OptIn(ExperimentalCoroutinesApi::class)
class DetailViewModel(private val repo: GuideRepository, saved: SavedStateHandle) : ViewModel() {
    val id = saved.get<String>("id").orEmpty()
    private val reload = MutableStateFlow(0)
    private val mutableError = MutableStateFlow<String?>(null)
    val error = mutableError.asStateFlow()
    private val mutableBusy = MutableStateFlow(false)
    val busy = mutableBusy.asStateFlow()
    @Volatile private var displayedVersion = 0L
    private var latestPosition: Pair<Int, Int>? = null
    val state = reload.flatMapLatest {
        flow {
            emit(DetailState.Loading)
            displayedVersion = repo.contentVersion()
            val reading = repo.reading(id)
            var lastBody: String? = null
            var paragraphs = emptyList<String>()
            emitAll(repo.detail(id).map<CardDetails, DetailState> { value ->
                if (value.card == null) DetailState.Missing else {
                    if (lastBody != value.card.body) { lastBody = value.card.body; paragraphs = value.card.body.split("\n\n") }
                    DetailState.Ready(value, paragraphs, reading)
                }
            })
        }.flowOn(Dispatchers.Default).catch { e ->
            if (e is CancellationException) throw e
            Log.e("Guide", "Detail query failed", e); emit(DetailState.Error)
        }
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), DetailState.Loading)
    fun retry() { reload.value++ }
    fun clearError() { mutableError.value = null }
    fun position(index: Int, offset: Int) { latestPosition = index to offset; repo.scheduleReading(id, index, offset, displayedVersion) }
    fun flushReading() { latestPosition?.let { repo.scheduleReading(id, it.first, it.second, displayedVersion, immediate = true) } }
    fun toggleFavorite() {
        if (mutableBusy.value) return
        mutableBusy.value = true
        viewModelScope.launch {
            try { repo.toggleFavorite(id) }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { Log.e("Guide", "Favorite save failed", e); mutableError.value = "Не удалось сохранить избранное. Попробуйте ещё раз." }
            finally { mutableBusy.value = false }
        }
    }
}

@OptIn(ExperimentalCoroutinesApi::class)
class GalleryViewModel(repo: GuideRepository, saved: SavedStateHandle) : ViewModel() {
    private val id = saved.get<String>("id").orEmpty()
    private val reload = MutableStateFlow(0)
    val state = reload.flatMapLatest { repo.dao.images(id).asDataState("Gallery query failed") }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), DataState.Loading)
    fun retry() { reload.value++ }
}

sealed interface BackupState {
    data object Idle : BackupState
    data object Preparing : BackupState
    data class Ready(val text: String, val favorites: Int, val reading: Int) : BackupState
    data class Restored(val result: SavedCardsImportResult) : BackupState
    data class Error(val message: String) : BackupState
}
class BackupViewModel(private val repo: GuideRepository) : ViewModel() {
    private val mutableState = MutableStateFlow<BackupState>(BackupState.Idle)
    val state = mutableState.asStateFlow()
    private var running = false

    // Builds the text once, on demand: the same Ready.text backs both "save to a file" and
    // "share" so a person is never asked twice, and never gets two exports a moment apart.
    fun prepareExport(exportedAt: String) {
        if (running) return
        running = true
        mutableState.value = BackupState.Preparing
        viewModelScope.launch {
            try {
                val export = repo.exportSavedCards()
                mutableState.value = BackupState.Ready(
                    SavedCardsCodec.encode(export, exportedAt), export.favorites.size, export.reading.size)
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                Log.e("Guide", "Backup export failed", e)
                mutableState.value = BackupState.Error("Не удалось подготовить резервную копию.")
            } finally { running = false }
        }
    }

    fun restore(text: String) {
        if (running) return
        running = true
        mutableState.value = BackupState.Preparing
        viewModelScope.launch {
            try {
                mutableState.value = BackupState.Restored(repo.importSavedCards(SavedCardsCodec.decode(text)))
            } catch (e: CancellationException) { throw e }
            catch (e: IllegalArgumentException) {
                mutableState.value = BackupState.Error(e.message ?: "Некорректный файл резервной копии")
            } catch (e: Exception) {
                Log.e("Guide", "Backup restore failed", e)
                mutableState.value = BackupState.Error("Не удалось прочитать файл резервной копии.")
            } finally { running = false }
        }
    }

    fun reset() { mutableState.value = BackupState.Idle }
}
