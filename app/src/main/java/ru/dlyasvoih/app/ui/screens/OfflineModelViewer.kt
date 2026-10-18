package ru.dlyasvoih.app.ui.screens

import android.annotation.SuppressLint
import android.content.Context
import android.net.Uri
import android.view.ViewGroup
import android.webkit.WebChromeClient
import android.webkit.ConsoleMessage
import android.util.Log
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner

@Composable
internal fun OfflineModelAction(cardId: String, active: Boolean, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val model = remember(cardId, context) { OfflineModelFiles.forCard(context, cardId) } ?: return
    var open by rememberSaveable(cardId) { mutableStateOf(false) }
    LaunchedEffect(active) { if (!active) open = false }
    FilledTonalButton(onClick = { open = true }, modifier = modifier.fillMaxWidth().testTag("open_offline_3d")) {
        Text("3D-модель")
        Spacer(Modifier.weight(1f))
        Text("Офлайн", style = MaterialTheme.typography.labelMedium)
    }
    if (open && active) OfflineModelDialog(modelId = model.id) { open = false }
}

@Composable
internal fun OfflineModelGallery(onDismiss: () -> Unit) {
    val context = LocalContext.current
    val models = remember(context) { OfflineModelFiles.models(context) }
    var selected by rememberSaveable { mutableStateOf<String?>(null) }
    val selectedId = selected
    if (selectedId != null) {
        OfflineModelDialog(modelId = selectedId) { selected = null }
        return
    }
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.systemBars).testTag("offline_3d_gallery")) {
            Column {
                GuideBar("3D-модели · офлайн", onDismiss)
                Text("${models.size} моделей · доступны без интернета", Modifier.padding(16.dp),
                    style = MaterialTheme.typography.bodyMedium)
                LazyColumn(modifier = Modifier.testTag("offline_3d_gallery_list"),
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 24.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(models, key = { it.id }) { model ->
                        OutlinedCard(onClick = { selected = model.id },
                            modifier = Modifier.fillMaxWidth().testTag("offline_model:${model.id}")) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                                Text(model.title, style = MaterialTheme.typography.titleMedium)
                                Text(model.subtitle, style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }
    }
}

private class ViewerHolder {
    var view: WebView? = null
}

@Composable
internal fun OfflineModelDialog(modelId: String = "tm-46", onViewerCreated: (WebView) -> Unit = {}, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val model = remember(modelId, context) { OfflineModelFiles.models(context).first { it.id == modelId } }
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
                GuideBar("${model.title} · 3D", onDismiss)
                Box(Modifier.weight(1f).fillMaxWidth()) {
                    if (failed) StatusPanel("Не удалось открыть 3D-просмотр. Попробуйте снова.", retry = {
                        failed = false; attempt++
                    }) else key(attempt) {
                        AndroidView(modifier = Modifier.fillMaxSize().clipToBounds().testTag("offline_3d_webview"),
                            factory = { context -> createOfflineModelWebView(context, modelId = model.id, onFailure = { failed = true },
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
                    Text("${model.author} · ${model.license}", style = MaterialTheme.typography.labelMedium)
                    Text(model.subtitle + ". " + model.displayNote,
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        TextButton(onClick = { uriHandler.openUri(model.source) },
                            contentPadding = PaddingValues(0.dp)) { Text("Автор и источник") }
                        TextButton(onClick = { uriHandler.openUri(model.licenseUrl) },
                            contentPadding = PaddingValues(0.dp)) { Text("Лицензия") }
                    }
                }
            }
        }
    }
}

@SuppressLint("SetJavaScriptEnabled")
internal fun createOfflineModelWebView(context: Context, modelId: String = "tm-46", onFailure: () -> Unit,
    onRendererGone: (WebView) -> Unit): WebView = WebView(context).apply {
    layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
    settings.apply {
        javaScriptEnabled = true
        useWideViewPort = true
        loadWithOverviewMode = true
        setSupportZoom(false)
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
    webChromeClient = object : WebChromeClient() {
        override fun onConsoleMessage(message: ConsoleMessage): Boolean {
            Log.i("OfflineModelViewer", message.message())
            return true
        }
    }
    webViewClient = object : WebViewClient() {
        override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse =
            OfflineModelFiles.response(context, request.url)

        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
            !OfflineModelFiles.isEntry(context, request.url)

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            if (request.isForMainFrame) onFailure()
        }

        override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
            onRendererGone(view)
            return true
        }
    }
    loadUrl(OfflineModelFiles.entryUrl(modelId))
}
