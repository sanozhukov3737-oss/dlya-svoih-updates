package ru.dlyasvoih.app.ui.screens

import androidx.activity.compose.ReportDrawnWhen
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.dlyasvoih.app.R
import ru.dlyasvoih.app.data.MainSection
import ru.dlyasvoih.app.data.update.RemoteUpdateState
import ru.dlyasvoih.app.data.update.AppUpdateState
import ru.dlyasvoih.app.data.local.CardPreview
import ru.dlyasvoih.app.ui.CatalogHierarchy
import ru.dlyasvoih.app.ui.OverviewViewModel
import ru.dlyasvoih.app.ui.theme.LocalAtlasAppearance
import ru.dlyasvoih.app.ui.theme.THEME_DARK
import ru.dlyasvoih.app.ui.theme.THEME_LIGHT
import ru.dlyasvoih.app.ui.theme.THEME_SYSTEM

@Composable
fun OverviewScreen(
    vm: OverviewViewModel,
    section: String = "",
    onBack: (() -> Unit)? = null,
    onSection: (MainSection) -> Unit = {},
    onCategory: (String) -> Unit = {},
    onOpenCard: (String) -> Unit = {},
    onUpdate: () -> Unit = {},
    onSearch: () -> Unit = {},
    group: String = "",
    onGroup: (String) -> Unit = {}
) {
    val state by vm.state.collectAsStateWithLifecycle()
    val onlineUpdate by vm.remoteUpdates.collectAsStateWithLifecycle()
    val appUpdate by vm.appUpdates.collectAsStateWithLifecycle()
    val isHome = section.isEmpty()
    val categoryById = remember(state.categories) { state.categories.associateBy { it.id } }
    val ammunitionIds = remember(state.categories) {
        state.categories.filter { it.section == MainSection.AMMUNITION.name }.map { it.id }
    }
    val visibleIds = remember(state.categories, section, group) {
        when {
            group == CatalogHierarchy.ENGINEERING_GROUP -> CatalogHierarchy.engineeringIds(ammunitionIds)
            group == CatalogHierarchy.INITIATION_GROUP -> CatalogHierarchy.initiationIds(ammunitionIds)
            isHome || section == MainSection.AMMUNITION.name -> CatalogHierarchy.rootIds(ammunitionIds)
            else -> state.categories.filter { it.section == section }.map { it.id }
        }
    }
    ReportDrawnWhen { !state.loading && !state.error }
    val title = when (group) {
        CatalogHierarchy.ENGINEERING_GROUP -> "Инженерные боеприпасы"
        CatalogHierarchy.INITIATION_GROUP -> "Средства взрывания"
        else -> MainSection.fromId(section)?.title ?: "ДЛЯ СВОИХ"
    }
    var appearanceOpen by rememberSaveable { mutableStateOf(false) }
    var aboutOpen by rememberSaveable { mutableStateOf(false) }
    var menuOpen by remember { mutableStateOf(false) }
    Scaffold(topBar = {
        GuideBar(title, onBack) {
            IconButton(onClick = onSearch, modifier = Modifier.testTag("search_icon")) {
                Icon(painterResource(R.drawable.icon_ui_search), contentDescription = "Открыть поиск")
            }
            if (isHome) {
                Box(Modifier.wrapContentSize(Alignment.TopEnd)) {
                    IconButton(onClick = { menuOpen = true }, modifier = Modifier.testTag("home_menu_button")) {
                        Icon(painterResource(R.drawable.icon_ui_more), contentDescription = "Открыть меню")
                    }
                    DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                        DropdownMenuItem(text = { Text(if (onlineUpdate is RemoteUpdateState.Available ||
                            (onlineUpdate as? RemoteUpdateState.Error)?.catalog != null ||
                            appUpdate is AppUpdateState.Available || appUpdate is AppUpdateState.Ready ||
                            (appUpdate as? AppUpdateState.Error)?.app != null)
                            "Обновления · доступно" else "Обновления") },
                            modifier = Modifier.testTag("home_menu_update"),
                            onClick = { menuOpen = false; onUpdate() })
                        DropdownMenuItem(text = { Text("Тема и размер текста") },
                            modifier = Modifier.testTag("home_menu_appearance"),
                            onClick = { menuOpen = false; appearanceOpen = true })
                        DropdownMenuItem(text = { Text("О приложении") },
                            modifier = Modifier.testTag("home_menu_about"),
                            onClick = { menuOpen = false; aboutOpen = true })
                    }
                }
            }
        }
    }) { padding ->
        when {
            state.loading -> StatusPanel("Открываем каталог…", Modifier.padding(padding), loading = true)
            state.error -> StatusPanel("Не удалось прочитать каталог", Modifier.padding(padding), retry = vm::retry)
            else -> LazyColumn(
                Modifier.fillMaxSize().padding(padding).testTag("home_list"),
                contentPadding = PaddingValues(start = 14.dp, end = 14.dp, bottom = 28.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                if (isHome) {
                    if (state.favoriteCards.isNotEmpty()) item(key = "favorites") {
                        PreviewShelf("Избранное", state.favoriteCards, onOpenCard)
                    }
                    item(key = "section_title") {
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text("РАЗДЕЛЫ", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                            Text("Полевой каталог", style = MaterialTheme.typography.headlineMedium)
                        }
                    }
                } else {
                    item(key = "intro") {
                        Text(if (group.isNotEmpty()) "Выберите тип" else "Категории", style = MaterialTheme.typography.headlineSmall)
                    }
                    if (group.isEmpty()) item(key = "all") {
                        CatalogMenuRow("@all", "Все материалы раздела", "Общий список", state.counts[section]) { onCategory("") }
                    }
                }

                val entries = visibleIds.map { id ->
                    val children = when (id) {
                        CatalogHierarchy.ENGINEERING_GROUP -> CatalogHierarchy.engineeringIds(ammunitionIds)
                        CatalogHierarchy.INITIATION_GROUP -> CatalogHierarchy.initiationIds(ammunitionIds)
                        else -> emptyList()
                    }
                    val categoryTitle = when (id) {
                        CatalogHierarchy.ENGINEERING_GROUP -> "Инженерные боеприпасы"
                        CatalogHierarchy.INITIATION_GROUP -> "Средства взрывания"
                        "fuzes", "engineering" -> "Общие сведения"
                        "ied" -> "СВУ"
                        else -> categoryById[id]?.title ?: id
                    }
                    val total = if (children.isNotEmpty()) children.sumOf { state.categoryCounts[it] ?: 0 }
                        else state.categoryCounts[id] ?: 0
                    MenuEntry(id, categoryTitle, CatalogHierarchy.subtitle(id), total, children.isNotEmpty())
                } + if (isHome) MainSection.entries.filter { it != MainSection.AMMUNITION }.map {
                    MenuEntry(it.name, it.title, it.subtitle, state.counts[it.name] ?: 0, false, it)
                } else emptyList()

                if (isHome) {
                    items(entries.chunked(2), key = { row -> row.joinToString("|") { it.id } }) { row ->
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            row.forEach { entry ->
                                CatalogMenuTile(entry.id, entry.title, entry.count, Modifier.weight(1f)) {
                                    when {
                                        entry.section != null -> onSection(entry.section)
                                        entry.hasChildren -> onGroup(entry.id)
                                        else -> onCategory(entry.id)
                                    }
                                }
                            }
                            if (row.size == 1) Spacer(Modifier.weight(1f))
                        }
                    }
                } else {
                    items(entries, key = { "category:${it.id}" }) { entry ->
                        CatalogMenuRow(entry.id, entry.title, entry.subtitle, entry.count) {
                            if (entry.hasChildren) onGroup(entry.id) else onCategory(entry.id)
                        }
                    }
                }
            }
        }
    }
    if (appearanceOpen) AppearanceDialog { appearanceOpen = false }
    if (aboutOpen) AboutDialog(state.contentVersion,
        if (state.loading || state.error) null else state.counts.values.sum()) { aboutOpen = false }
}

