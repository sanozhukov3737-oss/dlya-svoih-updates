package ru.dlyasvoih.app.ui.screens

import android.Manifest
import android.content.Intent
import android.os.Build
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
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import ru.dlyasvoih.app.data.update.UpdateNotifications

@Composable
internal fun UpdateNotificationCard(prompt: Boolean = false) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val prefs = remember(context) { context.getSharedPreferences("dlya_svoih", android.content.Context.MODE_PRIVATE) }
    var permitted by remember { mutableStateOf(UpdateNotifications.permitted(context)) }
    var wanted by remember { mutableStateOf(UpdateNotifications.wanted(context)) }
    var dismissed by remember { mutableStateOf(prefs.getBoolean("notification_prompt_dismissed", false)) }
    DisposableEffect(lifecycle, context) {
        val observer = LifecycleEventObserver { _, event -> if (event == Lifecycle.Event.ON_RESUME) {
            permitted = UpdateNotifications.permitted(context)
            wanted = UpdateNotifications.wanted(context)
            UpdateNotifications.schedule(context)
        } }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        UpdateNotifications.configure(context, granted)
        wanted = granted; permitted = UpdateNotifications.permitted(context)
        dismissed = true; prefs.edit().putBoolean("notification_prompt_dismissed", true).apply()
    }
    fun enable() {
        if (Build.VERSION.SDK_INT >= 33 && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            permission.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else if (!UpdateNotifications.permitted(context)) {
            context.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName))
        } else { UpdateNotifications.configure(context, true); wanted = true; permitted = true }
    }
    if (prompt && (dismissed || permitted || !wanted)) return
    OutlinedCard(Modifier.fillMaxWidth().testTag("update_notification_card")) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Уведомления об обновлениях", style = MaterialTheme.typography.titleSmall)
            Text("Сообщим о новой версии приложения или каталога. Одна версия — одно уведомление.", style = MaterialTheme.typography.bodySmall)
            if (prompt || !permitted) {
                Row {
                    TextButton(onClick = { enable() }, modifier = Modifier.testTag("enable_update_notifications")) { Text("Включить уведомления") }
                    if (prompt) TextButton(onClick = { dismissed = true; prefs.edit().putBoolean("notification_prompt_dismissed", true).apply() }) { Text("Позже") }
                }
                if (!prompt) TextButton(onClick = {
                    context.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName))
                }) { Text("Настройки Android") }
            } else {
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Text("Уведомлять о новых версиях", Modifier.weight(1f))
                    Switch(checked = wanted, onCheckedChange = { value ->
                        wanted = value; UpdateNotifications.configure(context, value)
                    }, modifier = Modifier.testTag("update_notifications_switch"))
                }
            }
            if (!prompt) Text(if (wanted && permitted) "Проверяем в фоне примерно раз в 6 часов, когда есть интернет."
                else "Уведомления выключены. Обновления можно проверить вручную.", style = MaterialTheme.typography.bodySmall)
        }
    }
}
