package ru.dlyasvoih.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import ru.dlyasvoih.app.data.update.*

@RunWith(AndroidJUnit4::class)
class RemoteCatalogContractTest {
    private fun feed() = JSONObject().put("formatVersion", 1).put("contentVersion", 148)
        .put("url", "https://example.com/catalog-148.zip").put("bytes", 12345)
        .put("sha256", "a".repeat(64)).put("changes", "Обновлены карточки").put("minAppCode", 116)

    @Test fun cachedOfferRoundTripsWithoutChangingVersionHashOrSource() {
        val offer = RemoteCatalogSource.decode(feed().toString())
        assertEquals(148L, offer.version)
        assertEquals(offer, RemoteCatalogSource.decode(RemoteCatalogSource.encode(offer)))
    }

    @Test fun malformedAndOversizedOffersAreRejected() {
        for ((field, invalid) in listOf("contentVersion" to 0, "bytes" to (PackFiles.MAX_ARCHIVE + 1),
            "sha256" to "invalid", "url" to "http://example.com/catalog.zip", "minAppCode" to 0,
            "minAppCode" to 4294967412L, "bytes" to 12345.5,
            "changes" to "x".repeat(5001), "formatVersion" to 2)) {
            assertThrows("Field: $field", RuntimeException::class.java) {
                RemoteCatalogSource.decode(feed().put(field, invalid).toString())
            }
        }
        assertThrows(Exception::class.java) { RemoteCatalogSource.decode("not json") }
    }
}
