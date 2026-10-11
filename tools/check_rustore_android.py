"""Verify actual certificate rotation/data retention and capture real store APK screens."""
import hashlib,json,re,sqlite3,subprocess,time,urllib.request,sys,struct
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
 raw=raw[raw.index('<?xml'):];(OUT/'last-ui.xml').write_text(raw)
 return ET.fromstring(raw)

def find(attr,value):
 return next((n for n in dump().iter('node') if n.get(attr)==value or (attr=='text' and value in n.get('text',''))),None)

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

only_screenshots='--screenshots-only' in sys.argv
if not only_screenshots:
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
# The same already-signed APK is used for clean store screenshots.
if only_screenshots:
 assert hashlib.sha256((OUT/'DLYA_SVOIH_v0.3.126_RUSTORE.apk').read_bytes()).hexdigest()=='0c3b394f7ec048326d065c04f3a4efc7e78f7e125773d508b5592581600dbcc8'
 assert 'Success' in adb('install','-r',OUT/'DLYA_SVOIH_v0.3.126_RUSTORE.apk')
adb('shell','pm','clear',PKG)
adb('shell','settings','put','global','sysui_demo_allowed','1')
adb('shell','am','start','-W','-n',PKG+'/.MainActivity')
wait('resource-id','home_list');shot('01_catalog.png')
width,height=struct.unpack('>II',(SCREEN/'01_catalog.png').read_bytes()[16:24])
assert width>=720 and height>=1280,(width,height)
tap(wait('content-desc','Открыть поиск'));field=wait('resource-id','search_input');tap(field)
adb('shell','input','text','1966%s1970');adb('shell','input','keyevent','4')
wait('text','9К111 «Фагот»');shot('02_search.png')
tap(wait('text','9К111 «Фагот»'));wait('resource-id','detail_list');shot('03_fagot.png')
for _ in range(14):
 node=find('text','Характеристики — 9М111-2')
 if node is not None:
  y=int(re.findall(r'\d+',node.get('bounds'))[1]);delta=max(0,y-int(height*.15))
  if delta>100:adb('shell','input','swipe',width//2,int(height*.85),width//2,max(int(height*.18),int(height*.85)-delta),'450')
  shot('04_fagot_characteristics.png');break
 adb('shell','input','swipe',width//2,int(height*.85),width//2,int(height*.35),'450')
else:raise AssertionError('Fagot table absent on real Android UI')
crashes=adb('logcat','-d','-b','crash')
assert 'FATAL EXCEPTION' not in crashes and 'Fatal signal' not in crashes
(OUT/'release-crash.log').write_text(crashes)
(OUT/'screenshots-check.json').write_text(json.dumps({'deviceSdk':int(adb('shell','getprop','ro.build.version.sdk')),'width':width,'height':height,'screenshots':4,'crashes':0,'apkSha256':hashlib.sha256((OUT/'DLYA_SVOIH_v0.3.126_RUSTORE.apk').read_bytes()).hexdigest()},indent=2)+'\n')
if not only_screenshots:
 old.unlink();seed.unlink();after.unlink()
 for p in OUT.glob('migration-after.db-*'):p.unlink()
 print(json.dumps(report))
