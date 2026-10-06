package ru.dlyasvoih.app.ui.screens

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.dlyasvoih.app.ui.BackupState
import ru.dlyasvoih.app.ui.BackupViewModel
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// Reinstalling under a different signing key drops favorites and reading progress for good (see
// README_RU.md and GuideDatabase); nothing else in the app protects against that. This screen is
// the only way out: it turns both tables into one small plain-text file the person keeps outside
// the app, and reads that same text back in on any install, by card id, independent of signing.
@Composable
fun BackupScreen(vm: BackupViewModel, onBack: () -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val activity = LocalContext.current
    val appContext = activity.applicationContext
    val exportedAt = remember { SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.ROOT).format(Date()) }
    val fileName = remember { "dlya-svoih-backup-${exportedAt.take(10)}.txt" }

    val saveFile = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/plain")) { uri ->
        val ready = state as? BackupState.Ready
        if (uri != null && ready != null) {
            appContext.contentResolver.openOutputStream(uri)?.use { it.write(ready.text.toByteArray(Charsets.UTF_8)) }
        }
    }
    val openFile = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            val text = appContext.contentResolver.openInputStream(uri)?.use { it.readBytes() }?.toString(Charsets.UTF_8)
            if (text != null) vm.restore(text)
        }
    }

    Scaffold(topBar = { GuideBar("Резервная копия", onBack) }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(20.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text("Избранное и «Недавние» сохраняются на этом устройстве, но теряются насовсем при " +
                "переустановке с другим ключом подписи. Сохраните список вне приложения — файлом или " +
                "обычным текстом, отправленным любым способом без интернета — и восстановите его " +
                "позже на этом или другом устройстве.", style = MaterialTheme.typography.bodyMedium)

            Text("Сохранить", style = MaterialTheme.typography.titleMedium)
            Button(onClick = { vm.prepareExport(exportedAt) }, enabled = state !is BackupState.Preparing) {
                Text("Подготовить резервную копию")
            }
            val ready = state as? BackupState.Ready
            if (ready != null) {
                Text("Готово: ${ready.favorites} избранных, ${ready.reading} недавних.",
                    style = MaterialTheme.typography.bodySmall)
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedButton(onClick = { saveFile.launch(fileName) }) { Text("Сохранить в файл") }
                    OutlinedButton(onClick = {
                        val send = Intent(Intent.ACTION_SEND).apply {
                            type = "text/plain"
                            putExtra(Intent.EXTRA_TEXT, ready.text)
                            putExtra(Intent.EXTRA_SUBJECT, "ДЛЯ СВОИХ — резервная копия")
                        }
                        activity.startActivity(Intent.createChooser(send, "Поделиться резервной копией"))
                    }) { Text("Поделиться") }
                }
            }

            HorizontalDivider()

            Text("Восстановить", style = MaterialTheme.typography.titleMedium)
            Text("Выберите ранее сохранённый файл резервной копии. Уже сохранённые на этом устройстве " +
                "отметки не стираются — восстановление только добавляет то, чего здесь ещё нет.",
                style = MaterialTheme.typography.bodyMedium)
            Button(onClick = { openFile.launch(arrayOf("text/plain", "application/octet-stream", "*/*")) },
                enabled = state !is BackupState.Preparing) { Text("Выбрать файл резервной копии") }

            when (val current = state) {
                BackupState.Preparing -> LinearProgressIndicator(Modifier.fillMaxWidth())
                is BackupState.Restored -> {
                    val result = current.result
                    Text("Восстановлено: ${result.favoritesRestored} избранных, ${result.readingRestored} недавних.",
                        style = MaterialTheme.typography.bodyMedium)
                    if (result.hasMissing) {
                        Text("Не найдены в этом каталоге и не восстановлены:", style = MaterialTheme.typography.bodyMedium)
                        for (title in result.favoritesMissing + result.readingMissing) {
                            Text("· $title", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                is BackupState.Error -> Text(current.message, color = MaterialTheme.colorScheme.error)
                else -> Unit
            }
        }
    }
}
