package ru.dlyasvoih.app.diagnostics

import android.os.SystemClock
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.painter.Painter
import coil3.EventListener
import coil3.compose.AsyncImagePainter
import coil3.decode.DecodeResult
import coil3.decode.Decoder
import coil3.fetch.FetchResult
import coil3.fetch.Fetcher
import coil3.request.ErrorResult
import coil3.request.ImageRequest
import coil3.request.Options
import coil3.request.SuccessResult
import coil3.size.SizeResolver
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.atomic.AtomicInteger

/** Only copied into the disposable debug source set by prepare.py. */
object PhotoProbe {
    private val sequence = AtomicInteger()
    private val events = mutableListOf<Map<String, Any?>>()
    private val draws = mutableMapOf<String, Long>()
    @Volatile var batch = 0
    @Volatile var phase = "setup"
    @Volatile var lastSettled = ""

    fun now(): Long = SystemClock.elapsedRealtimeNanos()
    @Synchronized fun record(kind: String, values: Map<String, Any?> = emptyMap()): Long {
        val at = now()
        events.add(mapOf("kind" to kind, "atNs" to at, "batch" to batch,
            "phase" to phase, "thread" to Thread.currentThread().name) + values)
        return at
    }
    @Synchronized fun begin(value: Int) {
        batch = value
        lastSettled = ""
        draws.clear()
    }
    fun settled(id: String) {
        record("settled", mapOf("cardId" to id))
        lastSettled = id
    }
    @Synchronized fun drawnAt(path: String): Long? = draws[path]
    @Synchronized fun eventJson(): JSONArray = JSONArray(events.map { JSONObject(it) })

    fun listener(): EventListener {
        val number = sequence.incrementAndGet()
        val createdBatch = batch
        val createdPhase = phase
        fun fields(request: ImageRequest) = mapOf("requestId" to number,
            "requestIdentity" to System.identityHashCode(request), "data" to request.data.toString(),
            "startedBatch" to createdBatch, "startedPhase" to createdPhase)
        return object : EventListener() {
            override fun onStart(request: ImageRequest) { record("requestStart", fields(request)) }
            override fun resolveSizeStart(request: ImageRequest, sizeResolver: SizeResolver) {
                record("resolveStart", fields(request))
            }
            override fun resolveSizeEnd(request: ImageRequest, size: coil3.size.Size) {
                record("resolveEnd", fields(request) + ("resolvedSize" to size.toString()))
            }
            override fun fetchStart(request: ImageRequest, fetcher: Fetcher, options: Options) {
                record("fetchStart", fields(request))
            }
            override fun fetchEnd(request: ImageRequest, fetcher: Fetcher, options: Options, result: FetchResult?) {
                record("fetchEnd", fields(request))
            }
            override fun decodeStart(request: ImageRequest, decoder: Decoder, options: Options) {
                record("decodeStart", fields(request))
            }
            override fun decodeEnd(request: ImageRequest, decoder: Decoder, options: Options, result: DecodeResult?) {
                record("decodeEnd", fields(request) + mapOf("decodedWidth" to result?.image?.width,
                    "decodedHeight" to result?.image?.height, "decodedBytes" to result?.image?.size))
            }
            override fun onSuccess(request: ImageRequest, result: SuccessResult) {
                record("requestSuccess", fields(request) + mapOf("source" to result.dataSource.name,
                    "width" to result.image.width, "height" to result.image.height,
                    "bytes" to result.image.size, "cacheKey" to result.memoryCacheKey?.toString()))
            }
            override fun onCancel(request: ImageRequest) { record("requestCancel", fields(request)) }
            override fun onError(request: ImageRequest, result: ErrorResult) {
                record("requestError", fields(request) + ("error" to result.throwable.toString()))
            }
        }
    }

    fun transform(state: AsyncImagePainter.State): AsyncImagePainter.State {
        if (state !is AsyncImagePainter.State.Success) return state
        val result = state.result
        val path = result.request.data.toString().removePrefix("file:///android_asset/")
        val paintBatch = batch
        val fields = mapOf("requestIdentity" to System.identityHashCode(result.request),
            "data" to result.request.data.toString(), "source" to result.dataSource.name,
            "width" to result.image.width, "height" to result.image.height)
        record("painterSuccess", fields)
        return state.copy(painter = FirstDrawPainter(state.painter) {
            synchronized(this) {
                val at = record("firstDraw", fields + ("painterBatch" to paintBatch))
                if (paintBatch == batch) draws[path] = at
            }
        })
    }

    private class FirstDrawPainter(val delegate: Painter, val first: () -> Unit) : Painter() {
        private var reported = false
        private var alpha = 1f
        private var colorFilter: ColorFilter? = null
        override val intrinsicSize: Size get() = delegate.intrinsicSize
        override fun applyAlpha(alpha: Float): Boolean { this.alpha = alpha; return true }
        override fun applyColorFilter(colorFilter: ColorFilter?): Boolean { this.colorFilter = colorFilter; return true }
        override fun DrawScope.onDraw() {
            with(delegate) { draw(size, alpha, colorFilter) }
            if (!reported) { reported = true; first() }
        }
    }
}
