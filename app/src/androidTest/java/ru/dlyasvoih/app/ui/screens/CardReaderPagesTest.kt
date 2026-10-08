package ru.dlyasvoih.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertFalse
import org.junit.Rule
import org.junit.Test
import ru.dlyasvoih.app.data.local.ReaderCard

class CardReaderPagesTest {
    @get:Rule val compose = createComposeRule()

    @Test fun neighborsArePreparedWithoutRecordingOffscreenCardsAsRead() {
        val ids = (1..100).map { "card-$it" }
        val prepared = mutableSetOf<String>()
        val settled = mutableListOf<String>()
        compose.setContent {
            var jump by remember { mutableStateOf<ReaderJump?>(null) }
            MaterialTheme {
                CardReaderPages(ids, "card-50", { settled.add(it) }, jump) { id, active, _, _, _, _ ->
                    DisposableEffect(id) {
                        prepared.add(id)
                        onDispose { prepared.remove(id) }
                    }
                    Column(Modifier.fillMaxSize()) {
                        if (active) {
                            Text(id, Modifier.testTag("visible_card"))
                            Button(onClick = { jump = ReaderJump(74, 1) }, modifier = Modifier.testTag("jump_75")) {
                                Text("Go to 75")
                            }
                        }
                    }
                }
            }
        }
        compose.onNodeWithTag("visible_card").assertTextEquals("card-50")
        compose.runOnIdle {
            assertTrue(prepared.containsAll(listOf("card-49", "card-50", "card-51")))
            assertFalse(prepared.contains("card-1"))
            assertFalse(prepared.contains("card-100"))
            assertEquals(listOf("card-50"), settled)
        }
        compose.onNodeWithTag("jump_75").performClick()
        compose.onNodeWithTag("visible_card").assertTextEquals("card-75")
        compose.runOnIdle {
            assertTrue(prepared.containsAll(listOf("card-74", "card-75", "card-76")))
            // A distant jump must release the old page window, rather than keep a VM
            // for every article encountered while navigating a large catalogue.
            assertFalse(prepared.contains("card-50"))
            assertEquals(listOf("card-50", "card-75"), settled)
        }
    }

    @Test fun selectedCardOpensAndRightSwipeAdvancesWithFiniteEnds() {
        val settled = mutableListOf<String>()
        compose.setContent {
            MaterialTheme {
                CardReaderPages(listOf("a", "b", "c"), "b", { settled.add(it) }) { id, active, page, total, previous, next ->
                    Column(Modifier.fillMaxSize()) {
                        if (active) Text("$id:$page/$total", Modifier.testTag("visible_card"))
                        Button(onClick = previous ?: {}, enabled = previous != null,
                            modifier = Modifier.testTag(if (active) "previous" else "previous_$id")) { Text("Previous") }
                        Button(onClick = next ?: {}, enabled = next != null,
                            modifier = Modifier.testTag(if (active) "next" else "next_$id")) { Text("Next") }
                    }
                }
            }
        }
        compose.onNodeWithTag("visible_card").assertTextEquals("b:2/3")
        compose.onNodeWithTag("card_reader").performTouchInput { swipeRight() }
        compose.onNodeWithTag("visible_card").assertTextEquals("c:3/3")
        compose.onNodeWithTag("next").assertIsNotEnabled()
        compose.onNodeWithTag("card_reader").performTouchInput { swipeRight() }
        compose.onNodeWithTag("visible_card").assertTextEquals("c:3/3")
        compose.runOnIdle { assertEquals(listOf("b", "c"), settled) }
        compose.onNodeWithTag("previous").performClick()
        compose.onNodeWithTag("visible_card").assertTextEquals("b:2/3")
        compose.onNodeWithTag("card_reader").performTouchInput { swipeLeft() }
        compose.onNodeWithTag("visible_card").assertTextEquals("a:1/3")
        compose.onNodeWithTag("previous").assertIsNotEnabled()
    }

