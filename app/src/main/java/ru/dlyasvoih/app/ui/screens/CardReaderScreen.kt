package ru.dlyasvoih.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.LayoutDirection
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModelStore
import androidx.lifecycle.ViewModelStoreOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.launch
import ru.dlyasvoih.app.data.GuideRepository
import ru.dlyasvoih.app.ui.CardReaderState
import ru.dlyasvoih.app.ui.CardReaderViewModel
import ru.dlyasvoih.app.ui.DetailViewModel

@Composable
fun CardReaderScreen(vm: CardReaderViewModel, repo: GuideRepository, onBack: () -> Unit,
    onList: () -> Unit, onRelated: (String) -> Unit, onImage: (String, Int) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    var pickerPage by remember { mutableStateOf<Int?>(null) }
    var jump by remember { mutableStateOf<ReaderJump?>(null) }
    var jumpToken by remember { mutableIntStateOf(0) }
    when (val current = state) {
        CardReaderState.Loading -> ReaderStatus(onBack) { StatusPanel("Открываем книгу карточек…", loading = true) }
        CardReaderState.Error -> ReaderStatus(onBack) { StatusPanel("Не удалось загрузить карточки", retry = vm::retry) }
        is CardReaderState.Ready -> if (current.ids.isEmpty()) {
            ReaderStatus(onBack) { StatusPanel("Нет карточек с выбранными фильтрами.") }
        } else {
            CardReaderPages(current.ids, vm.initialId, vm::rememberCard, jump) { id, active, page, total, previous, next ->
                ReaderDetailPage(repo, id, active, onBack, onRelated, pageNavigation = {
                    Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp)) {
                        Text(current.title, maxLines = 1, overflow = TextOverflow.Ellipsis,
                            style = MaterialTheme.typography.labelLarge)
                        Text(current.country, maxLines = 1, overflow = TextOverflow.Ellipsis,
                            style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            TextButton(onClick = previous ?: {}, enabled = previous != null,
                                modifier = Modifier.testTag("reader_previous").semantics { contentDescription = "Предыдущая карточка" }) { Text("‹") }
                            TextButton(onClick = { pickerPage = page }, modifier = Modifier.weight(1f)
                                .testTag("reader_position").semantics { contentDescription = "Перейти к карточке" }) {
                                Text("$page / $total", style = MaterialTheme.typography.labelLarge)
                            }
                            TextButton(onClick = onList) { Text("Список") }
                            TextButton(onClick = next ?: {}, enabled = next != null,
                                modifier = Modifier.testTag("reader_next").semantics { contentDescription = "Следующая карточка" }) { Text("›") }
                        }
                        Text("Свайп вправо — следующая карточка", style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(bottom = 6.dp))
                    }
                }, onImage = { index -> onImage(id, index) })
            }
            pickerPage?.let { page ->
                ReaderCardPicker(current.cards, page, onChoose = { index ->
                    jump = ReaderJump(index, ++jumpToken)
                    pickerPage = null
                }, onDismiss = { pickerPage = null })
            }
        }
    }
}

/** Stable page keys retain vertical positions; only a settled visible page is marked as read. */
@Composable
internal fun CardReaderPages(ids: List<String>, initialId: String, onSettled: (String) -> Unit,
    jump: ReaderJump? = null,
    content: @Composable (id: String, active: Boolean, page: Int, total: Int,
        previous: (() -> Unit)?, next: (() -> Unit)?) -> Unit) {
    if (ids.isEmpty()) return
    // Physical pages run opposite to the catalog order. A finger moving to the right decreases
    // the physical page number, so it opens the next card. Keep the normal pager scroll/nested-
    // scroll implementation rather than reversing it around vertically scrolling articles.
    val pager = key("reader-right-swipe-v2") {
        rememberPagerState(initialPage = ids.lastIndex - ids.indexOf(initialId).coerceAtLeast(0), pageCount = { ids.size })
    }
    val scope = rememberCoroutineScope()
    val settledCallback by rememberUpdatedState(onSettled)
    LaunchedEffect(pager, jump) {
        jump?.let { if (it.index in ids.indices) pager.scrollToPage(ids.lastIndex - it.index) }
    }
    LaunchedEffect(pager, ids) {
        snapshotFlow { if (pager.isScrollInProgress) null else ids.getOrNull(ids.lastIndex - pager.settledPage) }
            .filterNotNull().distinctUntilChanged().collect { settledCallback(it) }
    }
    CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr) {
        HorizontalPager(state = pager, modifier = Modifier.fillMaxSize().testTag("card_reader"),
            // Prepare one page in each direction while idle, including its asynchronous
            // detail/image load. Do not start composing the next article during the swipe.
            // Keep this window bounded; page-owned ViewModels are still disposed outside it.
            beyondViewportPageCount = 1,
            reverseLayout = false, key = { ids[ids.lastIndex - it] }) { physicalPage ->
            val index = ids.lastIndex - physicalPage
            val previous: (() -> Unit)? = if (index > 0) ({ scope.launch { pager.animateScrollToPage(physicalPage + 1) }; Unit }) else null
            val next: (() -> Unit)? = if (index + 1 < ids.size) ({ scope.launch { pager.animateScrollToPage(physicalPage - 1) }; Unit }) else null
            content(ids[index], physicalPage == pager.settledPage && !pager.isScrollInProgress,
                index + 1, ids.size, previous, next)
        }
    }
}

internal data class ReaderJump(val index: Int, val token: Int)

@Composable
private fun ReaderDetailPage(repo: GuideRepository, id: String, active: Boolean, onBack: () -> Unit, onRelated: (String) -> Unit,
    pageNavigation: @Composable () -> Unit, onImage: (Int) -> Unit) {
    // A store belongs to one composed page and is cleared when it leaves the pager. Using the
    // navigation entry's store here would retain a DetailViewModel for every card ever visited.
    val owner = remember(id) { object : ViewModelStoreOwner { override val viewModelStore = ViewModelStore() } }
    DisposableEffect(owner) { onDispose { owner.viewModelStore.clear() } }
    val vm: DetailViewModel = viewModel(viewModelStoreOwner = owner, factory = remember(repo, id) {
        viewModelFactory { initializer { DetailViewModel(repo, SavedStateHandle(mapOf("id" to id))) } }
    })
    DetailScreen(vm, onBack, active, pageNavigation, onRelated, onImage)
}

@Composable
private fun ReaderStatus(onBack: () -> Unit, content: @Composable () -> Unit) {
    Scaffold(topBar = { GuideBar("Книга карточек", onBack) }) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) { content() }
    }
}
