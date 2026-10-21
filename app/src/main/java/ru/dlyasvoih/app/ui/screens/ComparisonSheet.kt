package ru.dlyasvoih.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.ScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import ru.dlyasvoih.app.data.CatalogSearch
import ru.dlyasvoih.app.data.local.CardEntity
import ru.dlyasvoih.app.data.local.CardPreview
import ru.dlyasvoih.app.ui.content.ComparisonContent

private data class ComparisonData(val cards: List<CardEntity>, val rows: List<ComparisonContent.TableRow>)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun ComparisonSheet(card: CardEntity, related: List<CardPreview>,
    loadCard: suspend (String) -> CardEntity?, onDismiss: () -> Unit) {
    val options = remember(card.id, card.section, card.categoryId, related) {
        related.filter { it.id != card.id && it.section == card.section && it.categoryId == card.categoryId }.distinctBy { it.id }
    }
    var selectedIds by rememberSaveable(card.id) { mutableStateOf(options.take(1).map { it.id }) }
    var choosing by rememberSaveable(card.id) { mutableStateOf(false) }
    var retry by remember { mutableIntStateOf(0) }
    LaunchedEffect(options) {
        val valid = selectedIds.filter { id -> options.any { it.id == id } }.take(2)
        selectedIds = valid.ifEmpty { options.take(1).map { it.id } }
    }
    val data by produceState<ComparisonData?>(null, card.id, card.body, selectedIds, retry) {
        value = null
        try {
            val selected = selectedIds.mapNotNull { id -> loadCard(id)?.takeIf {
                !it.archived && it.id == id && it.section == card.section && it.categoryId == card.categoryId
            } }
            if (selected.size != selectedIds.size || selected.isEmpty()) {
                value = ComparisonData(emptyList(), emptyList())
            } else {
                val cards = listOf(card) + selected
                value = withContext(Dispatchers.Default) {
                    ComparisonData(cards, ComparisonContent.table(cards.map { it.body }))
                }
            }
        } catch (cancelled: CancellationException) { throw cancelled }
        catch (error: Exception) {
            android.util.Log.e("Guide", "Comparison loading failed", error)
            value = ComparisonData(emptyList(), emptyList())
        }
    }
    ModalBottomSheet(onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.fillMaxWidth().fillMaxHeight(0.92f)) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Сравнение", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                TextButton(onClick = { choosing = true }, modifier = Modifier.testTag("comparison_choose"), enabled = options.isNotEmpty()) {
                    Text("Выбрать карточки")
                }
            }
            Text(if (selectedIds.size == 2) "3 карточки · таблицу можно сдвигать вбок" else "2 карточки одной категории",
                Modifier.padding(horizontal = 16.dp, vertical = 4.dp), style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
            val ready = data
            if (ready == null) {
                Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            } else if (ready.cards.isEmpty()) {
                Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(if (options.isEmpty()) "В этой категории нет других карточек." else "Не удалось загрузить выбранные карточки.")
                    if (options.isNotEmpty()) Button(onClick = { retry++ }) { Text("Повторить") }
                }
            } else {
                ComparisonTable(ready, onRemove = { id -> selectedIds = selectedIds.filterNot { it == id } })
            }
        }
    }
    if (choosing) ComparisonPicker(options, selectedIds, onDismiss = { choosing = false }) {
        selectedIds = it
        choosing = false
    }
}

