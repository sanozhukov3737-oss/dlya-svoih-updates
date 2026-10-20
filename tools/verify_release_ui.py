import re
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

out = Path(os.environ.get('RECOVERY_UI_OUT', 'build'))
out.mkdir(parents=True, exist_ok=True)

def visible_model_pixels(frame, region):
    pixels = list(frame.crop(region).getdata())
    # Match the flat light viewer background, not the app chrome or reset button.
    visible = sum(max(abs(r-231), abs(g-233), abs(b-228)) > 35 for r,g,b in pixels)
    return visible, len(set(pixels))

def check_readable_finish(frame, region, title, illustrative=False):
    pixels = [p for p in frame.crop(region).getdata()
              if max(abs(p[0]-231), abs(p[1]-233), abs(p[2]-228)) > 35]
    assert len(pixels) > 500, (title, 'Exterior is indistinguishable from its background')
    colored = sum(max(p)-min(p) > 20 for p in pixels) / len(pixels)
    luminance = sorted(.2126*r + .7152*g + .0722*b for r,g,b in pixels)
    dark = sum(value < 30 for value in luminance) / len(luminance)
    relief = luminance[int(len(luminance)*.90)] - luminance[int(len(luminance)*.10)]
    if illustrative:
        assert colored > .65, (title, 'Default white/gray finish', colored)
    assert dark < .35, (title, 'Exterior is crushed to black', dark)
    assert relief > 15, (title, 'Surface shading is flat', relief)
    print('Readable finish verified:', title, {'colored': round(colored, 3),
          'dark': round(dark, 3), 'luminanceRange': round(relief, 1)}, flush=True)

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

def viewer_geometry():
    node = find(lambda a: a.get('class') == 'android.webkit.WebView')
    x1, y1, x2, y2 = map(int, re.findall(r'\d+', node.attrib['bounds']))
    assert x2-x1 > 80 and y2-y1 > 80, node.attrib
    width, height = x2-x1, y2-y1
    region = (int(x1+width*.12), int(y1+height*.14), int(x2-width*.12), int(y2-height*.14))
    gesture = tuple(map(str, (int(x1+width*.25), int(y1+height*.47),
                              int(x1+width*.75), int(y1+height*.57))))
    return region, gesture, (x1, y1, x2, y2)

def rotate_visible_viewer():
    region, gesture, bounds = viewer_geometry()
    adb('shell', 'input', 'swipe', *gesture, '700')
    time.sleep(1)
    return region, bounds

def assert_rotation(before, after, region, title):
    # Exclude status-bar clock, app chrome and reset controls from the comparison.
    from PIL import ImageChops
    difference = ImageChops.difference(before, after).crop(region)
    changed = sum(max(pixel) > 10 for pixel in difference.getdata())
    assert changed > 100, (title, 'Touch rotation did not change the model', changed)

