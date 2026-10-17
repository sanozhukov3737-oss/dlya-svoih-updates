package ru.dlyasvoih.app.ui.screens

import android.annotation.SuppressLint
import android.content.Context
import android.net.Uri
import android.view.ViewGroup
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import java.io.ByteArrayInputStream

internal object OfflineModelFiles {
    const val CARD_ID = "ref-v8-tm-46"
    const val ENTRY_URL = "https://appassets.androidplatform.net/assets/viewer3d/index.html"
    const val SOURCE = "https://sketchfab.com/3d-models/tm-46-anti-tank-landmine-3f3ef18d34764342934e96c508d488b0"
    private val files = mapOf(
        "index.html" to "text/html", "viewer.bundle.js" to "text/javascript",
        "tm-46.glb" to "model/gltf-binary", "model-credits.json" to "application/json"
    )

    fun response(context: Context, uri: Uri): WebResourceResponse {
        val prefix = "/assets/viewer3d/"
        val path = uri.encodedPath.orEmpty()
        val name = path.removePrefix(prefix)
        val mime = files[name]
        if (uri.scheme != "https" || uri.host != "appassets.androidplatform.net" || uri.port != -1 ||
            uri.userInfo != null || uri.query != null || !path.startsWith(prefix) || mime == null) {
            return blocked()
        }
        return try {
            WebResourceResponse(mime, if (name.endsWith(".glb")) null else "UTF-8", 200, "OK",
                mapOf("Cache-Control" to "no-store", "X-Content-Type-Options" to "nosniff"),
                context.assets.open("viewer3d/$name"))
        } catch (_: Exception) { blocked() }
    }

    private fun blocked() = WebResourceResponse("text/plain", "UTF-8", 403, "Forbidden",
        emptyMap(), ByteArrayInputStream(byteArrayOf()))
}

@Composable
internal fun OfflineModelAction(cardId: String, active: Boolean, modifier: Modifier = Modifier) {
    if (cardId != OfflineModelFiles.CARD_ID) return
    var open by rememberSaveable(cardId) { mutableStateOf(false) }
    LaunchedEffect(active) { if (!active) open = false }
    FilledTonalButton(onClick = { open = true }, modifier = modifier.fillMaxWidth().testTag("open_offline_3d")) {
        Text("3D-модель")
        Spacer(Modifier.weight(1f))
        Text("Офлайн", style = MaterialTheme.typography.labelMedium)
    }
    if (open && active) OfflineModelDialog { open = false }
}

private class ViewerHolder {
    var view: WebView? = null
}

@Composable
internal fun OfflineModelDialog(onViewerCreated: (WebView) -> Unit = {}, onDismiss: () -> Unit) {
    val uriHandler = LocalUriHandler.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val holder = remember { ViewerHolder() }
    var failed by remember { mutableStateOf(false) }
    var attempt by remember { mutableIntStateOf(0) }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_PAUSE -> holder.view?.onPause()
                Lifecycle.Event.ON_RESUME -> holder.view?.onResume()
                else -> Unit
            }
        }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false,
        decorFitsSystemWindows = false)) {
        Surface(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.systemBars).testTag("offline_3d_dialog")) {
            Column(Modifier.fillMaxSize()) {
                GuideBar("ТМ-46 · 3D", onDismiss)
                Box(Modifier.weight(1f).fillMaxWidth()) {
                    if (failed) StatusPanel("Не удалось открыть 3D-просмотр. Попробуйте снова.", retry = {
                        failed = false; attempt++
                    }) else key(attempt) {
                        AndroidView(modifier = Modifier.fillMaxSize().testTag("offline_3d_webview"),
                            factory = { context -> createOfflineModelWebView(context, onFailure = { failed = true },
                                onRendererGone = { destroyed ->
                                    (destroyed.parent as? ViewGroup)?.removeView(destroyed)
                                    if (holder.view === destroyed) holder.view = null
                                    destroyed.destroy()
                                    failed = true
                                }).also { holder.view = it; onViewerCreated(it) } },
                            onRelease = { view ->
                                if (holder.view === view) {
                                    holder.view = null
                                    view.stopLoading(); view.onPause(); view.destroy()
                                }
                            })
                    }
                }
                HorizontalDivider()
                Column(Modifier.padding(horizontal = 16.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text("Oscar Goldsworthy · CC BY 4.0", style = MaterialTheme.typography.labelMedium)
                    Text("Текстуры уменьшены для телефона. Модель сохранена в приложении.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    TextButton(onClick = { uriHandler.openUri(OfflineModelFiles.SOURCE) },
                        contentPadding = PaddingValues(0.dp)) { Text("Автор и источник · Sketchfab") }
                }
            }
        }
    }
}

@SuppressLint("SetJavaScriptEnabled")
internal fun createOfflineModelWebView(context: Context, onFailure: () -> Unit,
    onRendererGone: (WebView) -> Unit): WebView = WebView(context).apply {
    settings.apply {
        javaScriptEnabled = true
        domStorageEnabled = false
        allowFileAccess = false
        allowContentAccess = false
        blockNetworkLoads = true
        javaScriptCanOpenWindowsAutomatically = false
        setSupportMultipleWindows(false)
        mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
        cacheMode = WebSettings.LOAD_NO_CACHE
        mediaPlaybackRequiresUserGesture = true
    }
    setBackgroundColor(android.graphics.Color.rgb(19, 26, 23))
    webViewClient = object : WebViewClient() {
        override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse =
            OfflineModelFiles.response(context, request.url)

        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
            request.url.toString() != OfflineModelFiles.ENTRY_URL

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            if (request.isForMainFrame) onFailure()
        }

        override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
            onRendererGone(view)
            return true
        }
    }
    loadUrl(OfflineModelFiles.ENTRY_URL)
}
