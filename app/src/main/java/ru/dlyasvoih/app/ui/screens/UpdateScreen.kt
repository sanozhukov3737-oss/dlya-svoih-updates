package ru.dlyasvoih.app.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.dlyasvoih.app.data.GuideRepository
import ru.dlyasvoih.app.data.UpdateState
import ru.dlyasvoih.app.data.update.RemoteUpdateState
import ru.dlyasvoih.app.data.update.AppUpdateState
import kotlinx.coroutines.flow.MutableStateFlow
import java.net.URI

@Composable
fun UpdateScreen(repo: GuideRepository, onBack: () -> Unit) {
    val state by repo.updateState.collectAsStateWithLifecycle()
    val online by repo.remoteUpdateState.collectAsStateWithLifecycle()
    val source by repo.updateSource.collectAsStateWithLifecycle()
    val autoCheck by repo.autoCheckUpdates.collectAsStateWithLifecycle()
    val appFlow = remember(repo) { repo.appUpdater?.state ?: MutableStateFlow<AppUpdateState>(AppUpdateState.Idle) }
    val appState by appFlow.collectAsStateWithLifecycle()
    val catalogBusy = state == UpdateState.Running || online.busy
    val busy = catalogBusy || appState.busy
    var sourceOpen by rememberSaveable { mutableStateOf(false) }
    val context = LocalContext.current.applicationContext
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) repo.importContent { context.contentResolver.openInputStream(uri) ?: error("Файл недоступен") }
    }
    Scaffold(topBar = { GuideBar("Обновления", onBack) }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)) {
            repo.appUpdater?.let { AppUpdateCard(it, catalogBusy) }
            Text("Каталог: новые карточки и фотографии без установки APK.")
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Каталог", style = MaterialTheme.typography.titleMedium)
                    if (source.isBlank()) {
                        Text("Источник обновлений ещё не подключён. Адрес выдаёт автор каталога.")
                    } else {
                        Text("Источник: ${runCatching { URI(source).host }.getOrNull().orEmpty()}",
                            style = MaterialTheme.typography.bodySmall)
                        Text(if (autoCheck) "Проверка при запуске: раз в сутки" else "Проверка: вручную",
                            style = MaterialTheme.typography.bodySmall)
                        when (val current = online) {
                            RemoteUpdateState.Idle -> Text("Нажмите «Проверить обновления».")
                            RemoteUpdateState.Checking -> { LinearProgressIndicator(Modifier.fillMaxWidth()); Text("Проверяем версию каталога…") }
                            is RemoteUpdateState.Available -> {
                                Text("Доступна версия ${current.catalog.version}", style = MaterialTheme.typography.titleSmall)
                                if (current.catalog.changes.isNotBlank()) Text(current.catalog.changes)
                                Text("Размер: ${"%.1f".format(current.catalog.bytes / 1048576.0)} МБ")
                                Button(enabled = !busy, onClick = repo::installRemoteUpdate, modifier = Modifier.testTag("install_online_update")) {
                                    Text("Скачать и установить")
                                }
                            }
                            is RemoteUpdateState.Current -> Text(if (state is UpdateState.Done)
                                "Каталог обновлён до версии ${current.version}." else "У вас актуальная версия каталога: ${current.version}.")
                            is RemoteUpdateState.Downloading -> {
                                LinearProgressIndicator(progress = { (current.bytes.toFloat() / current.total.coerceAtLeast(1)).coerceIn(0f, 1f) },
                                    modifier = Modifier.fillMaxWidth())
                                Text("Скачиваем: ${(100 * current.bytes / current.total.coerceAtLeast(1)).coerceIn(0, 100)} %")
                            }
                            RemoteUpdateState.Installing -> { LinearProgressIndicator(Modifier.fillMaxWidth()); Text("Проверяем и устанавливаем каталог…") }
                            RemoteUpdateState.NeedsAppUpdate -> Text("Для нового каталога нужна новая версия приложения.")
                            is RemoteUpdateState.Error -> {
                                Text(current.message, color = MaterialTheme.colorScheme.error)
                                if (current.catalog != null) Button(enabled = !busy, onClick = repo::installRemoteUpdate) { Text("Повторить скачивание") }
                            }
                        }
                        OutlinedButton(enabled = !busy, onClick = { repo.checkRemoteUpdates() },
                            modifier = Modifier.testTag("check_online_updates")) { Text("Проверить обновления") }
                    }
                    TextButton(enabled = !busy, onClick = { sourceOpen = true }) {
                        Text(if (source.isBlank()) "Подключить источник" else "Настройки источника")
                    }
                }
            }
            Text("Избранное и недавние сохранятся. После обновления карточки откроются с начала.",
                style = MaterialTheme.typography.bodySmall)
            HorizontalDivider()
            Text("Установка из файла", style = MaterialTheme.typography.titleMedium)
            Text("Можно установить ZIP-пакет от автора без подключения к интернету.")
            when (val current = state) {
                UpdateState.Idle -> Unit
                UpdateState.Running -> { LinearProgressIndicator(Modifier.fillMaxWidth()); Text("Проверяем и устанавливаем обновление…") }
                is UpdateState.Done -> if (online is RemoteUpdateState.Idle) Text("Установлена версия каталога ${current.version}.")
                is UpdateState.Error -> Text(current.message, color = MaterialTheme.colorScheme.error)
            }
            Button(enabled = !busy, onClick = {
                picker.launch(arrayOf("application/zip", "application/x-zip-compressed", "application/octet-stream"))
            }) { Text("Выбрать ZIP-пакет") }
        }
    }
    if (sourceOpen) UpdateSourceDialog(source, autoCheck, onSave = repo::configureUpdates) { sourceOpen = false }
}

@Composable
private fun UpdateSourceDialog(source: String, autoCheck: Boolean, onSave: (String, Boolean) -> Unit,
    onDismiss: () -> Unit) {
    var address by rememberSaveable { mutableStateOf(source) }
    var automatic by rememberSaveable { mutableStateOf(autoCheck) }
    var error by remember { mutableStateOf<String?>(null) }
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Источник обновлений") }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Пустое поле отключает интернет-обновления каталога. Обновления APK берутся из официального репозитория приложения.")
            OutlinedTextField(value = address, onValueChange = { address = it.take(2048); error = null },
                label = { Text("Адрес обновлений") }, placeholder = { Text("https://…") }, isError = error != null,
                modifier = Modifier.fillMaxWidth().testTag("update_source_address"))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Проверять каталог и приложение при запуске", Modifier.weight(1f))
                Switch(automatic, onCheckedChange = { automatic = it })
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        }
    }, confirmButton = {
        TextButton(onClick = {
            try { onSave(address, automatic); onDismiss() }
            catch (e: IllegalArgumentException) { error = e.message ?: "Проверьте адрес" }
        }) { Text("Сохранить") }
    }, dismissButton = { TextButton(onClick = onDismiss) { Text("Отмена") } })
}
