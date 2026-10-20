package ru.dlyasvoih.testing

import androidx.benchmark.macro.MacrobenchmarkScope
import androidx.test.uiautomator.*

fun MacrobenchmarkScope.waitForHome() {
    check(device.wait(Until.hasObject(By.text("Средства взрывания")), 15_000)) { "Catalog did not become ready" }
}

fun MacrobenchmarkScope.searchAndOpenCard() {
    device.findObject(By.text("Поиск")).click()
    val input = device.wait(Until.findObject(By.res("search_input")), 5_000) ?: error("Search field missing")
    input.text = "ожог"
    val result = device.wait(Until.findObject(By.text("Термический ожог")), 10_000) ?: error("Search result missing")
    result.click()
    check(device.wait(Until.hasObject(By.res("detail_list")), 5_000))
}

fun MacrobenchmarkScope.openSection(label: String) {
    val home = device.wait(Until.findObject(By.res("home_list")), 5_000) ?: error("Home list missing")
    home.setGestureMargin(device.displayWidth / 5)
    var attempt = 0
    while (!device.hasObject(By.text(label)) && attempt++ < 5) {
        home.scroll(Direction.DOWN, 0.6f)
        device.waitForIdle()
    }
    (device.findObject(By.text(label)) ?: error("Section missing: $label")).click()
}
