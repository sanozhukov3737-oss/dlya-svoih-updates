package ru.dlyasvoih.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.dlyasvoih.app.data.CountrySelection
import ru.dlyasvoih.app.R
import ru.dlyasvoih.app.ui.CountryMenuViewModel

@Composable
fun CountryMenuScreen(vm: CountryMenuViewModel, onBack: () -> Unit, onSearch: () -> Unit, onCountry: (String) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    Scaffold(topBar = {
        GuideBar(state.title.ifBlank { "Выбор страны" }, onBack) {
            IconButton(onClick = onSearch, modifier = Modifier.testTag("search_icon")) {
                Icon(painterResource(R.drawable.icon_ui_search), contentDescription = "Открыть поиск")
            }
        }
    }) { padding ->
        when {
            state.loading -> StatusPanel("Открываем страны…", Modifier.padding(padding), loading = true)
            state.error -> StatusPanel("Не удалось прочитать список стран", Modifier.padding(padding), retry = vm::retry)
            else -> LazyColumn(Modifier.fillMaxSize().padding(padding).testTag("country_list"),
                contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                item(key = "heading") {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                        CatalogMenuIcon(vm.category.ifBlank { vm.section }, Modifier.size(64.dp))
                        Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                            Text("Выберите страну", style = MaterialTheme.typography.headlineSmall)
                            Text("Показаны страны, для которых есть карточки.", style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
                item(key = "all") {
                    CountryMenuRow("", "Все страны", state.total,
                        "Включая общие материалы без привязки к стране") { onCountry("") }
                }
                items(state.countries, key = { it.id }) { country ->
                    CountryMenuRow(country.id, country.name, country.total,
                        if (country.id == CountrySelection.USSR_AND_RUSSIA)
                            "Общий список советских и российских моделей без дублей" else null
                    ) { onCountry(country.id) }
                }
                if (state.total == 0) item(key = "empty") {
                    Text("Карточки этого типа пока не добавлены.", style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
    }
}

@Composable
private fun CountryMenuRow(id: String, title: String, total: Int, subtitle: String? = null, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth().testTag("country:$id")) {
        Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                subtitle?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                Text("Карточек: $total", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
            }
            Text("›", fontSize = 28.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
