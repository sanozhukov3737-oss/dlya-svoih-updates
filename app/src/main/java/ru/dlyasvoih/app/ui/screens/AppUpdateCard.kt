package ru.dlyasvoih.app.ui.screens

import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.dlyasvoih.app.data.update.AppUpdateController
import ru.dlyasvoih.app.data.update.AppUpdateState

@Composable
fun AppUpdateCard(controller: AppUpdateController, otherUpdateBusy: Boolean) {
    val state by controller.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val installer = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { }
    fun install() {
        controller.prepareInstall { intent ->
            try { installer.launch(intent) }
            catch (_: Exception) { controller.installLaunchFailed() }
        }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        if (controller.canInstall()) install()
    }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Приложение", style = MaterialTheme.typography.titleMedium)
            Text("Установлена версия ${controller.installedVersion}", style = MaterialTheme.typography.bodySmall)
            when (val current = state) {
                AppUpdateState.Idle -> Text("Проверьте наличие новой версии приложения.")
                AppUpdateState.Checking -> { LinearProgressIndicator(Modifier.fillMaxWidth()); Text("Проверяем версию приложения…") }
                AppUpdateState.NotPublished -> Text("Обновления APK ещё не опубликованы. Канал каталога уже работает.")
                AppUpdateState.Current -> Text("У вас актуальная версия приложения.")
                is AppUpdateState.Unsupported -> Text("Для новой версии нужен Android API ${current.minSdk} или новее.")
                is AppUpdateState.Available -> {
                    Text("Доступна версия ${current.app.versionName}", style = MaterialTheme.typography.titleSmall)
                    if (current.app.changes.isNotBlank()) Text(current.app.changes)
                    Text("Размер: ${"%.1f".format(current.app.bytes / 1048576.0)} МБ")
                    Button(enabled = !otherUpdateBusy, onClick = controller::download,
                        modifier = Modifier.testTag("download_app_update")) { Text("Скачать приложение") }
                }
                is AppUpdateState.Downloading -> {
                    LinearProgressIndicator(progress = { (current.bytes.toFloat() / current.total.coerceAtLeast(1)).coerceIn(0f, 1f) },
                        modifier = Modifier.fillMaxWidth())
                    Text("Скачиваем APK: ${(100 * current.bytes / current.total.coerceAtLeast(1)).coerceIn(0, 100)} %")
                }
                AppUpdateState.Verifying -> { LinearProgressIndicator(Modifier.fillMaxWidth()); Text("Проверяем APK и подпись…") }
                is AppUpdateState.Ready -> {
                    Text("Версия ${current.app.versionName} скачана и проверена.")
                    Text("Android попросит подтвердить установку. Избранное и недавние сохранятся.")
                    if (!controller.canInstall()) Text("При первом обновлении разрешите установку из «ДЛЯ СВОИХ» в настройках Android.")
                    Button(enabled = !otherUpdateBusy, onClick = {
                        if (controller.canInstall()) install()
                        else try {
                            permission.launch(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                Uri.parse("package:${context.packageName}")))
                        } catch (_: Exception) { controller.installLaunchFailed() }
                    }, modifier = Modifier.testTag("install_app_update")) { Text("Установить обновление") }
                }
                is AppUpdateState.Error -> {
                    Text(current.message, color = MaterialTheme.colorScheme.error)
                    if (current.app != null) OutlinedButton(enabled = !otherUpdateBusy, onClick = controller::download) {
                        Text("Повторить скачивание APK")
                    }
                }
            }
            OutlinedButton(enabled = !state.busy && !otherUpdateBusy, onClick = { controller.check() },
                modifier = Modifier.testTag("check_app_updates")) { Text("Проверить приложение") }
        }
    }
}
