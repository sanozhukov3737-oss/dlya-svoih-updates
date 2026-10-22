#!/usr/bin/env python3
"""Run just the PMN visual/gesture instrumentation and collect native evidence."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path

PACKAGE='ru.dlyasvoih.app.pmnvisualcheck'
TEST='ru.dlyasvoih.app.ui.screens.PmnVisualCheckTest'

def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-api',type=int,required=True)
    p.add_argument('--apks',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    sdk=Path(os.environ.get('ANDROID_SDK_ROOT') or os.environ['ANDROID_HOME'])
    adb=str(sdk/'platform-tools/adb');serial=os.environ.get('ANDROID_SERIAL','emulator-5554')
    def device(*args,timeout=30,check=True):
        return subprocess.run([adb,'-s',serial,*args],capture_output=True,timeout=timeout,check=check)
    report={'expectedApi':a.expected_api,'passed':False,'apks':{},'scope':'unpublished isolated PMN visual check'}
    for name in ['debug.apk','test.apk']:
        f=a.apks/name;report['apks'][name]={'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
    started=time.monotonic()
    try:
        api=int(device('shell','getprop','ro.build.version.sdk').stdout.strip());assert api==a.expected_api
        report['actualApi']=api
        for name in ['debug.apk','test.apk']: device('install','-r','-t',str(a.apks/name),timeout=150)
        result=device('shell','am','instrument','-w','-r','-e','class',TEST,
            PACKAGE+'.test/androidx.test.runner.AndroidJUnitRunner',timeout=180,check=False)
        output=(result.stdout+result.stderr).decode(errors='replace')
        (a.out/'instrumentation.txt').write_text(output)
        probe=device('shell','run-as',PACKAGE,'cat','files/pmn-visual-result.json',check=False)
        (a.out/'probe-result.json').write_bytes(probe.stdout)
        data=json.loads(probe.stdout);report['instrumentation']=data
        assert result.returncode==0 and 'OK (1 test)' in output and 'FAILURES!!!' not in output,output[-4000:]
        assert data['passed'] and data['api']==api and data['networkLoadsBlocked']
        report['passed']=True
    except Exception as error:
        report['error']=type(error).__name__+': '+str(error)
    finally:
        pull=device('pull','/data/local/tmp/pmn-visual-proof',str(a.out/'frames'),timeout=45,check=False)
        (a.out/'pull.txt').write_bytes(pull.stdout+pull.stderr)
        for name,args in [
            ('webview.log',['logcat','-d','-s','OfflineModelViewer:I','chromium:E','AndroidRuntime:E']),
            ('webview-provider.txt',['shell','dumpsys','webviewupdate']),
            ('crash.log',['logcat','-d','-b','crash'])]:
            try:
                r=device(*args,check=False);(a.out/name).write_bytes(r.stdout+r.stderr)
            except Exception as error: (a.out/name).write_text(str(error))
        report['seconds']=round(time.monotonic()-started,2)
        (a.out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return 0 if report['passed'] else 1

if __name__=='__main__': raise SystemExit(main())
