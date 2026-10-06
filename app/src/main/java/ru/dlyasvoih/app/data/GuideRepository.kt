package ru.dlyasvoih.app.data

import android.content.SharedPreferences
import android.util.Log
import androidx.paging.Pager
import androidx.paging.PagingConfig
import androidx.room.withTransaction
import androidx.sqlite.db.SimpleSQLiteQuery
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import ru.dlyasvoih.app.data.local.*
import ru.dlyasvoih.app.data.update.ContentUpdater
import ru.dlyasvoih.app.data.update.RemoteCatalogSource
import ru.dlyasvoih.app.data.update.RemoteFiles
import ru.dlyasvoih.app.data.update.RemoteUpdateState
import ru.dlyasvoih.app.data.update.AppUpdateController
import java.io.File
import java.io.InputStream

private const val DEFAULT_UPDATE_SOURCE =
    "https://github.com/sanozhukov3737-oss/dlya-svoih-updates/releases/latest/download/latest.json"

data class CardDetails(val card: CardEntity?, val images: List<ImageEntity>,
    val sources: List<SourceEntity>, val favorite: Boolean, val countries: List<CountryEntity>,
    val related: List<CardPreview> = emptyList(), val comparisonCards: List<CardEntity> = emptyList())

class GuideRepository(private val db: GuideDatabase, private val legacyPrefs: SharedPreferences,
    private val updater: ContentUpdater? = null, private val remote: RemoteCatalogSource? = null,
    private val appCode: Int = 0, val appUpdater: AppUpdateController? = null) {
    val dao = db.guideDao()
    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val mutableMenus = MutableStateFlow<CatalogMenuLoad>(CatalogMenuLoad.Loading)
    val menuData = mutableMenus.asStateFlow()
    private var menuJob: Job? = null

    // Loaded once before navigation starts, then refreshed only when catalog tables change.
    // New screen ViewModels can use menuData.value immediately without a loading frame.
    fun retryMenus() {
        if (menuJob?.isActive == true) return
        mutableMenus.value = CatalogMenuLoad.Loading
        menuJob = applicationScope.launch {
            try {
                combine(dao.categories(""), dao.sectionCounts(), dao.categoryCounts(),
                    dao.countries(), dao.menuCountryTotals()) { categories, sections, counts, countries, totals ->
                    CatalogMenus(categories, sections.associate { it.section to it.total },
                        counts.associate { it.categoryId to it.total }, countries, totals)
                }.combine(dao.observeMetadata("content_version")) { menus, version ->
                    menus.copy(contentVersion = version.orEmpty())
                }.distinctUntilChanged().flowOn(Dispatchers.Default).collect {
                    mutableMenus.value = CatalogMenuLoad.Ready(it)
                }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                Log.e("Guide", "Catalog menus load failed", e)
                mutableMenus.value = CatalogMenuLoad.Error
            }
        }
    }
    private val readingJobs = mutableMapOf<String, Job>()
    private val readingMutex = Mutex()
    private val mutableNotice = MutableStateFlow<String?>(null)
    val notice = mutableNotice.asStateFlow()
    fun clearNotice() { mutableNotice.value = null }
    private val mutableUpdateState = MutableStateFlow<UpdateState>(UpdateState.Idle)
    val updateState = mutableUpdateState.asStateFlow()
    private fun readCachedOffer() = runCatching {
        legacyPrefs.getString("update_cached_offer", null)?.let { RemoteCatalogSource.decode(it) }
    }.getOrNull()
    private val mutableRemoteUpdate = MutableStateFlow<RemoteUpdateState>(
        readCachedOffer()?.let { RemoteUpdateState.Available(it) } ?: RemoteUpdateState.Idle)
    val remoteUpdateState = mutableRemoteUpdate.asStateFlow()
    private val mutableUpdateSource = MutableStateFlow(
        legacyPrefs.getString("update_source", DEFAULT_UPDATE_SOURCE).orEmpty())
    val updateSource = mutableUpdateSource.asStateFlow()
    private val mutableAutoCheck = MutableStateFlow(legacyPrefs.getBoolean("update_auto_check", true))
    val autoCheckUpdates = mutableAutoCheck.asStateFlow()
    private fun updatesBusy() = mutableUpdateState.value == UpdateState.Running || mutableRemoteUpdate.value.busy

    fun configureUpdates(address: String, autoCheck: Boolean) {
        require(!updatesBusy()) { "Дождитесь завершения обновления" }
        val source = address.trim()
        if (source.isNotEmpty()) RemoteFiles.httpsUrl(source)
        legacyPrefs.edit().putString("update_source", source).putBoolean("update_auto_check", autoCheck)
            .remove("update_last_attempt").remove("update_cached_offer").apply()
        mutableUpdateSource.value = source
        mutableAutoCheck.value = autoCheck
        mutableRemoteUpdate.value = RemoteUpdateState.Idle
        if (source.isNotEmpty()) checkRemoteUpdates()
    }

    fun checkRemoteUpdates(automatic: Boolean = false) {
        val source = mutableUpdateSource.value
        if (source.isEmpty() || remote == null || updatesBusy()) return
        val now = System.currentTimeMillis()
        val previous = legacyPrefs.getLong("update_last_attempt", 0L)
        if (automatic && (!mutableAutoCheck.value || (now >= previous && now - previous < 24L * 60 * 60 * 1000))) return
        legacyPrefs.edit().putLong("update_last_attempt", now).apply()
        val fallback = when (val current = mutableRemoteUpdate.value) {
            is RemoteUpdateState.Available -> current.catalog
            is RemoteUpdateState.Error -> current.catalog
            else -> null
        }
        mutableRemoteUpdate.value = RemoteUpdateState.Checking
        mutableUpdateState.value = UpdateState.Idle
        applicationScope.launch {
            try {
                val offer = withContext(Dispatchers.IO) { remote.check(source) }
                legacyPrefs.edit().putString("update_cached_offer", RemoteCatalogSource.encode(offer)).apply()
                val installed = contentVersion()
                mutableRemoteUpdate.value = when {
                    offer.version <= installed -> RemoteUpdateState.Current(installed)
                    offer.minAppCode > appCode -> RemoteUpdateState.NeedsAppUpdate
                    else -> RemoteUpdateState.Available(offer)
                }
                if (automatic && mutableRemoteUpdate.value is RemoteUpdateState.Available) {
                    mutableNotice.value = "Доступно обновление каталога до версии ${offer.version}."
                }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                Log.e("Guide", "Online update check failed", e)
                mutableRemoteUpdate.value = RemoteUpdateState.Error(if (e is IllegalArgumentException)
                    e.message ?: "Некорректное описание обновления" else "Не удалось проверить обновления. Проверьте интернет и повторите попытку.", fallback)
            }
        }
    }

    fun installRemoteUpdate() {
        if (remote == null || updater == null || updatesBusy()) return
        val offer = when (val state = mutableRemoteUpdate.value) {
            is RemoteUpdateState.Available -> state.catalog
            is RemoteUpdateState.Error -> state.catalog
            else -> null
        } ?: return
        mutableRemoteUpdate.value = RemoteUpdateState.Downloading(0, offer.bytes)
        applicationScope.launch {
            var archive: File? = null
            try {
                val installed = contentVersion()
                if (offer.version <= installed) {
                    mutableRemoteUpdate.value = RemoteUpdateState.Current(installed)
                    return@launch
                }
                require(offer.minAppCode <= appCode) { "Для этого каталога нужна новая версия приложения" }
                val downloaded = withContext(Dispatchers.IO) {
                    remote.download(offer) { bytes -> mutableRemoteUpdate.value = RemoteUpdateState.Downloading(bytes, offer.bytes) }
                }
                archive = downloaded
                mutableRemoteUpdate.value = RemoteUpdateState.Installing
                val version = withContext(Dispatchers.IO) {
                    downloaded.inputStream().use { updater.importPack(it, expectedVersion = offer.version) }
                }
                mutableRemoteUpdate.value = RemoteUpdateState.Current(version)
                mutableUpdateState.value = UpdateState.Done(version)
                mutableNotice.value = "Каталог обновлён до версии $version."
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                Log.e("Guide", "Online catalog install failed", e)
                mutableRemoteUpdate.value = RemoteUpdateState.Error(if (e is IllegalArgumentException)
                    e.message ?: "Не удалось установить обновление" else
                    "Не удалось скачать или установить обновление. Проверьте интернет и свободное место.", offer)
            } finally { archive?.delete() }
        }
    }

    suspend fun initialize() = withContext(Dispatchers.IO) {
        updater?.initialize()
        db.withTransaction {
            if (dao.metadata("legacy_favorites_imported") == null) {
                // Marker and inserts commit atomically. Existing SQL favorites are never overwritten.
                val oldIds = legacyPrefs.getStringSet("favorites", emptySet()).orEmpty().toSet()
                for (id in oldIds.sorted()) if (dao.hasCard(id)) {
                    dao.addFavorite(FavoriteEntity(id, System.currentTimeMillis()))
                }
                dao.putMetadata(MetadataEntity("legacy_favorites_imported", "1"))
            }
        }
        withContext(Dispatchers.Main.immediate) { retryMenus() }
        check(menuData.first { it != CatalogMenuLoad.Loading } is CatalogMenuLoad.Ready) {
            "Catalog menus could not be loaded"
        }
        // Network checks never delay BootState.Ready or screen navigation.
        val installed = contentVersion()
        val cachedOffer = readCachedOffer()
        withContext(Dispatchers.Main.immediate) {
            if (cachedOffer != null && mutableUpdateSource.value.isNotEmpty()) {
                mutableRemoteUpdate.value = when {
                    cachedOffer.version <= installed -> RemoteUpdateState.Current(installed)
                    cachedOffer.minAppCode > appCode -> RemoteUpdateState.NeedsAppUpdate
                    else -> RemoteUpdateState.Available(cachedOffer)
                }
            } else if (mutableUpdateSource.value.isEmpty()) mutableRemoteUpdate.value = RemoteUpdateState.Idle
            checkRemoteUpdates(automatic = true)
            appUpdater?.restoreAndCheck()
        }
    }

    suspend fun cardIds(filter: CatalogFilter): List<String> = withContext(Dispatchers.IO) {
        val request = CatalogQuery.ids(filter)
        dao.cardIds(SimpleSQLiteQuery(request.sql, request.args.toTypedArray()))
    }

    suspend fun readerCards(filter: CatalogFilter): List<ReaderCard> = withContext(Dispatchers.IO) {
        val request = CatalogQuery.readerCards(filter)
        dao.readerCards(SimpleSQLiteQuery(request.sql, request.args.toTypedArray()))
    }

    fun cards(filter: CatalogFilter) = Pager(
        PagingConfig(pageSize = 30, initialLoadSize = 60, prefetchDistance = 8,
            maxSize = 180, enablePlaceholders = false)
    ) {
        val request = CatalogQuery.build(filter)
        val query = SimpleSQLiteQuery(request.sql, request.args.toTypedArray())
        if (filter.favoritesOnly) dao.favoritePage(query) else dao.page(query)
    }.flow

    fun detail(id: String) = combine(combine(dao.card(id), dao.images(id), dao.sources(id),
        dao.isFavorite(id), dao.cardCountries(id)) { card, images, sources, favorite, countries ->
        CardDetails(card, images, sources, favorite, countries)
    }, dao.relatedCards(id), dao.relatedCardEntities(id)) { details, related, comparisonCards ->
        details.copy(related = related, comparisonCards = comparisonCards)
    }

    suspend fun toggleFavorite(id: String) {
        db.withTransaction {
            // Transaction serializes fast taps and protects against read/modify/write races.
            if (dao.removeFavorite(id) == 0 && dao.hasCard(id)) {
                dao.addFavorite(FavoriteEntity(id, System.currentTimeMillis()))
            }
        }
    }

    suspend fun contentVersion(): Long = withContext(Dispatchers.IO) { dao.metadata("content_version")?.toLongOrNull() ?: 0L }

    suspend fun exportSavedCards(): SavedCardsExport = withContext(Dispatchers.IO) {
        SavedCardsExport(dao.allFavorites(), dao.allReading())
    }

    // Cards not present in this install (renamed, removed, or restored onto a different catalog
    // version) are reported by title rather than silently dropped, so the person can see what a
    // restore could not bring back.
    suspend fun importSavedCards(export: SavedCardsExport): SavedCardsImportResult = withContext(Dispatchers.IO) {
        val version = dao.metadata("content_version")?.toLongOrNull() ?: 0L
        val favoritesMissing = mutableListOf<String>()
        val readingMissing = mutableListOf<String>()
        var favoritesRestored = 0
        var readingRestored = 0
        db.withTransaction {
            // Reversed: the export lists the most recently saved item first, and each restored
            // favorite gets a fresh, later timestamp than the one before it, so restoring in
            // reverse puts the originally most recent item back on top.
            for (item in export.favorites.asReversed()) {
                if (dao.hasCard(item.cardId)) {
                    dao.addFavorite(FavoriteEntity(item.cardId, System.currentTimeMillis()))
                    favoritesRestored++
                } else favoritesMissing += item.title
            }
            for (item in export.reading.asReversed()) {
                if (!dao.hasCard(item.cardId)) { readingMissing += item.title; continue }
                // A restore never overwrites progress the person already has on this install.
                if (dao.reading(item.cardId) == null) {
                    dao.saveReading(ReadingEntity(item.cardId, 0, 0, System.currentTimeMillis(), version))
                }
                readingRestored++
            }
            dao.trimReading()
        }
        SavedCardsImportResult(favoritesRestored, favoritesMissing, readingRestored, readingMissing)
    }

    suspend fun reading(id: String): ReadingEntity? = withContext(Dispatchers.IO) {
        val reading = dao.reading(id) ?: return@withContext null
        if (reading.contentVersion == dao.metadata("content_version")?.toLongOrNull()) reading
        else reading.copy(itemIndex = 0, offset = 0)
    }

    // Application scope survives navigation; writes are debounced and serialized.
    fun scheduleReading(id: String, index: Int, offset: Int, contentVersion: Long, immediate: Boolean = false) {
        readingJobs.remove(id)?.cancel()
        val timestamp = System.currentTimeMillis()
        val job = applicationScope.launch(start = CoroutineStart.LAZY) {
            try {
                if (!immediate) delay(500)
                readingMutex.withLock {
                    db.withTransaction {
                        if (dao.hasCard(id)) {
                            dao.saveReading(ReadingEntity(id, index.coerceAtLeast(0), offset.coerceAtLeast(0), timestamp,
                                contentVersion))
                            dao.trimReading()
                        }
                    }
                }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { Log.e("Guide", "Reading progress save failed", e); mutableNotice.value = "Не удалось сохранить место чтения." }
            finally { if (readingJobs[id] === currentCoroutineContext()[Job]) readingJobs.remove(id) }
        }
        readingJobs[id] = job
        job.start()
    }

    suspend fun dismissReading(id: String) {
        readingJobs.remove(id)?.cancel()
        withContext(Dispatchers.IO) {
            readingMutex.withLock { dao.removeReading(id) }
        }
    }

    fun importContent(open: () -> InputStream) {
        if (updatesBusy() || updater == null) return
        mutableRemoteUpdate.value = RemoteUpdateState.Idle
        mutableUpdateState.value = UpdateState.Running
        applicationScope.launch {
            try {
                val version = withContext(Dispatchers.IO) { open().use { updater.importPack(it) } }
                mutableUpdateState.value = UpdateState.Done(version)
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                Log.e("Guide", "Content update failed", e)
                mutableUpdateState.value = UpdateState.Error(if (e is IllegalArgumentException) e.message ?: "Некорректный пакет" else "Не удалось прочитать пакет. Проверьте файл и свободное место.")
            }
        }
    }
}

sealed interface UpdateState {
    data object Idle : UpdateState
    data object Running : UpdateState
    data class Done(val version: Long) : UpdateState
    data class Error(val message: String) : UpdateState
}
