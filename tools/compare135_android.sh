#!/usr/bin/env bash
set -euo pipefail
mkdir -p build/compare135/reports
adb shell wm size 720x1280
adb shell wm density 320
bash ./gradlew :app:connectedDebugAndroidTest --no-daemon -PciSigningKeystore="$CI_SIGNING_KEYSTORE" -Pandroid.testInstrumentationRunnerArguments.class=ru.dlyasvoih.app.ui.screens.ComparisonSheetTest
cp -R app/build/outputs/androidTest-results/connected/debug build/compare135/reports/comparison
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
