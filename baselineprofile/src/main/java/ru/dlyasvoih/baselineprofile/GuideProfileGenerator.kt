package ru.dlyasvoih.baselineprofile

import androidx.benchmark.macro.junit4.BaselineProfileRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.LargeTest
import androidx.test.uiautomator.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import ru.dlyasvoih.testing.*

@RunWith(AndroidJUnit4::class)
@LargeTest
class GuideProfileGenerator {
    @get:Rule val profile = BaselineProfileRule()
    @Test fun startup() = profile.collect(packageName = "ru.dlyasvoih.app", includeInStartupProfile = true) {
        pressHome(); startActivityAndWait(); waitForHome()
    }
    @Test fun searchAndReading() = profile.collect(packageName = "ru.dlyasvoih.app") {
        pressHome(); startActivityAndWait(); waitForHome()
        searchAndOpenCard()
        val detail = device.findObject(By.res("detail_list"))
        detail.setGestureMargin(device.displayWidth / 5)
        detail.scroll(Direction.DOWN, 0.7f)
        device.pressBack()
    }
}
