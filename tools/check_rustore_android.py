"""Verify actual certificate rotation/data retention and capture real store APK screens."""
import hashlib,json,re,sqlite3,subprocess,time,urllib.request
from pathlib import Path
import xml.etree.ElementTree as ET

OUT=Path('build/rustore'); OUT.mkdir(parents=True,exist_ok=True)
SCREEN=OUT/'screenshots';SCREEN.mkdir(exist_ok=True)
PKG='ru.dlyasvoih.app'; DB='/data/user/0/'+PKG+'/databases/guide.db'

def adb(*args,binary=False):
 r=subprocess.run(['adb',*map(str,args)],capture_output=True,timeout=45)
 if r.returncode: raise RuntimeError('adb failed: '+r.stderr.decode(errors='replace')[-800:])
 return r.stdout if binary else r.stdout.decode(errors='replace').strip()

def dump():
 adb('shell','uiautomator','dump','/sdcard/rustore-ui.xml')
 raw=adb('shell','cat','/sdcard/rustore-ui.xml')
 return ET.fromstring(raw[raw.index('<?xml'):])

def find(attr,value):
 return next((n for n in dump().iter('node') if n.get(attr)==value),None)

def wait(attr,value,timeout=30):
 deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  n=find(attr,value)
  if n is not None:return n
  time.sleep(.5)
 raise AssertionError('UI missing: '+value)

def tap(n):
 x1,y1,x2,y2=map(int,re.findall(r'\d+',n.get('bounds')))
 adb('shell','input','tap',(x1+x2)//2,(y1+y2)//2)

def shot(name):
 dump()
 (SCREEN/name).write_bytes(adb('exec-out','screencap','-p',binary=True))

old=OUT/'previous-0.3.125.apk'
with urllib.request.urlopen('https://github.com/sanozhukov3737-oss/dlya-svoih-updates/releases/download/app-0.3.125/DLYA_SVOIH_v0.3.125.apk',timeout=60) as r,old.open('wb') as f:
 while chunk:=r.read(1024*1024):f.write(chunk)
assert hashlib.sha256(old.read_bytes()).hexdigest()=='a19a1b80200797dfe549917287bf3109dfd26210eeda5788250ba70a92da3980'
adb('root');adb('wait-for-device')
subprocess.run(['adb','uninstall',PKG],capture_output=True,timeout=30)
assert 'Success' in adb('install',old)
adb('shell','am','start','-W','-n',PKG+'/.MainActivity')
wait('resource-id','home_list')
adb('shell','am','force-stop',PKG)
uid=adb('shell','stat','-c','%u',DB)
seed=OUT/'migration-before.db';adb('pull',DB,seed)
# Seed the database on the disposable emulator; flush its local WAL before adb push.
with sqlite3.connect(seed) as db:
 assert db.execute("select value from metadata where key='content_version'").fetchone()==('188',)
 db.execute("insert or replace into favorites values ('first-aid-burn',123456)")
 db.execute("insert or replace into reading values ('first-aid-burn',2,33,123456,188)")
 db.commit()
 db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
db.close()
with sqlite3.connect(seed) as check:
 assert check.execute("select savedAt from favorites where cardId='first-aid-burn'").fetchone()==(123456,)
adb('push',seed,DB)
adb('shell','rm','-f',DB+'-wal',DB+'-shm')
adb('shell','chown',uid+':'+uid,DB)
assert 'Success' in adb('install','-r',OUT/'DLYA_SVOIH_v0.3.126_RUSTORE.apk')
adb('shell','am','start','-W','-n',PKG+'/.MainActivity')
wait('resource-id','home_list')
# Offline handbook must open successfully, before any catalog download is needed.
adb('shell','am','force-stop',PKG)
after=OUT/'migration-after.db';adb('pull',DB,after)
wal=adb('shell',f'if [ -f {DB}-wal ]; then echo yes; fi')
if wal=='yes':
 adb('pull',DB+'-wal',str(after)+'-wal')
with sqlite3.connect(after) as db:
 assert db.execute("select value from metadata where key='content_version'").fetchone()==('189',)
 assert db.execute("select savedAt from favorites where cardId='first-aid-burn'").fetchone()==(123456,)
 assert db.execute("select itemIndex,offset from reading where cardId='first-aid-burn'").fetchone()==(2,33)
 assert db.execute('select count(*) from cards where archived=0').fetchone()==(1324,)
 assert 'Характеристики — 9М111-2' in db.execute("select body from cards where id='atgm-9k111-fagot'").fetchone()[0]
assert adb('shell','stat','-c','%u',DB)==uid
report={'deviceSdk':int(adb('shell','getprop','ro.build.version.sdk')),'previousApk':'0.3.125','storeApk':'0.3.126','installOverPrevious':'success','uidPreserved':True,'favoritePreserved':True,'readingPositionPreserved':True,'catalogVersion':189,'cards':1324}
(OUT/'android-migration-check.json').write_text(json.dumps(report,indent=2)+'\n')
# Screenshots show a clean installation rather than seeded test history.
adb('shell','pm','clear',PKG)
adb('shell','settings','put','global','sysui_demo_allowed','1')
adb('shell','am','start','-W','-n',PKG+'/.MainActivity')
wait('resource-id','home_list');shot('01_catalog.png')
tap(wait('content-desc','Открыть поиск'));field=wait('resource-id','search_input');tap(field)
adb('shell','input','text','111');adb('shell','input','keyevent','66')
wait('text','9К111 «Фагот»');shot('02_search.png')
tap(wait('text','9К111 «Фагот»'));wait('resource-id','detail_list');shot('03_fagot.png')
for _ in range(14):
 if find('text','Характеристики — 9М111-2') is not None:
  shot('04_fagot_characteristics.png');break
 adb('shell','input','swipe','540','1750','540','650','450')
else:raise AssertionError('Fagot table absent on real Android UI')
crashes=adb('logcat','-d','-b','crash')
assert 'FATAL EXCEPTION' not in crashes and 'Fatal signal' not in crashes
(OUT/'release-crash.log').write_text(crashes)
# Do not upload private/emulator DB files or the obsolete APK.
old.unlink();seed.unlink();after.unlink()
for p in OUT.glob('migration-after.db-*'):p.unlink()
print(json.dumps(report))
