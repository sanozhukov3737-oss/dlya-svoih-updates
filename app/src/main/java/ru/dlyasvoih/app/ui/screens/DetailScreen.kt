package ru.dlyasvoih.app.ui.screens

import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.flow.distinctUntilChanged
import ru.dlyasvoih.app.R
import ru.dlyasvoih.app.data.MainSection
import ru.dlyasvoih.app.data.local.CardEntity
import ru.dlyasvoih.app.data.local.CardPreview
import ru.dlyasvoih.app.data.local.ImageEntity
import ru.dlyasvoih.app.ui.DataState
import ru.dlyasvoih.app.ui.DetailState
import ru.dlyasvoih.app.ui.DetailViewModel
import ru.dlyasvoih.app.ui.GalleryViewModel
import ru.dlyasvoih.app.ui.content.ReferenceBodyParser
import kotlin.math.max

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DetailScreen(vm: DetailViewModel, onBack: () -> Unit, active: Boolean = true,
    pageNavigation: (@Composable () -> Unit)? = null, onImage: (Int) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
    val ready = (state as? DetailState.Ready)?.value
    val paragraphs = (state as? DetailState.Ready)?.paragraphs.orEmpty()
    var quickOpen by remember { mutableStateOf(false) }
    var compareOpen by remember { mutableStateOf(false) }
    LaunchedEffect(error) { error?.let { snackbar.showSnackbar(it); vm.clearError() } }
    val context = LocalContext.current
    Scaffold(topBar = {
        Column {
            GuideBar("Карточка", onBack) {
                val shareCard = ready?.card
                if (shareCard != null) {
                    IconButton(onClick = {
                        val send = Intent(Intent.ACTION_SEND).apply {
                            type = "text/plain"
                            putExtra(Intent.EXTRA_TEXT, buildShareText(shareCard, paragraphs))
                            putExtra(Intent.EXTRA_SUBJECT, shareCard.title)
                        }
                        context.startActivity(Intent.createChooser(send, "Поделиться карточкой"))
                    }, modifier = Modifier.semantics { contentDescription = "Поделиться" }) {
                        Icon(painterResource(R.drawable.icon_ui_share), contentDescription = null)
                    }
                }
                if (ready != null) FavoriteButton(ready.favorite, !busy, vm::toggleFavorite)
            }
            pageNavigation?.invoke()
        }
    }, snackbarHost = { SnackbarHost(snackbar) }) { padding ->
        when (state) {
            DetailState.Loading -> StatusPanel("Открываем карточку…", Modifier.padding(padding), loading = true)
            DetailState.Error -> StatusPanel("Не удалось открыть карточку", Modifier.padding(padding), retry = vm::retry)
            DetailState.Missing -> StatusPanel("Карточка не найдена", Modifier.padding(padding))
            is DetailState.Ready -> {
                val value = ready ?: return@Scaffold
                val card = value.card ?: return@Scaffold
                val reading = (state as DetailState.Ready).reading
                val secondaryImages = value.images.drop(1)
                val displayParagraphs = remember(paragraphs, card.categoryId) {
                    readerParagraphs(paragraphs, card.categoryId == "mortars")
                }
                val itemCount = 5 + secondaryImages.size + displayParagraphs.size
                val listState = rememberLazyListState(reading?.itemIndex?.coerceIn(0, (itemCount - 1).coerceAtLeast(0)) ?: 0,
                    reading?.offset?.coerceIn(0, 100_000) ?: 0)
                val lifecycle = LocalLifecycleOwner.current.lifecycle
                LaunchedEffect(vm, listState, active) {
                    if (active) snapshotFlow { listState.firstVisibleItemIndex to listState.firstVisibleItemScrollOffset }
                        .distinctUntilChanged().collect { vm.position(it.first, it.second) }
                }
                DisposableEffect(vm, listState, lifecycle, active) {
                    fun flush() { vm.position(listState.firstVisibleItemIndex, listState.firstVisibleItemScrollOffset); vm.flushReading() }
                    val observer = LifecycleEventObserver { _, event -> if (active && event == Lifecycle.Event.ON_STOP) flush() }
                    lifecycle.addObserver(observer)
                    onDispose { if (active) flush(); lifecycle.removeObserver(observer) }
                }
                LazyColumn(
                    Modifier.fillMaxSize().padding(padding).testTag("detail_list"),
                    state = listState,
                    contentPadding = PaddingValues(bottom = 28.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    item(key = "hero") { DetailHero(card, value.images.firstOrNull(), value.countries.joinToString(" · ") { it.name }) { onImage(0) } }
                    if (card.categoryId != "mortars" || value.comparisonCards.isNotEmpty()) item(key = "actions") {
                        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            if (card.categoryId != "mortars") {
                                QuickAction("Быстрая сверка", R.drawable.icon_ui_focus, Modifier.weight(1f)) { quickOpen = true }
                            }
                            QuickAction("Сравнить", R.drawable.icon_ui_compare, Modifier.weight(1f), enabled = value.comparisonCards.isNotEmpty()) { compareOpen = true }
                        }
                    }
                    items(secondaryImages, key = { "image_${it.id}" }, contentType = { "image" }) { picture ->
                        val originalIndex = value.images.indexOf(picture)
                        Card(onClick = { onImage(originalIndex) }, modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
                            Surface(color = Color.White) {
                                LocalGuideImage(picture.localPath, picture.caption,
                                    Modifier.fillMaxWidth().heightIn(min = 180.dp, max = 360.dp)
                                        .aspectRatio((picture.width.toFloat() / picture.height.coerceAtLeast(1)).coerceIn(0.75f, 2.2f)), fit = true)
                            }
                            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                                Text(imageKindLabel(picture.caption), style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.primary)
                                Text(picture.caption, style = MaterialTheme.typography.labelMedium)
                                Text(imageRightsLabel(picture.caption), style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                    items(displayParagraphs, contentType = { "paragraph" }) { paragraph ->
                        Box(Modifier.padding(horizontal = 18.dp)) { ReferenceBodyBlock(paragraph) }
                    }
                    if (card.categoryId != "mortars") item(key = "tags") {
                        Text(card.tags, Modifier.padding(horizontal = 18.dp), style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary)
                    }
                    if (value.related.isNotEmpty()) item(key = "related") {
                        Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
                            Text("Похожие в категории", Modifier.padding(horizontal = 18.dp), style = MaterialTheme.typography.titleLarge)
                            LazyRow(contentPadding = PaddingValues(horizontal = 18.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                items(value.related.take(6), key = { it.id }) { related ->
                                    AtlasPreviewCard(related) { compareOpen = true }
                                }
                            }
                        }
                    }
                    item(key = "sources") { SourcesCard(value.sources, card.sourceGrade, card.verifiedAt) }
                }
            }
        }
    }
    val value = ready
    val card = value?.card
    if (quickOpen && card != null) {
        QuickRecognitionSheet(card, recognitionBlocks(paragraphs)) { quickOpen = false }
    }
    if (compareOpen && card != null && value != null && value.comparisonCards.isNotEmpty()) {
        ComparisonSheet(card, value.comparisonCards) { compareOpen = false }
    }
}

@Composable
private fun DetailHero(card: CardEntity, image: ImageEntity?, countries: String, onImage: () -> Unit) {
    Box(Modifier.fillMaxWidth().heightIn(min = 310.dp).clip(RoundedCornerShape(
        topStart = 0.dp, topEnd = 0.dp, bottomEnd = 26.dp, bottomStart = 26.dp))) {
        if (image != null) {
            Surface(onClick = onImage, modifier = Modifier.matchParentSize(), color = Color.White) {
                LocalGuideImage(image.localPath, image.caption, Modifier.fillMaxSize(), fit = true)
            }
        } else {
            Surface(Modifier.matchParentSize(), color = MaterialTheme.colorScheme.surfaceContainerHigh) {
                CatalogMenuIcon(card.categoryId.ifBlank { card.section }, Modifier.padding(68.dp), useRepresentativePhoto = false)
            }
        }
        Box(Modifier.matchParentSize().background(Brush.verticalGradient(listOf(Color.Transparent, Color.Transparent, Color(0xE5101411)))))
        Column(Modifier.align(Alignment.BottomStart).padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(MainSection.fromId(card.section)?.title.orEmpty().uppercase(), style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFFD5B477))
            }
            Text(card.title, style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Black,
                color = Color.White, maxLines = 4, overflow = TextOverflow.Ellipsis)
            Text(if (countries.isBlank()) "Общая памятка · без привязки к стране" else countries,
                style = MaterialTheme.typography.bodySmall, color = Color(0xFFD7DDD2))
        }
    }
}

@Composable
private fun QuickAction(label: String, icon: Int, modifier: Modifier = Modifier, enabled: Boolean = true, onClick: () -> Unit) {
    val haptics = LocalHapticFeedback.current
    FilledTonalButton(onClick = {
        haptics.performHapticFeedback(HapticFeedbackType.LongPress)
        onClick()
    }, modifier = modifier, enabled = enabled, contentPadding = PaddingValues(horizontal = 10.dp, vertical = 12.dp)) {
        Icon(painterResource(icon), contentDescription = null, Modifier.size(19.dp))
        Spacer(Modifier.width(7.dp))
        Text(label, maxLines = 1, style = MaterialTheme.typography.labelMedium)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun QuickRecognitionSheet(card: CardEntity, blocks: List<String>, onDismiss: () -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(Modifier.fillMaxWidth().padding(start = 20.dp, end = 20.dp, bottom = 28.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("БЫСТРАЯ СВЕРКА", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            Text(card.title, style = MaterialTheme.typography.headlineSmall)
            if (blocks.isEmpty()) Text(card.summary, style = MaterialTheme.typography.bodyLarge)
            else blocks.forEach { Text(it, style = MaterialTheme.typography.bodyLarge) }
            Text("Используйте полную карточку и источники для проверки контекста.", style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ComparisonSheet(card: CardEntity, related: List<CardEntity>, onDismiss: () -> Unit) {
    var selected by remember(related) { mutableStateOf(related.first()) }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 28.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("БЫСТРОЕ СРАВНЕНИЕ", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                CompareColumn(card, Modifier.weight(1f))
                CompareColumn(selected, Modifier.weight(1f))
            }
            Text("Сравнить с", style = MaterialTheme.typography.titleSmall)
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(related, key = { it.id }) { option ->
                    FilterChip(selected = option.id == selected.id, onClick = { selected = option },
                        label = { Text(option.title, maxLines = 1) })
                }
            }
            Text("Сравнение помогает заметить различия в описаниях; окончательную проверку делайте по источникам.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun CompareColumn(card: CardEntity, modifier: Modifier = Modifier) {
    val facts = remember(card.id, card.body) { comparisonFacts(card.body) }
    OutlinedCard(modifier) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(card.title, style = MaterialTheme.typography.titleSmall)
            Text(card.summary, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            facts.forEach { fact ->
                HorizontalDivider()
                Text(fact.first, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(fact.second, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

private fun comparisonFacts(body: String): List<Pair<String, String>> = body.lineSequence()
    .map(String::trim)
    .filter { it.startsWith("|") && it.endsWith("|") }
    .map { row -> row.trim('|').split('|').map(String::trim) }
    .filter { it.size >= 2 && it[0].isNotBlank() && it[1].isNotBlank() && !it[0].all { ch -> ch == '-' || ch == ':' } }
    .map { it[0] to it[1] }
    .filterNot { (label, _) -> label.equals("Параметр", true) || label.equals("Характеристика", true) }
    .distinctBy { it.first.lowercase() }
    .take(6).toList()

private fun readerParagraphs(paragraphs: List<String>, mortar: Boolean): List<String> {
    val hidden = setOf("Статус проверки") + (if (mortar) setOf(
        "Основание", "Признаки распознавания", "Фото и визуальная сверка", "Границы карточки"
    ) else emptySet())
    var skip = false
    return paragraphs.filter { paragraph ->
        val block = ReferenceBodyParser.parseBlock(paragraph)
        if (block.kind == ReferenceBodyParser.Kind.HEADING) skip = block.text in hidden
        !skip
    }
}

private fun recognitionBlocks(paragraphs: List<String>): List<String> {
    val start = paragraphs.indexOfFirst { it.trim().startsWith("Признаки распознавания", ignoreCase = true) }
    if (start < 0) return emptyList()
    return paragraphs.drop(start + 1).takeWhile {
        ReferenceBodyParser.parseBlock(it).kind != ReferenceBodyParser.Kind.HEADING
    }.filter { it.isNotBlank() }.take(5)
}

// Same slice-a-section technique as recognitionBlocks, anchored on the "## При обнаружении" heading
// instead: that section is the one piece of a card most worth carrying into a share, since it is
// the actual safety instruction rather than identification detail.
private fun findingsSection(paragraphs: List<String>): String? {
    val start = paragraphs.indexOfFirst {
        val block = ReferenceBodyParser.parseBlock(it)
        block.kind == ReferenceBodyParser.Kind.HEADING && block.text.equals("При обнаружении", ignoreCase = true)
    }
    if (start < 0) return null
    val body = paragraphs.drop(start + 1).takeWhile {
        ReferenceBodyParser.parseBlock(it).kind != ReferenceBodyParser.Kind.HEADING
    }.filter { it.isNotBlank() }
    return body.joinToString("\n\n").trim().takeIf { it.isNotEmpty() }
}

// Plain text only: the share target may be SMS, a messenger, or a radio operator reading it aloud,
// none of which can be assumed to render Markdown. No link is included because the app is offline
// by design and has nothing to link to.
private fun buildShareText(card: CardEntity, paragraphs: List<String>): String = buildString {
    append(card.title)
    if (card.summary.isNotBlank()) { append("\n\n"); append(card.summary) }
    findingsSection(paragraphs)?.let { append("\n\nПри обнаружении:\n"); append(it) }
    append("\n\nОфлайн-справочник «ДЛЯ СВОИХ». Отправлено без интернета — прямой ссылки на карточку нет.")
}

@Composable
private fun SourcesCard(sources: List<ru.dlyasvoih.app.data.local.SourceEntity>, sourceGrade: String, verifiedAt: String?) {
    var expanded by remember { mutableStateOf(false) }
    val uriHandler = LocalUriHandler.current
    OutlinedCard(Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Источники", style = MaterialTheme.typography.titleMedium)
                    Text("${sources.size} ссылок и документов", style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                TextButton(onClick = { expanded = !expanded }) { Text(if (expanded) "Свернуть" else "Показать") }
            }
            if (expanded) sources.forEachIndexed { index, source ->
                if (index > 0) HorizontalDivider()
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(source.title, style = MaterialTheme.typography.bodyMedium)
                    val url = source.url
                    if (url != null) {
                        TextButton(onClick = { uriHandler.openUri(url) }, contentPadding = PaddingValues(0.dp)) {
                            Text("Открыть источник", style = MaterialTheme.typography.bodySmall)
                        }
                    } else {
                        // Part of the catalog rests on documents that are not published on the web.
                        // Saying so is honest; an entry that merely looks like a dead link is not.
                        Text("Офлайн-источник: ссылки нет, сверяйте по самому документу",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    source.accessedAt?.let { Text("Проверено: $it", style = MaterialTheme.typography.labelSmall) }
                }
            }
        }
    }
}

private fun sourceGradeLabel(value: String): String = when (value) {
    "A" -> "A · первичный или официальный"
    "B" -> "B · профильный справочник"
    else -> "архивная редакционная запись"
}

/** Parsing changes presentation only: each old paragraph still occupies one lazy item. */
@Composable
private fun ReferenceBodyBlock(paragraph: String) {
    val block = remember(paragraph) { ReferenceBodyParser.parseBlock(paragraph) }
    SelectionContainer {
        when (block.kind) {
            ReferenceBodyParser.Kind.HEADING -> Text(block.text, modifier = Modifier.fillMaxWidth().semantics { heading() },
                style = MaterialTheme.typography.titleLarge)
            ReferenceBodyParser.Kind.TABLE -> ReferenceTable(block)
            else -> Text(block.text, style = MaterialTheme.typography.bodyLarge)
        }
    }
}

@Composable
private fun ReferenceTable(block: ReferenceBodyParser.Block) {
    val fontScale = LocalDensity.current.fontScale
    OutlinedCard(Modifier.fillMaxWidth()) {
        BoxWithConstraints(Modifier.fillMaxWidth().padding(horizontal = 14.dp)) {
            val stacked = maxWidth / fontScale < 340.dp
            Column(Modifier.fillMaxWidth()) {
                if (stacked) {
                    Text("${block.header.label} — ${block.header.value}", Modifier.fillMaxWidth().padding(vertical = 12.dp),
                        style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    HorizontalDivider()
                } else {
                    Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        Text(block.header.label, Modifier.weight(1f), style = MaterialTheme.typography.titleSmall)
                        Text(block.header.value, Modifier.weight(1f), style = MaterialTheme.typography.titleSmall)
                    }
                    HorizontalDivider()
                }
                block.rows.forEachIndexed { index, row ->
                    if (index > 0) HorizontalDivider()
                    if (stacked) {
                        Column(Modifier.fillMaxWidth().padding(vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(row.label, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(row.value, style = MaterialTheme.typography.bodyLarge)
                        }
                    } else {
                        Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                            Text(row.label, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(row.value, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun GalleryScreen(vm: GalleryViewModel, initialIndex: Int, onBack: () -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val images = (state as? DataState.Ready<List<ImageEntity>>)?.value.orEmpty()
    Scaffold(topBar = { GuideBar("Изображения", onBack) }) { padding ->
        when {
            state == DataState.Loading -> StatusPanel("Открываем изображения…", Modifier.padding(padding), loading = true)
            state == DataState.Error -> StatusPanel("Не удалось загрузить изображения", Modifier.padding(padding), retry = vm::retry)
            images.isEmpty() -> StatusPanel("Изображений нет", Modifier.padding(padding))
            else -> {
                val pager = rememberPagerState(initialPage = initialIndex.coerceIn(images.indices)) { images.size }
                Column(Modifier.fillMaxSize().padding(padding)) {
                    HorizontalPager(pager, modifier = Modifier.weight(1f), key = { images[it].id }) { index ->
                        ZoomableGuideImage(images[index], Modifier.fillMaxSize().padding(10.dp))
                    }
                    val current = pager.currentPage.coerceIn(images.indices)
                    Text("${current + 1} / ${images.size} · ${imageKindLabel(images[current].caption)}\n" +
                        "${images[current].caption}\n${imageRightsLabel(images[current].caption)}\n" +
                        "Щипок — масштаб, двойное касание — приблизить",
                        Modifier.padding(18.dp), style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
    }
}

private fun imageKindLabel(caption: String): String {
    val text = caption.lowercase()
    return when {
        "3d" in text || "макет" in text -> "Учебный макет / реконструкция"
        "иллюстрац" in text || "схем" in text || "рисунок" in text -> "Техническая иллюстрация"
        "семейн" in text || "ориентир" in text -> "Семейный визуальный ориентир"
        else -> "Справочная фотография"
    }
}

private fun imageRightsLabel(caption: String): String {
    val text = caption.lowercase()
    return when {
        "public domain" in text || "общественн" in text && "достояни" in text -> "Права: Public Domain / общественное достояние"
        "cc by-sa 4" in text -> "Лицензия: CC BY-SA 4.0"
        "cc by 4" in text -> "Лицензия: CC BY 4.0"
        "cc by-sa 3" in text -> "Лицензия: CC BY-SA 3.0"
        "cc by 3" in text -> "Лицензия: CC BY 3.0"
        "предоставлен" in text && "пользовател" in text -> "Права: предоставлено пользователем для проекта"
        else -> "Права: сверяйте условия в указанном источнике"
    }
}

@Composable
private fun ZoomableGuideImage(image: ImageEntity, modifier: Modifier = Modifier) {
    var scale by remember(image.id) { mutableFloatStateOf(1f) }
    var offsetX by remember(image.id) { mutableFloatStateOf(0f) }
    var offsetY by remember(image.id) { mutableFloatStateOf(0f) }
    var size by remember(image.id) { mutableStateOf(IntSize.Zero) }
    val haptics = LocalHapticFeedback.current
    fun clampOffsets() {
        val maxX = max(0f, (scale - 1f) * size.width / 2f)
        val maxY = max(0f, (scale - 1f) * size.height / 2f)
        offsetX = offsetX.coerceIn(-maxX, maxX)
        offsetY = offsetY.coerceIn(-maxY, maxY)
    }
    Box(modifier.clip(RoundedCornerShape(16.dp)).background(Color.Black), contentAlignment = Alignment.Center) {
        LocalGuideImage(image.localPath, image.caption,
            Modifier.fillMaxSize().onSizeChanged { size = it }
                .pointerInput(image.id) {
                    detectTapGestures(onDoubleTap = {
                        scale = if (scale > 1f) 1f else 2.5f
                        if (scale == 1f) { offsetX = 0f; offsetY = 0f }
                        haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                    })
                }
                .pointerInput(image.id) {
                    detectTransformGestures { _, pan, zoom, _ ->
                        scale = (scale * zoom).coerceIn(1f, 4f)
                        if (scale == 1f) { offsetX = 0f; offsetY = 0f }
                        else { offsetX += pan.x; offsetY += pan.y; clampOffsets() }
                    }
                }
                .graphicsLayer { scaleX = scale; scaleY = scale; translationX = offsetX; translationY = offsetY }, fit = true)
    }
}
