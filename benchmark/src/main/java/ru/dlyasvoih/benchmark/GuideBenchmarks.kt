package ru.dlyasvoih.benchmark

import androidx.benchmark.macro.*
import androidx.benchmark.macro.junit4.MacrobenchmarkRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.LargeTest
import androidx.test.uiautomator.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import ru.dlyasvoih.testing.*

@RunWith(AndroidJUnit4::class)
@LargeTest
class GuideBenchmarks {
    @get:Rule val benchmark = MacrobenchmarkRule()
    private val app = "ru.dlyasvoih.app.benchmark"

    @Test fun coldStartWithoutProfile() = startup(CompilationMode.None())
    @Test fun coldStartWithProfile() = startup(CompilationMode.Partial(BaselineProfileMode.Require))
    private fun startup(compilation: CompilationMode) = benchmark.measureRepeated(
        packageName = app, metrics = listOf(StartupTimingMetric()), iterations = 10,
        startupMode = StartupMode.COLD, compilationMode = compilation,
        setupBlock = { pressHome() }
    ) { startActivityAndWait(); waitForHome() }

    @Test fun scrollTenThousandCards() = benchmark.measureRepeated(
        packageName = app, metrics = listOf(FrameTimingMetric()), iterations = 10,
        compilationMode = CompilationMode.Partial(BaselineProfileMode.Require),
        setupBlock = {
            pressHome(); startActivityAndWait(); waitForHome()
            openSection("СВО")
            check(device.wait(Until.hasObject(By.res("catalog_list")), 10_000))
            check(device.wait(Until.hasObject(By.text("Нагрузочная карточка 00000")), 10_000)) { "Synthetic benchmark catalog is missing" }
        }
    ) {
        val list = device.findObject(By.res("catalog_list"))
        list.setGestureMargin(device.displayWidth / 5)
        repeat(8) { list.fling(Direction.DOWN); device.waitForIdle() }
        repeat(4) { list.fling(Direction.UP); device.waitForIdle() }
    }

    @Test fun searchThenOpenCard() = benchmark.measureRepeated(
        packageName = app, metrics = listOf(FrameTimingMetric()), iterations = 10,
        compilationMode = CompilationMode.Partial(BaselineProfileMode.Require),
        setupBlock = { pressHome(); startActivityAndWait(); waitForHome() }
    ) { searchAndOpenCard() }
}
