#!/usr/bin/env bash
set -euo pipefail
mkdir -p build/compare135/reports
save_reports() {
  cp -R app/build/outputs/androidTest-results/connected/debug build/compare135/reports/comparison 2>/dev/null || true
  adb exec-out screencap -p > build/compare135/reports/last-debug-screen.png || true
  adb shell uiautomator dump /sdcard/comparison135-debug.xml >/dev/null || true
  adb pull /sdcard/comparison135-debug.xml build/compare135/reports/last-debug-ui.xml >/dev/null 2>&1 || true
}
trap save_reports EXIT
adb shell wm size 720x1280
adb shell wm density 320
bash ./gradlew :app:connectedDebugAndroidTest --no-daemon -PciSigningKeystore="$CI_SIGNING_KEYSTORE" -Pandroid.testInstrumentationRunnerArguments.class=ru.dlyasvoih.app.ui.screens.ComparisonSheetTest
save_reports
trap - EXIT
/usr/bin/python3 - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET
files=list(Path('build/compare135/reports/comparison').glob('TEST-*.xml'))
assert files,'Missing Android comparison reports'
suites=[ET.parse(p).getroot() for p in files]
assert sum(int(s.attrib['tests']) for s in suites)==4
assert sum(int(s.attrib.get(k,0)) for s in suites for k in ('failures','errors','skipped'))==0
PY
/usr/bin/python3 tools/compare135_android.py
