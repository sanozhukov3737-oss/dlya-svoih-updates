package ru.dlyasvoih.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import coil3.request.ImageRequest
import ru.dlyasvoih.app.R
import ru.dlyasvoih.app.data.local.CardPreview
import ru.dlyasvoih.app.data.update.PackFiles
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GuideBar(title: String, onBack: (() -> Unit)? = null, actions: @Composable RowScope.() -> Unit = {}) {
    TopAppBar(
        title = { Text(title, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.ExtraBold) },
        navigationIcon = {
            if (onBack != null) IconButton(onClick = onBack, modifier = Modifier.semantics { contentDescription = "Назад" }) {
                Icon(painterResource(R.drawable.icon_ui_back), contentDescription = null)
            }
        },
        actions = actions,
        colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background)
    )
}

@Composable
fun StatusPanel(text: String, modifier: Modifier = Modifier, loading: Boolean = false, retry: (() -> Unit)? = null) {
    Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(Modifier.padding(24.dp).widthIn(max = 480.dp), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp)) {
            if (loading) CircularProgressIndicator()
            Text(text, style = MaterialTheme.typography.bodyLarge)
            if (retry != null) Button(onClick = retry) { Text("Повторить") }
        }
    }
}

@Composable
fun LocalGuideImage(path: String, description: String, modifier: Modifier = Modifier, fit: Boolean = false) {
    val context = LocalContext.current
    var failed by remember(path) { mutableStateOf(false) }
    var attempt by remember(path) { mutableIntStateOf(0) }
    Box(modifier, contentAlignment = Alignment.Center) {
        if (failed) {
            TextButton(onClick = { attempt++; failed = false }) { Text("Повторить", style = MaterialTheme.typography.labelSmall) }
        } else {
            val model = remember(context, path, attempt) {
                val local: Any? = when {
                    PackFiles.isMediaPath(path) -> "file:///android_asset/$path"
                    path.matches(Regex("packs/[0-9a-f]{64}/(?:images|thumbs)/[a-zA-Z0-9_-]{1,96}\\.(?:webp|png|jpg|jpeg)")) -> File(context.filesDir, path)
                    else -> null
                }
                ImageRequest.Builder(context).data(local).build()
            }
            AsyncImage(model = model, contentDescription = description,
                contentScale = if (fit) ContentScale.Fit else ContentScale.Crop,
                onError = { failed = true }, modifier = Modifier.fillMaxSize())
        }
    }
}

@Composable
fun FavoriteButton(selected: Boolean?, enabled: Boolean = true, onClick: () -> Unit) {
    val label = when (selected) { true -> "Убрать из избранного"; false -> "В избранное"; null -> "Проверяем избранное" }
    val haptics = LocalHapticFeedback.current
    IconButton(onClick = {
        haptics.performHapticFeedback(HapticFeedbackType.LongPress)
        onClick()
    }, enabled = enabled && selected != null, modifier = Modifier.semantics { contentDescription = label }) {
        if (selected == null) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
        else Icon(painterResource(if (selected) R.drawable.icon_ui_star else R.drawable.icon_ui_star_outline),
            contentDescription = null, tint = MaterialTheme.colorScheme.primary)
    }
}

