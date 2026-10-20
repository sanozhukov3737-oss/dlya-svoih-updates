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
            "bytes" to 300000000L, "minSdk" to 0, "sha256" to "abc", "signerSha256" to "x".repeat(64),
            "url" to "http://example.com/app.apk", "url" to "https://user:password@example.com/app.apk")) {
            val json = JSONObject(RemoteAppSource.encode(offer))
            json.getJSONObject("app").put(key, value)
            assertThrows(Exception::class.java) { RemoteAppSource.decode(json.toString()) }
        }
    }
}
