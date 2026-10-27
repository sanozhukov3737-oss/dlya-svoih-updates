package ru.dlyasvoih.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import ru.dlyasvoih.app.data.update.RemoteApp
import ru.dlyasvoih.app.data.update.RemoteAppSource

@RunWith(AndroidJUnit4::class)
class RemoteAppContractTest {
    private val offer = RemoteApp(118, "0.3.114", "ru.dlyasvoih.app", 26,
        "https://example.com/app-118.apk", 1000, "a".repeat(64), "b".repeat(64), "Обновление интерфейса")

    @Test fun apkOfferRoundTripsAndCatalogOnlyFeedIsSupported() {
        assertEquals(offer, RemoteAppSource.decode(RemoteAppSource.encode(offer)))
        assertNull(RemoteAppSource.decode("{\"formatVersion\":1,\"contentVersion\":147}"))
    }

    @Test fun apkOfferRejectsMalformedAndUnsafeValues() {
        for ((key, value) in listOf("versionCode" to 1.5, "versionCode" to -1, "bytes" to 0,
            "bytes" to 2147483649L, "minSdk" to 0, "sha256" to "abc", "signerSha256" to "x".repeat(64),
            "url" to "http://example.com/app.apk", "url" to "https://user:password@example.com/app.apk")) {
            val json = JSONObject(RemoteAppSource.encode(offer))
            json.getJSONObject("app").put(key, value)
            assertThrows(Exception::class.java) { RemoteAppSource.decode(json.toString()) }
        }
    }

    @Test fun largeOfferIsPreferredAfterTheCompatibleBridge() {
        val json = JSONObject(RemoteAppSource.encode(offer))
        val large = JSONObject(json.getJSONObject("app").toString())
            .put("versionCode", 143).put("bytes", 1400000000L)
        json.put("appLarge", large)
        assertEquals(143, RemoteAppSource.decode(json.toString())!!.versionCode)
        assertEquals(1400000000L, RemoteAppSource.decode(json.toString())!!.bytes)
        assertEquals(118, json.getJSONObject("app").getInt("versionCode"))
    }
}