try:
    adb('shell', 'am', 'start', '-W', '-n', 'ru.dlyasvoih.app/.MainActivity', '--es', 'shortcut_route', 'search_tab')
    for query, expected_title in (('SMi35', 'S.Mi.35'), ('PMK40', 'ПМК-40'),
                                  ('46', 'ТМ-46'), ('TM-46', 'ТМ-46'), ('TM46', 'ТМ-46')):
        search = find(lambda a: a.get('class') == 'android.widget.EditText')
        tap(search)
        adb('shell', 'input', 'keyevent', 'KEYCODE_MOVE_END', *(['KEYCODE_DEL'] * 20))
        adb('shell', 'input', 'text', query)
        adb('shell', 'input', 'keyevent', '4')
        card = find(lambda a: a.get('text') == expected_title or a.get('content-desc') == expected_title, timeout=35)
        root = tree()
        assert any(n.attrib.get('class') == 'android.widget.EditText' and n.attrib.get('text') == query for n in root.iter('node')), 'Search query did not change'
        assert any(n.attrib.get('text') == 'Все категории' for n in root.iter('node')), 'Search unexpectedly restricted to a category'
        (out / ('search-' + query + '-release.xml')).write_bytes(ET.tostring(root, encoding='utf-8'))
        (out / ('search-' + query + '-release.png')).write_bytes(adb('exec-out', 'screencap', '-p'))
        print('Unfiltered release search found the exact card on the first screen:', query, expected_title, flush=True)
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
    region, _, _ = viewer_geometry()
    visible, colors = visible_model_pixels(image, region)
    assert visible > 500 and colors > 100, f'Model pixels are missing: {visible}, colors={colors}'
    rotate_visible_viewer()
    (out / 'offline-model-release-rotated.png').write_bytes(adb('exec-out', 'screencap', '-p'))
    rotated = Image.open(out / 'offline-model-release-rotated.png').convert('RGB')
    assert_rotation(image, rotated, region, 'ТМ-46')
    print('Actual model pixels and touch rotation verified', visible, flush=True)
    # Open the collection through the same menu exposed to users in the release APK.
    tap(find(lambda a: a.get('content-desc') == 'Назад'))
    tap(find(lambda a: a.get('text') == 'Каталог'))
    for _ in range(6):
        current = tree()
        if any(n.get('content-desc') == 'Открыть меню' for n in current.iter('node')):
            break
        back = next((n for n in current.iter('node') if n.get('content-desc') == 'Назад'), None)
        assert back is not None, 'Catalog root cannot be reached from the current screen'
        tap(back)
    tap(find(lambda a: a.get('content-desc') == 'Открыть меню'))
    tap(find(lambda a: a.get('text') == '3D-модели · офлайн'))
    find(lambda a: 'моделей · доступны без интернета' in a.get('text', ''))
    (out / 'offline-model-gallery-release.png').write_bytes(adb('exec-out', 'screencap', '-p'))
    import json
    proof_ids = {'pfm-1', 'pmk-40', 'm1a1-at', 'tm-62-family', 'pignone-mod43',
                 'm14-complete', 'pmn-2-complete', 'm16-complete', 'british-drifting-mine'}
    model_manifest = json.loads(Path(os.environ.get('RECOVERY_MODELS_MANIFEST',
        'app/src/main/assets/viewer3d/models.json')).read_text())['models']
    proof_models = [m for m in model_manifest if m['id'] in proof_ids]
    assert len(proof_models) == len(proof_ids), 'A required visual proof model is missing'
    for model in proof_models:
        title, slug = model['title'], model['id']
        tap(find(lambda a: a.get('text') == title, scroll=True))
        find(lambda a: a.get('text') == title + ' · 3D')
        time.sleep(6)
        root = tree()
        texts = [n.get('text', '') for n in root.iter('node')]
        assert not any('Не удалось' in text or 'недоступен' in text for text in texts), texts
        assert any(model['author'] in text and model['license'] in text for text in texts), (title, 'Attribution is not visible', texts)
        path = out / ('offline-model-' + slug + '-release.png')
        path.write_bytes(adb('exec-out', 'screencap', '-p'))
        frame = Image.open(path).convert('RGB')
        region, _, viewer_bounds = viewer_geometry()
        visible, colors = visible_model_pixels(frame, region)
        assert visible > 500 and colors > 40, (title, visible, colors)
        illustrative = model['displayColorMode'] == 'illustrative'
        check_readable_finish(frame, region, title, illustrative)
        if illustrative:
            assert any('Условная' in text for text in texts), texts
        if slug == 'pfm-1':
            pixels = list(frame.crop(region).getdata())
            olive = sum(g > r * 1.05 and r > b * 1.15 and 35 < g < 220 for r,g,b in pixels)
            assert olive > 500, f'PFM-1 exterior is not visibly olive: {olive}'
            vx1, vy1, vx2, vy2 = viewer_bounds
            corners = [frame.getpixel((int(vx1+(vx2-vx1)*.05), int(vy1+(vy2-vy1)*.20))),
                       frame.getpixel((int(vx2-(vx2-vx1)*.05), int(vy1+(vy2-vy1)*.20)))]
            assert all(max(abs(a-b) for a,b in zip(pixel, (231,233,228))) < 4 for pixel in corners), corners
            assert any('Условная оливковая окраска' in text for text in texts), texts
        rotate_visible_viewer()
        rotated_path = out / ('offline-model-' + slug + '-release-rotated.png')
        rotated_path.write_bytes(adb('exec-out', 'screencap', '-p'))
        rotated = Image.open(rotated_path).convert('RGB')
        assert_rotation(frame, rotated, region, title)
        check_readable_finish(rotated, region, title + ' rotated', illustrative)
        print('Release collection, attribution, pixels and rotation verified:', title, flush=True)
        tap(find(lambda a: a.get('content-desc') == 'Назад'))
finally:
    log = adb('logcat', '-d', '-s', 'OfflineModelViewer:I', 'chromium:E', '*:S')
    (out / 'release-webview.log').write_bytes(log)
    print(log.decode(errors='replace')[-5000:], flush=True)
    (out / 'release-last-screen.png').write_bytes(adb('exec-out', 'screencap', '-p'))
