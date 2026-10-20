#!/usr/bin/env python3
"""Diagnostic Android captures; success means collection completed, not render QA passed."""
import argparse,json,re,time
from pathlib import Path
import recovery_android_stage3 as ui

def main():
    p=argparse.ArgumentParser();p.add_argument('--signed',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--models',type=Path,required=True);a=p.parse_args()
    ui.out=a.out.resolve();ui.out.mkdir(parents=True,exist_ok=True)
    assert ui.sha(a.signed)==ui.SIGNED_SHA
    ui.adb('root');ui.adb('wait-for-device')
    for service in ('wifi','data'):ui.adb('shell','svc',service,'disable')
    ui.offline('probe')
    assert 'Success' in ui.adb('install','--no-streaming',a.signed).decode()
    ui.catalog_root();ui.tap(ui.description('Открыть меню'));ui.tap(ui.text('3D-модели · офлайн'))
    models=[m for m in json.loads(a.models.read_text())['models'] if m['id'] in {'m14-complete','pmn-2-complete','m16-complete','british-drifting-mine'}]
    for m in models:
        for _ in range(20):
            root=ui.tree();node=next((n for n in root.iter('node') if n.get('text')==m['title']),None)
            if node is not None:ui.tap(node);break
            dims=ui.adb('shell','wm','size').decode();w,h=map(int,re.search(r'(\d+)x(\d+)',dims).groups())
            ui.adb('shell','input','swipe',int(w*.4),int(h*.8),int(w*.4),int(h*.3),'450')
        ui.text(m['title']+' · 3D');time.sleep(5)
        ui.capture(m['id']+'-initial')
        print('INITIAL',m['id'],[(n.get('text'),n.get('content-desc')) for n in ui.tree().iter('node') if n.get('text') or n.get('content-desc')],flush=True)
        ui.tap(ui.description('Сбросить положение модели'));time.sleep(2);ui.capture(m['id']+'-reset')
        node=ui.find(lambda x:x.get('class')=='android.webkit.WebView');x1,y1,x2,y2=ui.bounds(node)
        ui.adb('shell','input','swipe',int(x1+(x2-x1)*.25),int(y1+(y2-y1)*.47),int(x1+(x2-x1)*.75),int(y1+(y2-y1)*.57),'700')
        time.sleep(1);ui.capture(m['id']+'-rotated')
        print('AFTER RESET AND ROTATION',m['id'],[(n.get('text'),n.get('content-desc')) for n in ui.tree().iter('node') if n.get('text') or n.get('content-desc')],flush=True)
        ui.tap(ui.description('Назад'))
    (ui.out/'probe-result.json').write_text(json.dumps({'diagnosticOnly':True,'apkSha256':ui.SIGNED_SHA,'models':[m['id'] for m in models]},indent=2)+'\n')

try:main()
finally:
    if ui.out:
        (ui.out/'device-logcat.txt').write_bytes(ui.adb('logcat','-d'))