    @Test fun verticalPositionBelongsToEachCardAndSurvivesPagingBack() {
        compose.setContent {
            MaterialTheme {
                CardReaderPages(listOf("a", "b"), "a", {}) { id, _, _, _, _, _ ->
                    val list = rememberLazyListState()
                    LazyColumn(Modifier.fillMaxSize().testTag("article_$id"), state = list) {
                        items(100) { row -> Text("$id row $row", Modifier.fillMaxWidth().height(60.dp)) }
                    }
                }
            }
        }
        compose.onNodeWithTag("article_a").performScrollToIndex(10)
        compose.onNodeWithText("a row 10").assertIsDisplayed()
        compose.onNodeWithTag("card_reader").performTouchInput { swipeRight() }
        compose.onNodeWithText("b row 0").assertIsDisplayed()
        compose.onNodeWithTag("card_reader").performTouchInput { swipeLeft() }
        compose.onNodeWithText("a row 10").assertIsDisplayed()
    }

    @Test fun rightSwipeAdvancesEvenWhenThePhoneUsesRtlLayout() {
        compose.setContent {
            MaterialTheme {
                CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                    CardReaderPages(listOf("a", "b", "c"), "b", {}) { id, active, _, _, _, _ ->
                        Box(Modifier.fillMaxSize()) {
                            if (active) Text(id, Modifier.testTag("visible_card"))
                        }
                    }
                }
            }
        }
        compose.onNodeWithTag("visible_card").assertTextEquals("b")
        compose.onNodeWithTag("card_reader").performTouchInput { swipeRight() }
        compose.onNodeWithTag("visible_card").assertTextEquals("c")
        compose.onNodeWithTag("card_reader").performTouchInput { swipeLeft() }
        compose.onNodeWithTag("visible_card").assertTextEquals("b")
    }

    @Test fun choosingADistantCardKeepsTheRightSwipeDirectionAndSettledId() {
        val ids = (1..250).map { "card-$it" }
        val settled = mutableListOf<String>()
        compose.setContent {
            var jump by remember { mutableStateOf<ReaderJump?>(null) }
            MaterialTheme {
                CardReaderPages(ids, ids.first(), { settled.add(it) }, jump) { id, active, page, total, _, _ ->
                    Column(Modifier.fillMaxSize()) {
                        if (active) {
                            Text("$id:$page/$total", Modifier.testTag("visible_card"))
                            Button(onClick = { jump = ReaderJump(199, 1) }, modifier = Modifier.testTag("jump_200")) {
                                Text("Go to 200")
                            }
                        }
                    }
                }
            }
        }
        compose.onNodeWithTag("jump_200").performClick()
        compose.onNodeWithTag("visible_card").assertTextEquals("card-200:200/250")
        compose.onNodeWithTag("card_reader").performTouchInput { swipeRight() }
        compose.onNodeWithTag("visible_card").assertTextEquals("card-201:201/250")
        compose.onNodeWithTag("card_reader").performTouchInput { swipeLeft() }
        compose.onNodeWithTag("visible_card").assertTextEquals("card-200:200/250")
        compose.runOnIdle { assertEquals("card-200", settled.last()) }
    }

    @Test fun pickerFindsOriginalNumberAndSelectsOriginalIndex() {
        var selected: Int? = null
        compose.setContent {
            MaterialTheme {
                ReaderCardPicker(listOf(ReaderCard("a", "Alpha"), ReaderCard("b", "Bravo"),
                    ReaderCard("c", "Charlie")), 1, { selected = it }, {})
            }
        }
        compose.onNodeWithTag("reader_picker_query").performTextInput("2")
        compose.onNodeWithTag("reader_choose_b").performClick()
        compose.runOnIdle { assertEquals(1, selected) }
        compose.onNodeWithTag("reader_picker_query").performTextClearance()
        compose.onNodeWithTag("reader_picker_query").performTextInput("charlie")
        compose.onNodeWithTag("reader_choose_c").performClick()
        compose.runOnIdle { assertEquals(2, selected) }
    }
}
