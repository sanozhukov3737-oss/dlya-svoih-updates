package ru.dlyasvoih.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.delay
import ru.dlyasvoih.app.GuideApplication
import ru.dlyasvoih.app.data.models.ModelPackPhase

internal fun modelSize(bytes: Long) = if (bytes >= 1024L * 1024 * 1024) "%.2f ГБ".format(bytes / 1073741824.0)
    else "%.1f МБ".format(bytes / 1048576.0)

@Composable
internal fun ModelPackCard() {
    val context = LocalContext.current
    val store = remember(context) { (context.applicationContext as GuideApplication).modelPacks }
    val state by store.state.collectAsStateWithLifecycle()
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    var expanded by rememberSaveable { mutableStateOf(false) }
    var remove by remember { mutableStateOf(false) }
    var wifiOnly by remember { mutableStateOf(store.wifiOnly) }
    LaunchedEffect(store, lifecycle) {
        lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
            while (true) { store.refresh(); delay(1200) }
        }
    }
    OutlinedCard(Modifier.fillMaxWidth().testTag("model_pack_card")) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("3D-коллекция", style = MaterialTheme.typography.titleSmall)
                    Text(if (state.installed) "${store.descriptor.files.size} моделей · занято ${modelSize(state.installedBytes)}"
                        else "${store.descriptor.files.size} моделей · ${modelSize(store.descriptor.bytes)}", style = MaterialTheme.typography.bodySmall)
                }
                if (state.installed && !state.busy) TextButton(onClick = { expanded = !expanded },
                    modifier = Modifier.testTag("model_pack_manage")) { Text(if (expanded) "Скрыть" else "Управление") }
            }
            if (!state.installed || expanded || state.busy || state.phase == ModelPackPhase.Error) {
                when (state.phase) {
                    ModelPackPhase.Downloading, ModelPackPhase.Waiting -> {
                        LinearProgressIndicator(progress = { (state.downloaded.toFloat()/store.descriptor.bytes).coerceIn(0f,1f) },
                            modifier = Modifier.fillMaxWidth())
                        Text(if (state.phase == ModelPackPhase.Waiting) "Ожидаем подходящую сеть. Загрузка продолжится автоматически."
                            else "Скачиваем: ${modelSize(state.downloaded)} из ${modelSize(store.descriptor.bytes)}",
                            style = MaterialTheme.typography.bodySmall)
                        TextButton(onClick = { store.cancel() }, modifier = Modifier.testTag("model_pack_cancel")) { Text("Отменить скачивание") }
                    }
                    ModelPackPhase.Verifying -> {
                        LinearProgressIndicator(Modifier.fillMaxWidth())
                        Text("Проверяем пакет моделей…", style = MaterialTheme.typography.bodySmall)
                        TextButton(onClick = { store.cancel() }, modifier = Modifier.testTag("model_pack_cancel")) { Text("Отменить") }
                    }
                    else -> {
                        if (state.message.isNotBlank()) Text(state.message, color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall)
                        if (!state.current) {
                            Text(if (state.installed) "Доступна новая коллекция. Текущие модели работают до окончания загрузки."
                                else "Модели скачиваются отдельно по желанию. Карточки и фотографии доступны без этого пакета.",
                                style = MaterialTheme.typography.bodySmall)
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text("Только Wi-Fi", Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                                Switch(checked = wifiOnly, onCheckedChange = { wifiOnly = it; store.setWifiOnly(it) },
                                    modifier = Modifier.testTag("model_pack_wifi"))
                            }
                            Button(onClick = store::download, modifier = Modifier.fillMaxWidth().testTag("model_pack_download")) {
                                Text(if (state.installed) "Обновить модели" else "Скачать ${store.descriptor.files.size} моделей")
                            }
                            Text("Загрузка продолжится в фоне. Пакет можно удалить и скачать снова.", style = MaterialTheme.typography.bodySmall)
                        }
                        if (state.installed) OutlinedButton(onClick = { remove = true },
                            modifier = Modifier.fillMaxWidth().testTag("model_pack_delete")) { Text("Удалить модели · ${modelSize(state.installedBytes)}") }
                    }
                }
            }
        }
    }
    if (remove) AlertDialog(onDismissRequest = { remove = false }, title = { Text("Удалить 3D-модели?") },
        text = { Text("Освободится ${modelSize(state.installedBytes)}. Карточки, фотографии и избранное сохранятся. Модели можно скачать снова.") },
        confirmButton = { TextButton(onClick = { remove = false; store.delete() }, modifier = Modifier.testTag("model_pack_confirm_delete")) { Text("Удалить модели") } },
        dismissButton = { TextButton(onClick = { remove = false }) { Text("Отмена") } })
}