@Composable
fun StatusBadge(contentStatus: String, modelStatus: String, modifier: Modifier = Modifier) {
    val colors = MaterialTheme.colorScheme
    val (container, foreground) = when (contentStatus) {
        "candidate" -> colors.tertiaryContainer to colors.onTertiaryContainer
        "medical_review_required" -> colors.errorContainer to colors.onErrorContainer
        "source_only" -> colors.secondaryContainer to colors.onSecondaryContainer
        else -> colors.primaryContainer to colors.onPrimaryContainer
    }
    Surface(modifier, color = container, contentColor = foreground, shape = RoundedCornerShape(7.dp)) {
        Text(statusLabel(contentStatus, modelStatus).uppercase(), Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            style = MaterialTheme.typography.labelSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

fun statusLabel(contentStatus: String, modelStatus: String): String = when (contentStatus) {
    "candidate" -> candidateLabel(modelStatus)
    "medical_review_required" -> "Требуется медицинская проверка"
    "source_only" -> "По предоставленному источнику"
    "reviewed" -> "Проверено по источникам"
    "verified" -> "Подтверждено по источнику"
    else -> if (modelStatus in setOf("verified-model", "verified-family", "verified-system"))
        "Подтверждено по источнику" else "Справочный материал"
}

@Composable
fun CardRow(card: CardPreview, favorite: Boolean?, busy: Boolean, onOpen: () -> Unit, onFavorite: () -> Unit) {
    Card(onClick = onOpen, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)) {
        Row(Modifier.padding(start = 8.dp, top = 10.dp, bottom = 10.dp, end = 2.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.width(4.dp).height(70.dp).clip(RoundedCornerShape(4.dp)).background(categoryAccent(card.categoryId)))
            CardThumbnail(card, Modifier.size(68.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text(card.title, style = MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Text(card.summary, style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            FavoriteButton(favorite, !busy, onFavorite)
        }
    }
}

@Composable
fun CardGrid(card: CardPreview, favorite: Boolean?, busy: Boolean, onOpen: () -> Unit, onFavorite: () -> Unit) {
    Card(onClick = onOpen, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)) {
        Column {
            Box(Modifier.fillMaxWidth().height(112.dp)) {
                CardThumbnail(card, Modifier.fillMaxSize())
                Box(Modifier.fillMaxWidth().height(4.dp).background(categoryAccent(card.categoryId)).align(Alignment.TopCenter))
                Box(Modifier.align(Alignment.TopEnd).padding(4.dp)) { FavoriteButton(favorite, !busy, onFavorite) }
            }
            Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(card.title, style = MaterialTheme.typography.titleSmall, minLines = 2, maxLines = 3,
                    overflow = TextOverflow.Ellipsis)
                Text(card.summary, style = MaterialTheme.typography.bodySmall, maxLines = 2,
                    overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
fun AtlasPreviewCard(card: CardPreview, modifier: Modifier = Modifier, onOpen: () -> Unit) {
    OutlinedCard(onClick = onOpen, modifier = modifier.width(210.dp), shape = RoundedCornerShape(16.dp)) {
        Column {
            CardThumbnail(card, Modifier.fillMaxWidth().height(94.dp))
            Column(Modifier.padding(11.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text(card.title, style = MaterialTheme.typography.titleSmall, minLines = 2, maxLines = 2,
                    overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

@Composable
private fun CardThumbnail(card: CardPreview, modifier: Modifier) {
    if (card.thumbnailPath != null) {
        Surface(modifier, color = Color.White, shape = RoundedCornerShape(11.dp)) {
            LocalGuideImage(card.thumbnailPath, "Иллюстрация: ${card.title}", Modifier.padding(4.dp), fit = true)
        }
    } else {
        Surface(modifier, color = MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(11.dp)) {
            CatalogMenuIcon(card.categoryId.ifBlank { card.section }, Modifier.padding(12.dp), useRepresentativePhoto = false)
        }
    }
}

private fun categoryAccent(category: String): Color = when {
    "mine" in category -> Color(0xFFD28652)
    "artillery" in category || "mortar" in category -> Color(0xFFB8A45D)
    "grenade" in category -> Color(0xFF7FA875)
    "initiation" in category || "deton" in category || "fuze" in category -> Color(0xFFC58A68)
    else -> Color(0xFF7D9C84)
}

fun candidateLabel(modelStatus: String): String = when (modelStatus) {
    "designation-conflict" -> "Проверяется · конфликт названия"
    "generic-designation" -> "Проверяется · индекс не уточнён"
    "disputed-origin" -> "Проверяется · происхождение спорно"
    else -> "Проверяется · не подтверждено"
}
