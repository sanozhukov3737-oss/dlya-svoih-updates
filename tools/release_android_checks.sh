#!/usr/bin/env bash
set -euo pipefail
mkdir -p build
bash ./gradlew :app:connectedDebugAndroidTest --no-daemon -PciSigningKeystore="$CI_SIGNING_KEYSTORE" -Pandroid.testInstrumentationRunnerArguments.class=ru.dlyasvoih.app.ui.screens.CardReaderPagesTest,ru.dlyasvoih.app.ui.screens.ComparisonSheetTest,ru.dlyasvoih.app.ui.screens.CatalogMenuIconTest,ru.dlyasvoih.app.ui.screens.OfflineModelViewerTest,ru.dlyasvoih.app.PackagedDatabaseTest,ru.dlyasvoih.app.SearchRegressionTest || true
adb pull /data/local/tmp/offline-model-tm46.png build/offline-model-tm46.png || true
python3 -c "import json,subprocess; models=json.load(open('app/src/main/assets/viewer3d/models.json'))['models']; [subprocess.run(['adb','pull','/data/local/tmp/offline-model-'+m['id']+suffix+'.png','build/offline-model-'+m['id']+suffix+'-debug.png'],check=False) for m in models for suffix in ('','-rotated') if not suffix or m['id'] in ('m14-complete','pmn-2-complete','m16-complete','british-drifting-mine')]"
adb logcat -c
# Instrumentation just installed the current debug version. Remove that test
# package only on this newly created emulator before installing the older public
# baseline; otherwise Android correctly rejects a versionCode downgrade.
test "$(adb shell getprop ro.kernel.qemu | tr -d '\r')" = "1"
adb uninstall ru.dlyasvoih.app
adb install --no-streaming build/previous-release.apk
adb shell am start -W -n ru.dlyasvoih.app/.MainActivity --es shortcut_route search_tab
adb shell uiautomator dump /sdcard/before-update.xml
adb shell am force-stop ru.dlyasvoih.app
adb install -r app/build/outputs/apk/release/app-release.apk
python3 build/verify-release-ui.py
python3 -c "from pathlib import Path; assert 'ru.dlyasvoih.app' in Path('build/release-ui.xml').read_text(), 'Release UI did not open'"
adb logcat -d -b crash > build/release-crash.log
python3 -c "from pathlib import Path; log = Path('build/release-crash.log').read_text(); assert 'FATAL EXCEPTION' not in log and 'Fatal signal' not in log, log"
