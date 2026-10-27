package ru.dlyasvoih.app.ui.screens

import android.annotation.SuppressLint
import android.content.Context
import android.net.Uri
import android.view.ViewGroup
import android.view.WindowManager
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
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.window.DialogWindowProvider
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.dlyasvoih.app.GuideApplication

@Composable
internal fun OfflineModelAction(cardId: String, active: Boolean, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val available = remember(cardId, context) { OfflineModelFiles.hasForCard(context, cardId) }
    if (!available) return
    val pack by (context.applicationContext as GuideApplication).modelPacks.state.collectAsStateWithLifecycle()
    var open by rememberSaveable(cardId) { mutableStateOf(false) }
    LaunchedEffect(active) { if (!active) open = false }
    FilledTonalButton(onClick = { open = true }, modifier = modifier.fillMaxWidth().testTag("open_offline_3d")) {
        Text("3D-модель")
        Spacer(Modifier.weight(1f))
        Text(if (pack.installed) "Офлайн" else "Скачать", style = MaterialTheme.typography.labelMedium)
    }
    if (open && active) OfflineModelGallery(cardId = cardId, onDismiss = { open = false })
}

@Composable
internal fun OfflineModelGallery(cardId: String? = null, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val pack by (context.applicationContext as GuideApplication).modelPacks.state.collectAsStateWithLifecycle()
    val loaded by produceState<List<OfflineModel>?>(null, context, cardId) {
        value = withContext(Dispatchers.IO) {
            OfflineModelFiles.models(context).filter { cardId == null || cardId in it.cardIds }
        }
    }
    val models = loaded.orEmpty()
    var query by rememberSaveable(cardId) { mutableStateOf("") }
    val filtered = remember(models, query) { OfflineModelFiles.search(models, query) }
    var selected by rememberSaveable { mutableStateOf<String?>(null) }
    val selectedId = selected
    if (selectedId != null) {
        OfflineModelDialog(modelId = selectedId) { selected = null }
        return
    }
    if (cardId != null && models.size == 1) {
        OfflineModelDialog(modelId = models.single().id, onDismiss = onDismiss)
        return
    }
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        val window = (LocalView.current.parent as? DialogWindowProvider)?.window
        val entryFocus = remember { FocusRequester() }
        val keyboardVisible = WindowInsets.ime.getBottom(LocalDensity.current) > 0
        val keyboard = LocalSoftwareKeyboardController.current
        DisposableEffect(window) {
            val previous = window?.attributes?.softInputMode
            window?.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN or WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
            onDispose { previous?.let { window?.setSoftInputMode(it) } }
        }
        LaunchedEffect(Unit) { entryFocus.requestFocus(); keyboard?.hide() }
        Surface(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.systemBars).testTag("offline_3d_gallery")) {
            Column(Modifier.focusRequester(entryFocus).focusable()) {
                GuideBar("3D-модели · офлайн", onDismiss)
                if (!keyboardVisible) Box(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) { ModelPackCard() }
                Text(if (loaded == null) "Загружаем коллекцию…" else "${filtered.size} из ${models.size} моделей" + if (pack.installed) " · офлайн" else "", Modifier.padding(16.dp),
                    style = MaterialTheme.typography.bodyMedium)
                OutlinedTextField(value = query, onValueChange = { query = it },
                    label = { Text("Найти модель") }, singleLine = true,
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp).testTag("offline_model_search"))
                if (loaded != null && filtered.isEmpty()) Text("Модели не найдены", Modifier.padding(16.dp))
                LazyColumn(modifier = Modifier.weight(1f).testTag("offline_3d_gallery_list"),
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 24.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(filtered, key = { it.id }) { model ->
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
    val pack by (context.applicationContext as GuideApplication).modelPacks.state.collectAsStateWithLifecycle()
    if (!pack.installed) {
        Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false)) {
            Surface(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.systemBars).testTag("offline_3d_dialog")) {
                Column {
                    GuideBar("${model.title} · 3D", onDismiss)
                    Column(Modifier.padding(16.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                        Text("Для просмотра этой модели скачайте 3D-коллекцию.")
                        ModelPackCard()
                    }
                }
            }
        }
        return
    }
    val uriHandler = LocalUriHandler.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val holder = remember { ViewerHolder() }
    var failed by remember { mutableStateOf(false) }
    var attempt by remember { mutableIntStateOf(0) }
    var details by rememberSaveable(modelId) { mutableStateOf(false) }
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
                    Text(model.subtitle, style = MaterialTheme.typography.bodySmall)
                    TextButton(onClick = { details = !details }, contentPadding = PaddingValues(0.dp)) {
                        Text(if (details) "Скрыть сведения" else "Автор, источники и пояснения")
                    }
                    if (details) Column(Modifier.heightIn(max = 180.dp).verticalScroll(rememberScrollState())) {
                    Text("${model.author} · ${model.license}", style = MaterialTheme.typography.labelMedium)
                    Text(model.displayNote,
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        if (model.source.startsWith("https://")) TextButton(onClick = { uriHandler.openUri(model.source) },
                            contentPadding = PaddingValues(0.dp)) { Text("Автор и источник") }
                        if (model.licenseUrl.startsWith("https://")) TextButton(onClick = { uriHandler.openUri(model.licenseUrl) },
                            contentPadding = PaddingValues(0.dp)) { Text("Лицензия") }
                    }
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
    setBackgroundColor(android.graphics.Color.rgb(231, 233, 228))
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
