package ru.dlyasvoih.app.data.update

import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.FileProvider
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.io.File
import java.security.MessageDigest

class UpdateFileProvider : FileProvider()

class AppUpdateController(private val context: Context, private val prefs: SharedPreferences,
    private val source: RemoteAppSource = RemoteAppSource(context.cacheDir)) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val mutableState = MutableStateFlow<AppUpdateState>(AppUpdateState.Idle)
    val state = mutableState.asStateFlow()
    @Suppress("DEPRECATION")
    private val installed = context.packageManager.getPackageInfo(context.packageName, signingFlags())
    val installedVersion: String = installed.versionName.orEmpty()

    fun check(automatic: Boolean = false) {
        if (mutableState.value.busy) return
        val now = System.currentTimeMillis()
        val previous = prefs.getLong("app_update_last_attempt", 0)
        if (automatic && (!prefs.getBoolean("update_auto_check", true) ||
                (now >= previous && now - previous < 24L * 60 * 60 * 1000))) return
        prefs.edit().putLong("app_update_last_attempt", now).apply()
        val fallback = offer()
        mutableState.value = AppUpdateState.Checking
        scope.launch {
            try {
                val app = withContext(Dispatchers.IO) { source.check() }
                mutableState.value = when {
                    app == null -> AppUpdateState.NotPublished
                    app.packageName != context.packageName -> throw IllegalArgumentException("Выпуск APK относится к другому приложению")
                    app.versionCode.toLong() <= code(installed) -> AppUpdateState.Current
                    app.minSdk > Build.VERSION.SDK_INT -> AppUpdateState.Unsupported(app.minSdk)
                    else -> {
                        require(signers(installed) == setOf(app.signerSha256)) {
                            "APK подписан другим ключом. Автору нужно использовать ключ текущей установки."
                        }
                        prefs.edit().putString("app_update_cached_offer", RemoteAppSource.encode(app)).apply()
                        val file = source.cachedFile()
                        val ready = withContext(Dispatchers.IO) {
                            file.isFile && runCatching { verify(file, app); true }.getOrDefault(false)
                        }
                        if (ready) AppUpdateState.Ready(app, file) else AppUpdateState.Available(app)
                    }
                }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { mutableState.value = AppUpdateState.Error(message(e, "Не удалось проверить обновление приложения. Проверьте интернет."), fallback) }
        }
    }

    // Restore only validated metadata; downloaded APK is checked again before exposing it.
    fun restoreAndCheck() {
        scope.launch {
            val cached = runCatching { prefs.getString("app_update_cached_offer", null)?.let { RemoteAppSource.decode(it) } }.getOrNull()
            if (cached != null && cached.versionCode.toLong() <= code(installed)) {
                withContext(Dispatchers.IO) { source.cachedFile().delete() }
                prefs.edit().remove("app_update_cached_offer").apply()
            }
            if (cached != null && cached.versionCode.toLong() > code(installed) && cached.packageName == context.packageName &&
                cached.minSdk <= Build.VERSION.SDK_INT && signers(installed) == setOf(cached.signerSha256)) {
                val file = source.cachedFile()
                val ready = withContext(Dispatchers.IO) { file.isFile && runCatching { verify(file, cached); true }.getOrDefault(false) }
                if (mutableState.value == AppUpdateState.Idle) mutableState.value =
                    if (ready) AppUpdateState.Ready(cached, file) else AppUpdateState.Available(cached)
            }
            check(automatic = true)
        }
    }

    fun download() {
        if (mutableState.value.busy) return
        val app = offer() ?: return
        mutableState.value = AppUpdateState.Downloading(0, app.bytes)
        scope.launch {
            var file: File? = null
            try {
                val downloaded = withContext(Dispatchers.IO) { source.download(app) {
                    mutableState.value = AppUpdateState.Downloading(it, app.bytes)
                } }
                file = downloaded
                mutableState.value = AppUpdateState.Verifying
                withContext(Dispatchers.IO) { verify(downloaded, app) }
                mutableState.value = AppUpdateState.Ready(app, downloaded)
            } catch (e: CancellationException) { file?.delete(); throw e }
            catch (e: Exception) {
                file?.delete()
                mutableState.value = AppUpdateState.Error(message(e, "Не удалось скачать APK. Проверьте интернет и свободное место."), app)
            }
        }
    }

    fun canInstall(): Boolean = context.packageManager.canRequestPackageInstalls()

    fun prepareInstall(onReady: (Intent) -> Unit) {
        val ready = mutableState.value as? AppUpdateState.Ready ?: return
        mutableState.value = AppUpdateState.Verifying
        scope.launch {
            try {
                withContext(Dispatchers.IO) { verify(ready.file, ready.app) }
                require(canInstall()) { "Разрешите установку обновлений для «ДЛЯ СВОИХ» в настройках Android." }
                val uri = FileProvider.getUriForFile(context, "${context.packageName}.updates", ready.file)
                val intent = Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                intent.clipData = ClipData.newRawUri("Обновление приложения", uri)
                mutableState.value = ready
                onReady(intent)
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { mutableState.value = AppUpdateState.Error(message(e, "Не удалось открыть установку Android."), ready.app) }
        }
    }

    fun installLaunchFailed() {
        mutableState.value = AppUpdateState.Error("Не удалось открыть установку Android. Повторите проверку обновлений.", offer())
    }

    private fun offer(): RemoteApp? = when (val current = mutableState.value) {
        is AppUpdateState.Available -> current.app
        is AppUpdateState.Ready -> current.app
        is AppUpdateState.Error -> current.app
        else -> null
    }

    @Suppress("DEPRECATION")
    private fun verify(file: File, app: RemoteApp) {
        require(file.isFile && file.length() == app.bytes && PackFiles.sha256(file) == app.sha256) { "APK повреждён. Скачайте обновление ещё раз." }
        val archive = context.packageManager.getPackageArchiveInfo(file.absolutePath, signingFlags())
            ?: throw IllegalArgumentException("Не удалось прочитать APK")
        ApkUpdatePolicy.validate(
            ApkUpdatePolicy.Identity(context.packageName, code(installed), installed.versionName.orEmpty(),
                installed.applicationInfo?.minSdkVersion ?: 0, signers(installed)),
            ApkUpdatePolicy.Identity(app.packageName, app.versionCode.toLong(), app.versionName, app.minSdk, setOf(app.signerSha256)),
            ApkUpdatePolicy.Identity(archive.packageName, code(archive), archive.versionName.orEmpty(),
                archive.applicationInfo?.minSdkVersion ?: 0, signers(archive)), Build.VERSION.SDK_INT)
    }

    private fun message(e: Exception, fallback: String) = if (e is IllegalArgumentException) e.message ?: fallback else fallback

    companion object {
        @Suppress("DEPRECATION")
        private fun signingFlags(): Int = if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES else PackageManager.GET_SIGNATURES
        @Suppress("DEPRECATION")
        private fun code(info: PackageInfo): Long = if (Build.VERSION.SDK_INT >= 28) info.longVersionCode else info.versionCode.toLong()
        @Suppress("DEPRECATION")
        private fun signers(info: PackageInfo): Set<String> {
            val certificates = if (Build.VERSION.SDK_INT >= 28) info.signingInfo?.apkContentsSigners else info.signatures
            return certificates.orEmpty().map { signature ->
                MessageDigest.getInstance("SHA-256").digest(signature.toByteArray()).joinToString("") { "%02x".format(it.toInt() and 255) }
            }.toSet()
        }
    }
}
