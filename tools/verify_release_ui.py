import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

out = Path('build')

def adb(*args):
    return subprocess.run(['adb', *args], capture_output=True, check=True).stdout

def tree():
    raw = adb('shell', 'uiautomator', 'dump', '/sdcard/offline-proof.xml')
    raw = adb('exec-out', 'cat', '/sdcard/offline-proof.xml')
    (out / 'release-ui.xml').write_bytes(raw)
    return ET.fromstring(raw)

def tap(node):
    x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.attrib['bounds']))
    adb('shell', 'input', 'tap', str((x1+x2)//2), str((y1+y2)//2))

def find(predicate, timeout=25, scroll=False):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root = tree()
        for node in root.iter('node'):
            if predicate(node.attrib):
                return node
        if scroll:
            adb('shell', 'input', 'swipe', '160', '490', '160', '180', '350')
        time.sleep(.6)
    texts = [n.attrib.get('text') or n.attrib.get('content-desc') for n in root.iter('node')]
    raise AssertionError('UI element missing: ' + repr([t for t in texts if t]))

try:
    adb('shell', 'am', 'start', '-W', '-n', 'ru.dlyasvoih.app/.MainActivity', '--es', 'shortcut_route', 'search_tab')
    for query in ('46', 'TM-46', 'TM46'):
        search = find(lambda a: a.get('class') == 'android.widget.EditText')
        tap(search)
        adb('shell', 'input', 'keyevent', 'KEYCODE_MOVE_END', *(['KEYCODE_DEL'] * 20))
        adb('shell', 'input', 'text', query)
        adb('shell', 'input', 'keyevent', '4')
        card = find(lambda a: a.get('text') == 'ТМ-46' or a.get('content-desc') == 'ТМ-46', timeout=35)
        root = tree()
        assert any(n.attrib.get('class') == 'android.widget.EditText' and n.attrib.get('text') == query for n in root.iter('node')), 'Search query did not change'
        assert any(n.attrib.get('text') == 'Все категории' for n in root.iter('node')), 'Search unexpectedly restricted to a category'
        (out / ('search-' + query + '-release.xml')).write_bytes(ET.tostring(root, encoding='utf-8'))
        (out / ('search-' + query + '-release.png')).write_bytes(adb('exec-out', 'screencap', '-p'))
        print('Unfiltered release search found ТМ-46 on the first screen:', query, flush=True)
    tap(card)
    button = find(lambda a: '3D-модель' in (a.get('text', '') + a.get('content-desc', '')), scroll=True)
    tap(button)
    time.sleep(5)
    root = tree()
    print('REAL RELEASE VIEWER TEXT:', [(n.attrib.get('text'), n.attrib.get('content-desc')) for n in root.iter('node') if n.attrib.get('text') or n.attrib.get('content-desc')], flush=True)
    (out / 'offline-model-release.png').write_bytes(adb('exec-out', 'screencap', '-p'))
    from PIL import Image, ImageChops
    image = Image.open(out / 'offline-model-release.png').convert('RGB')
    w, h = image.size
    region = (int(w*.15), int(h*.30), int(w*.85), int(h*.70))
    pixels = list(image.crop(region).getdata())
    visible = sum(max(abs(r-19), abs(g-26), abs(b-23)) > 35 for r,g,b in pixels)
    assert visible > 500 and len(set(pixels)) > 100, f'Model pixels are missing: {visible}, colors={len(set(pixels))}'
    adb('shell', 'input', 'swipe', '90', '290', '230', '330', '700')
    time.sleep(1)
    (out / 'offline-model-release-rotated.png').write_bytes(adb('exec-out', 'screencap', '-p'))
    rotated = Image.open(out / 'offline-model-release-rotated.png').convert('RGB')
    assert ImageChops.difference(image, rotated).crop(region).getbbox(), 'Rotation did not change the visible model'
    print('Actual model pixels and touch rotation verified', visible, flush=True)
finally:
    log = adb('logcat', '-d', '-s', 'OfflineModelViewer:I', 'chromium:E', '*:S')
    (out / 'release-webview.log').write_bytes(log)
    print(log.decode(errors='replace')[-5000:], flush=True)
    (out / 'release-last-screen.png').write_bytes(adb('exec-out', 'screencap', '-p'))