@Composable
private fun ColumnScope.ComparisonTable(data: ComparisonData, onRemove: (String) -> Unit) {
    val horizontal = rememberScrollState()
    val vertical = key(data.cards.map { it.id }) { rememberLazyListState() }
    var summaries by rememberSaveable(data.cards.map { it.id }) { mutableStateOf(data.rows.isEmpty()) }
    BoxWithConstraints(Modifier.weight(1f).fillMaxWidth()) {
        val count = data.cards.size
        val columnWidth = maxOf(148.dp, (maxWidth - 32.dp - 12.dp * (count - 1)) / count)
        val tableWidth = columnWidth * count + 12.dp * (count - 1) + 32.dp
        val labelWidth = maxWidth - 32.dp
        Column(Modifier.horizontalScroll(horizontal).width(tableWidth).fillMaxHeight().testTag("comparison_columns")) {
            Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                data.cards.forEachIndexed { index, card ->
                    Column(Modifier.width(columnWidth).testTag("comparison_header_$index"), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Box(Modifier.fillMaxWidth().height(56.dp).clip(RoundedCornerShape(10.dp)).background(Color.White), contentAlignment = Alignment.Center) {
                            if (card.thumbnailPath != null) LocalGuideImage(card.thumbnailPath, card.title, Modifier.fillMaxSize(), fit = true)
                            else Text("Нет изображения", style = MaterialTheme.typography.labelSmall, color = Color.DarkGray)
                        }
                        Text(card.title, style = MaterialTheme.typography.titleSmall, maxLines = 4, overflow = TextOverflow.Ellipsis)
                        if (index == 0) Text("Основная карточка", Modifier.heightIn(min = 32.dp),
                            style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                        else TextButton(onClick = { onRemove(card.id) }, enabled = count == 3,
                            modifier = Modifier.heightIn(min = 32.dp).testTag("comparison_remove_$index"),
                            contentPadding = PaddingValues(horizontal = 0.dp)) {
                            Text(if (count == 3) "Убрать" else "Выбрана", style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
            HorizontalDivider()
            LazyColumn(Modifier.weight(1f).fillMaxWidth().testTag("comparison_table"), state = vertical,
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 28.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if (data.rows.isNotEmpty()) item {
                    TextButton(onClick = { summaries = !summaries },
                        modifier = Modifier.offset { IntOffset(horizontal.value, 0) }, contentPadding = PaddingValues(0.dp)) {
                        Text(if (summaries) "Скрыть описания" else "Показать описания")
                    }
                }
                if (summaries) item { ComparisonRow("Описание", data.cards.map { it.summary }, columnWidth, "summary", labelWidth, horizontal) }
                items(data.rows.size) { index ->
                    val row = data.rows[index]
                    ComparisonRow(row.label, row.values, columnWidth, index.toString(), labelWidth, horizontal)
                }
                if (data.rows.isEmpty()) item {
                    Text("В карточках нет таблиц характеристик. Показаны описания.",
                        Modifier.width(labelWidth).offset { IntOffset(horizontal.value, 0) }, style = MaterialTheme.typography.bodySmall)
                }
                item {
                    Text("«Нет данных в карточке» означает, что значение не указано. Единицы измерения сохранены по источникам.",
                        modifier = Modifier.width(labelWidth).offset { IntOffset(horizontal.value, 0) },
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun ComparisonRow(label: String, values: List<String?>, width: Dp, key: String, labelWidth: Dp, horizontal: ScrollState) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(label, Modifier.width(labelWidth).offset { IntOffset(horizontal.value, 0) }.testTag("comparison_label_$key"),
            style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            values.forEachIndexed { index, value ->
                val suffix = when (index) { 0 -> "left"; 1 -> "right"; else -> "third" }
                Text(value ?: "Нет данных в карточке", Modifier.width(width).testTag("comparison_${key}_$suffix"),
                    style = MaterialTheme.typography.bodySmall)
            }
        }
        HorizontalDivider()
    }
}

@Composable
private fun ComparisonPicker(options: List<CardPreview>, selected: List<String>, onDismiss: () -> Unit,
    onApply: (List<String>) -> Unit) {
    var query by rememberSaveable { mutableStateOf("") }
    var chosen by rememberSaveable { mutableStateOf(selected) }
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current
    val dismiss = { focus.clearFocus(); keyboard?.hide(); onDismiss() }
    val indexed = remember(options) { options.map { it to CatalogSearch.normalize(it.title) } }
    val matches = remember(indexed, query) {
        val words = CatalogSearch.normalize(query).split(' ').filter { it.isNotBlank() }
        indexed.filter { (_, title) -> words.all { it in title } }.map { it.first }
    }
    // Let WindowInsets and adjustResize account for the IME on legacy Android
    // as well; a floating decor-fitted window can leave Apply behind the IME.
    Dialog(onDismissRequest = dismiss, properties = DialogProperties(usePlatformDefaultWidth = false,
        decorFitsSystemWindows = false)) {
        Surface(Modifier.imePadding().systemBarsPadding().fillMaxWidth(0.96f).fillMaxHeight(0.88f), shape = RoundedCornerShape(24.dp)) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Выбор карточек", style = MaterialTheme.typography.titleLarge)
                OutlinedTextField(query, onValueChange = { query = it.take(120) }, Modifier.fillMaxWidth().testTag("comparison_search"),
                    label = { Text("Поиск по названию") }, singleLine = true)
                LazyColumn(Modifier.weight(1f).fillMaxWidth().testTag("comparison_options")) {
                    item(key = "comparison_heading") {
                        Text("Одна или две карточки из текущей категории", Modifier.padding(bottom = 10.dp),
                            style = MaterialTheme.typography.bodySmall)
                    }
                    item(key = "comparison_chosen") {
                        LazyRow(Modifier.padding(bottom = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            items(options.filter { it.id in chosen }, key = { it.id }) { option ->
                                InputChip(selected = true, onClick = { chosen = chosen - option.id }, label = { Text(option.title + " ×", maxLines = 1) })
                            }
                        }
                    }
                    items(matches, key = { it.id }) { option ->
                        val checked = option.id in chosen
                        val enabled = checked || chosen.size < 2
                        Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).testTag("comparison_option_" + option.id)
                            .toggleable(value = checked, enabled = enabled, role = Role.Checkbox) {
                                chosen = if (checked) chosen - option.id else chosen + option.id
                            }.padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = checked, onCheckedChange = null, enabled = enabled)
                            Spacer(Modifier.width(8.dp))
                            Text(option.title, Modifier.weight(1f), maxLines = 3, overflow = TextOverflow.Ellipsis,
                                color = if (enabled) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    if (matches.isEmpty()) item { Text("Карточки не найдены", Modifier.padding(vertical = 20.dp)) }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = dismiss) { Text("Отмена") }
                    Button(onClick = { focus.clearFocus(); keyboard?.hide(); onApply(chosen) }, enabled = chosen.isNotEmpty(), modifier = Modifier.testTag("comparison_apply")) {
                        Text("Сравнить · ${chosen.size + 1}")
                    }
                }
            }
        }
    }
}
