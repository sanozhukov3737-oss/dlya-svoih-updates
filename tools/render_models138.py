"""Execute one native Android render shard and collect both views of every model."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

def run(*args,**kwargs):
    return subprocess.run(list(map(str,args)),check=True,capture_output=True,timeout=kwargs.get('timeout',120)).stdout

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--shard',type=int,required=True);p.add_argument('--shards',type=int,default=8)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--apks',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    for apk in ['debug.apk','test.apk']:
        result=run('adb','install','--no-streaming',a.apks/apk,timeout=360).decode();assert 'Success' in result,result
    for service in ['wifi','data']:run('adb','shell','svc',service,'disable')
    output=run('adb','shell','am','instrument','-w','-r','-e','class',
        'ru.dlyasvoih.app.ui.screens.Collection138RenderTest','-e','modelShard',a.shard,'-e','modelShards',a.shards,
        'ru.dlyasvoih.app.test/androidx.test.runner.AndroidJUnitRunner',timeout=1500).decode(errors='replace')
    (a.out/'instrumentation.txt').write_text(output)
    subprocess.run(['adb','pull','/sdcard/Android/data/ru.dlyasvoih.app/files/collection138',str(a.out)],check=True,timeout=180)
    assert re.search(r'OK \(1 test\)',output) and 'FAILURES!!!' not in output,output[-12000:]
    result=json.loads((a.out/'collection138/result.json').read_text())
    models=json.loads((Path('app/src/main/assets/viewer3d/models.json')).read_text())['models']
    expected={m['id'] for i,m in enumerate(models) if i%a.shards==a.shard}
    assert {m['id'] for m in result['models']}==expected
    for m in result['models']:
        assert m['passed'] and all((a.out/'collection138'/m[k]).stat().st_size>1000 for k in ['initial','rotated'])
    print('Verified two actual Android views for',len(expected),'models',flush=True)

if __name__=='__main__':main()