@Composable
private fun AboutDialog(contentVersion: String, total: Int?, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val appVersion = remember(context) {
        runCatching { context.packageManager.getPackageInfo(context.packageName, 0).versionName }
            .getOrNull().orEmpty().ifBlank { "—" }
    }
    AlertDialog(onDismissRequest = onDismiss, modifier = Modifier.testTag("about_dialog"),
        title = { Text("ДЛЯ СВОИХ") }, text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Офлайн-справочник с фотографиями, описаниями, техническими характеристиками и ссылками на источники.")
                Text("Разделы: боеприпасы, ПТРК, СВО и медицина.")
                HorizontalDivider()
                Text("Карточек в каталоге: ${total?.toString() ?: "—"}", Modifier.testTag("about_card_count"))
                Text("Версия каталога: ${contentVersion.ifBlank { "—" }}")
                Text("Версия приложения: $appVersion")
                Text("Каталог и встроенные фотографии доступны без подключения к интернету.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }, confirmButton = { TextButton(onClick = onDismiss) { Text("Закрыть") } })
}

private data class MenuEntry(
    val id: String,
    val title: String,
    val subtitle: String,
    val count: Int,
    val hasChildren: Boolean,
    val section: MainSection? = null
)

@Composable
private fun PreviewShelf(title: String, cards: List<CardPreview>, onOpen: (String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
        Text(title, style = MaterialTheme.typography.titleLarge)
        LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(end = 12.dp)) {
            items(cards, key = { it.id }) { card -> AtlasPreviewCard(card) { onOpen(card.id) } }
        }
    }
}

@Composable
private fun CatalogMenuTile(iconKey: String, title: String, count: Int, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = modifier.height(154.dp).testTag("menu:$iconKey"), shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)) {
        Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.SpaceBetween) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Top) {
                CatalogMenuIcon(iconKey, Modifier.size(52.dp))
                Text(count.toString(), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            }
            Text(title, style = MaterialTheme.typography.titleSmall, maxLines = 3, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
fun CatalogMenuRow(iconKey: String, title: String, subtitle: String, count: Int? = null, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth().testTag("menu:$iconKey"), shape = RoundedCornerShape(17.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            CatalogMenuIcon(iconKey, Modifier.size(56.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (count != null) Text("$count карточек", style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary)
            }
            Text("›", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun AppearanceDialog(onDismiss: () -> Unit) {
    val appearance = LocalAtlasAppearance.current
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Вид приложения") }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Тема", style = MaterialTheme.typography.labelLarge)
            listOf(THEME_SYSTEM to "Как в системе", THEME_LIGHT to "Светлая", THEME_DARK to "Тёмная").forEach { (mode, label) ->
                Row(Modifier.fillMaxWidth().clickable { appearance.setThemeMode(mode) }.padding(vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(appearance.themeMode == mode, onClick = null)
                    Text(label)
                }
            }
            HorizontalDivider()
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Крупный режим", style = MaterialTheme.typography.titleSmall)
                    Text("Увеличивает текст и подписи", style = MaterialTheme.typography.bodySmall)
                }
                Switch(appearance.largeMode, appearance.setLargeMode)
            }
        }
    }, confirmButton = { TextButton(onClick = onDismiss) { Text("Готово") } })
}
