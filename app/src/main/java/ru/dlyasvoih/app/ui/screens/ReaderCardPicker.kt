package ru.dlyasvoih.app.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import ru.dlyasvoih.app.data.local.ReaderCard
import ru.dlyasvoih.app.ui.ReaderIndex

@Composable
internal fun ReaderCardPicker(cards: List<ReaderCard>, currentPage: Int,
    onChoose: (Int) -> Unit, onDismiss: () -> Unit) {
    var query by rememberSaveable { mutableStateOf("") }
    val index = remember(cards) { ReaderIndex(cards.map { it.title }) }
    val matches = remember(index, query) { index.find(query) }
    val list = rememberLazyListState()
    LaunchedEffect(query) {
        if (matches.isNotEmpty()) list.scrollToItem(if (query.isBlank())
            (currentPage - 1).coerceIn(0, matches.lastIndex) else 0)
    }
    AlertDialog(onDismissRequest = onDismiss, modifier = Modifier.testTag("reader_picker"),
        title = { Text("Перейти к карточке") }, text = {
            Column(Modifier.fillMaxWidth().heightIn(max = 420.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(value = query, onValueChange = { query = it.take(160) },
                    label = { Text("Название или номер") }, singleLine = true,
                    modifier = Modifier.fillMaxWidth().testTag("reader_picker_query"))
                Text("Найдено: ${matches.size} из ${cards.size}", style = MaterialTheme.typography.labelMedium)
                if (matches.isEmpty()) Text("Карточки не найдены. Проверьте название или номер.")
                else LazyColumn(state = list, modifier = Modifier.fillMaxWidth().weight(1f, fill = false)
                    .testTag("reader_picker_list")) {
                    items(matches, key = { cards[it].id }) { position ->
                        ListItem(headlineContent = { Text("${position + 1}. ${cards[position].title}") },
                            supportingContent = if (position + 1 == currentPage) ({ Text("Открыта сейчас") }) else null,
                            colors = ListItemDefaults.colors(containerColor = if (position + 1 == currentPage)
                                MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surface),
                            modifier = Modifier.clickable { onChoose(position) }
                                .testTag("reader_choose_${cards[position].id}"))
                    }
                }
            }
        }, confirmButton = { TextButton(onClick = onDismiss) { Text("Закрыть") } })
}
