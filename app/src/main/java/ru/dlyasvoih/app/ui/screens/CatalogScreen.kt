package ru.dlyasvoih.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.paging.LoadState
import androidx.paging.compose.collectAsLazyPagingItems
import androidx.paging.compose.itemKey
import kotlinx.coroutines.flow.distinctUntilChanged
import ru.dlyasvoih.app.R
import ru.dlyasvoih.app.data.MainSection
import ru.dlyasvoih.app.data.SearchQuery
import ru.dlyasvoih.app.data.CatalogStatus
import ru.dlyasvoih.app.data.PhotoSelection
import ru.dlyasvoih.app.ui.*

@Composable
fun CatalogScreen(vm: CatalogViewModel, onBack: (() -> Unit)? = null,
    onRead: (() -> Unit)? = null, onOpen: (String) -> Unit) {
    val query by vm.query.collectAsStateWithLifecycle()
    val country by vm.country.collectAsStateWithLifecycle()
    val category by vm.selectedCategory.collectAsStateWithLifecycle()
    val status by vm.status.collectAsStateWithLifecycle()
    val photo by vm.photo.collectAsStateWithLifecycle()
    val options by vm.options.collectAsStateWithLifecycle()
    val favorites by vm.favorites.collectAsStateWithLifecycle()
    val pending by vm.pending.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val applied by vm.applied.collectAsStateWithLifecycle()
    val cards = vm.pages.collectAsLazyPagingItems()
    val listState = rememberLazyListState()
    val gridState = rememberLazyGridState()
    val snackbar = remember { SnackbarHostState() }
    val filterOptions = (options as? DataState.Ready<FilterOptions>)?.value
    val countryLabel = filterOptions?.countries?.firstOrNull { it.id == country }?.name
        ?: if (country.isEmpty()) "Все страны / контексты" else "Страна / контекст: $country"
    val categoryLabel = filterOptions?.categories?.firstOrNull { it.id == category }?.title
        ?: if (category.isEmpty()) "Все категории" else category
    val statusLabel = when (status) {
        CatalogStatus.VERIFIED -> "Подтверждённые"
        CatalogStatus.REVIEWED -> "Проверенные"
        CatalogStatus.SOURCE_ONLY -> "По источнику"
        CatalogStatus.CANDIDATE -> "Требуют проверки"
        else -> "Любая достоверность"
    }
    val photoLabel = when (photo) {
        PhotoSelection.WITH_PHOTO -> "Есть фото"
        PhotoSelection.WITHOUT_PHOTO -> "Без фото"
        else -> "Любые изображения"
    }
    val favoriteStatuses = (favorites as? DataState.Ready<FavoriteStatuses>)?.value
    val key = FilterKey(SearchQuery.key(query), country, category, status, photo)
    val firstKey = cards.itemSnapshotList.items.firstOrNull()?.key
    val refresh = cards.loadState.refresh
    val waiting = applied != key || (firstKey != null && firstKey != key) || refresh is LoadState.Loading
    var lastKey by remember { mutableStateOf(key) }
    var countryDialog by rememberSaveable { mutableStateOf(false) }
    var categoryDialog by rememberSaveable { mutableStateOf(false) }
    var statusDialog by rememberSaveable { mutableStateOf(false) }
    var photoDialog by rememberSaveable { mutableStateOf(false) }
    var searchExpanded by rememberSaveable { mutableStateOf(vm.mode == CatalogMode.SEARCH || query.isNotBlank()) }
    var gridMode by rememberSaveable(vm.category) { mutableStateOf(vm.category == "grenades") }
    LaunchedEffect(error) { error?.let { snackbar.showSnackbar(it); vm.clearError() } }
    LaunchedEffect(cards) {
        snapshotFlow { cards.itemSnapshotList.items.map { it.card.id } }.distinctUntilChanged().collect(vm::observeFavorites)
    }
    LaunchedEffect(waiting, key, refresh) {
        if (!waiting && refresh is LoadState.NotLoading && lastKey != key) {
            if (cards.itemCount > 0) {
                if (gridMode) gridState.scrollToItem(0) else listState.scrollToItem(0)
            }
            lastKey = key
        }
    }
    val title = when (vm.mode) {
        CatalogMode.SEARCH -> "Поиск"
        CatalogMode.FAVORITES -> "Избранное"
        CatalogMode.HISTORY -> "Недавние"
        CatalogMode.CATALOG -> filterOptions?.categories?.firstOrNull { it.id == vm.category }?.title
            ?: MainSection.fromId(vm.section)?.title ?: "Каталог"
    }
    Scaffold(topBar = {
        GuideBar(title, onBack) {
            IconButton(onClick = { gridMode = !gridMode }, modifier = Modifier.semantics {
                contentDescription = if (gridMode) "Показать списком" else "Показать сеткой"
            }) {
                Icon(painterResource(if (gridMode) R.drawable.icon_ui_list else R.drawable.icon_ui_grid), contentDescription = null)
            }
            if (vm.mode != CatalogMode.SEARCH) {
                IconButton(onClick = {
                    searchExpanded = !searchExpanded
                    if (!searchExpanded) vm.setQuery("")
                }, modifier = Modifier.testTag("search_toggle").semantics {
                    contentDescription = if (searchExpanded) "Закрыть поиск" else "Открыть поиск"
                }) {
                    Icon(painterResource(if (searchExpanded) R.drawable.icon_ui_close else R.drawable.icon_ui_search), contentDescription = null)
                }
            }
        }
    }, snackbarHost = { SnackbarHost(snackbar) }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(horizontal = 14.dp)) {
            if (searchExpanded) {
                OutlinedTextField(
                    value = query,
                    onValueChange = vm::setQuery,
                    modifier = Modifier.fillMaxWidth().height(50.dp).testTag("search_input"),
                    singleLine = true,
                    textStyle = MaterialTheme.typography.bodyMedium,
                    placeholder = { Text(if (vm.mode == CatalogMode.SEARCH) "Поиск по всему справочнику" else "Поиск в этом разделе") },
                    leadingIcon = { Icon(painterResource(R.drawable.icon_ui_search), contentDescription = null, Modifier.size(19.dp)) },
                    trailingIcon = {
                        if (query.isNotEmpty()) IconButton(onClick = { vm.setQuery("") }) {
                            Icon(painterResource(R.drawable.icon_ui_close), contentDescription = "Очистить")
                        }
                    },
                    shape = MaterialTheme.shapes.medium
                )
            }
            Row(Modifier.fillMaxWidth().padding(top = 7.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Фильтры", style = MaterialTheme.typography.labelLarge)
                Spacer(Modifier.weight(1f))
                if (!waiting && cards.itemCount > 0) Text("${cards.itemCount}+", style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (country.isNotEmpty() || status.isNotEmpty() || photo.isNotEmpty() || (vm.category.isEmpty() && category.isNotEmpty())) {
                    TextButton(onClick = vm::clearFilters) { Text("Сбросить") }
                }
            }
            LazyRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(7.dp),
                contentPadding = PaddingValues(bottom = 7.dp)) {
                item {
                    FilterChip(selected = country.isNotEmpty(), enabled = filterOptions != null,
                        modifier = Modifier.testTag("country_filter"), onClick = { countryDialog = true },
                        label = { Text(countryLabel, maxLines = 1) })
                }
                if (vm.category.isEmpty()) item {
                    FilterChip(selected = category.isNotEmpty(), enabled = filterOptions != null,
                        modifier = Modifier.testTag("category_filter"), onClick = { categoryDialog = true },
                        label = { Text(categoryLabel, maxLines = 1) })
                }
                item {
                    FilterChip(selected = status.isNotEmpty(), onClick = { statusDialog = true },
                        modifier = Modifier.testTag("status_filter"), label = { Text(statusLabel, maxLines = 1) })
                }
                item {
                    FilterChip(selected = photo.isNotEmpty(), onClick = { photoDialog = true },
                        modifier = Modifier.testTag("photo_filter"), label = { Text(photoLabel, maxLines = 1) })
                }
            }
            if (onRead != null) TextButton(onClick = onRead,
                enabled = !waiting && cards.itemCount > 0,
                modifier = Modifier.fillMaxWidth().testTag("open_book")) {
                Text("Листать как книгу")
            }
            when {
                options == DataState.Loading -> StatusPanel("Загружаем фильтры…", loading = true)
                options == DataState.Error -> StatusPanel("Не удалось прочитать страны / контексты и категории", retry = vm::retryOptions)
                refresh is LoadState.Error -> StatusPanel("Не удалось загрузить карточки", retry = cards::retry)
                waiting -> StatusPanel("Загружаем карточки…", loading = true)
                cards.itemCount == 0 -> StatusPanel(when {
                    vm.mode == CatalogMode.SEARCH && query.isBlank() -> "Введите название, слово из текста или тег."
                    query.isNotBlank() -> "Ничего не найдено с выбранными фильтрами. Попробуйте другое слово или страну / контекст."
                    country.isNotEmpty() -> "Карточек по выбранной стране / контексту пока нет. Общие памятки доступны в «Все страны / контексты»."
                    vm.mode == CatalogMode.FAVORITES -> "Здесь появятся карточки, отмеченные звездой."
                    vm.mode == CatalogMode.HISTORY -> "История пока пуста. Откройте карточку, и она появится здесь."
                    else -> "Этот раздел пока не наполнен."
                })
                else -> {
                    if (favorites == DataState.Error) TextButton(onClick = vm::retryOptions) {
                        Text("Не удалось прочитать избранное. Повторить")
                    }
                    if (gridMode) {
                        LazyVerticalGrid(
                            columns = GridCells.Adaptive(156.dp),
                            modifier = Modifier.weight(1f).testTag("catalog_list"),
                            state = gridState,
                            contentPadding = PaddingValues(bottom = 16.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp),
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            items(count = cards.itemCount, key = cards.itemKey { it.card.id }) { index: Int ->
                                cards[index]?.takeIf { it.key == key }?.card?.let { card ->
                                    CardGrid(card, favoriteStatuses?.takeIf { card.id in it.knownIds }?.selected?.contains(card.id),
                                        card.id in pending, { onOpen(card.id) }, { vm.toggleFavorite(card.id) })
                                }
                            }
                        }
                    } else {
                        LazyColumn(Modifier.weight(1f).testTag("catalog_list"), state = listState,
                            contentPadding = PaddingValues(bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                            items(count = cards.itemCount, key = cards.itemKey { it.card.id }, contentType = { "card" }) { index: Int ->
                                cards[index]?.takeIf { it.key == key }?.card?.let { card ->
                                    CardRow(card, favoriteStatuses?.takeIf { card.id in it.knownIds }?.selected?.contains(card.id),
                                        card.id in pending, { onOpen(card.id) }, { vm.toggleFavorite(card.id) })
                                }
                            }
                            when (cards.loadState.append) {
                                is LoadState.Loading -> item(key = "more_loading") {
                                    Box(Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                                }
                                is LoadState.Error -> item(key = "more_error") {
                                    TextButton(onClick = cards::retry) { Text("Загрузить следующие карточки ещё раз") }
                                }
                                else -> Unit
                            }
                        }
                    }
                }
            }
        }
    }
    if (countryDialog) {
        val countryOptions = filterOptions?.countries.orEmpty()
        AlertDialog(onDismissRequest = { countryDialog = false }, title = { Text("Страна / контекст") }, text = {
            LazyColumn(Modifier.heightIn(max = 400.dp)) {
                item { CountryOption("Все страны / контексты", country.isEmpty()) { vm.setCountry(""); countryDialog = false } }
                items(count = countryOptions.size, key = { index -> countryOptions[index].id }) { index: Int ->
                    val option = countryOptions[index]
                    CountryOption("${option.name} · ${option.total}", country == option.id) { vm.setCountry(option.id); countryDialog = false }
                }
            }
        }, confirmButton = { TextButton(onClick = { countryDialog = false }) { Text("Закрыть") } })
    }
    if (categoryDialog) {
        val categoryOptions = filterOptions?.categories.orEmpty()
        ChoiceDialog("Категория", listOf("" to "Все категории") + categoryOptions.map { it.id to it.title }, category,
            onSelect = { vm.setCategory(it); categoryDialog = false }, onDismiss = { categoryDialog = false })
    }
    if (statusDialog) {
        ChoiceDialog("Достоверность", listOf(
            "" to "Любая достоверность",
            CatalogStatus.VERIFIED to "Подтверждённые модели и семейства",
            CatalogStatus.REVIEWED to "Проверенные по источникам",
            CatalogStatus.SOURCE_ONLY to "По предоставленному источнику",
            CatalogStatus.CANDIDATE to "Требуют дополнительной проверки"
        ), status, onSelect = { vm.setStatus(it); statusDialog = false }, onDismiss = { statusDialog = false })
    }
    if (photoDialog) {
        ChoiceDialog("Изображения", listOf(
            "" to "Любые изображения",
            PhotoSelection.WITH_PHOTO to "Есть встроенное изображение",
            PhotoSelection.WITHOUT_PHOTO to "Изображение отсутствует"
        ), photo, onSelect = { vm.setPhoto(it); photoDialog = false }, onDismiss = { photoDialog = false })
    }
}

@Composable
private fun CountryOption(label: String, selected: Boolean, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        RadioButton(selected, onClick = null)
        Text(label, Modifier.padding(12.dp))
    }
}

@Composable
private fun ChoiceDialog(title: String, options: List<Pair<String, String>>, selected: String,
    onSelect: (String) -> Unit, onDismiss: () -> Unit) {
    AlertDialog(onDismissRequest = onDismiss, title = { Text(title) }, text = {
        LazyColumn(Modifier.heightIn(max = 430.dp)) {
            items(count = options.size, key = { index -> options[index].first }) { index ->
                val option = options[index]
                CountryOption(option.second, option.first == selected) { onSelect(option.first) }
            }
        }
    }, confirmButton = { TextButton(onClick = onDismiss) { Text("Закрыть") } })
}
