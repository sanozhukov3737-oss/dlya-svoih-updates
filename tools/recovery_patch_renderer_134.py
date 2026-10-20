#!/usr/bin/env python3
"""Apply the reviewed GPU-copy/first-frame fix without altering any GLB or compiled app code."""
import argparse,copy,hashlib,json,zipfile
from pathlib import Path

INPUT_SHA='f7f7d1034c5dba4117629e384833f5ade7545a3aae617b5b3b9da6f53b36b07f'
BUNDLE_SHA='e2ec3b59df4076ef8f9cb0a099217de5f15b2de9c918a76d8c49a89944a7e034'
ASSET='assets/viewer3d/viewer.bundle.js'
REPLACEMENTS=[
 ('var El=document.getElementById("status")','let recoveryEmptyFrameRetries=0;var El=document.getElementById("status")'),
 ('st.render(Mr,At),va.drawImage','st.render(Mr,At),st.getContext().finish(),va.drawImage'),
 ('Gu=!0;let s=va.getImageData','let s=va.getImageData'),
 ('wt.dataset.colors=String(e.size),console.info("Offline model frame"',
  'if(e.size<8&&recoveryEmptyFrameRetries<8){recoveryEmptyFrameRetries++;document.body.dataset.state="loading";El.hidden=false;vr();return;}Gu=true;wt.dataset.colors=String(e.size),console.info("Offline model frame"')]

def digest(raw):return hashlib.sha256(raw).hexdigest()
def patched_bundle(raw):
    assert digest(raw)==BUNDLE_SHA
    value=raw.decode()
    for before,after in REPLACEMENTS:
        assert value.count(before)==1,before
        value=value.replace(before,after)
    return value.encode()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apk',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    assert digest(a.apk.read_bytes())==INPUT_SHA
    a.out.mkdir(parents=True,exist_ok=True);target=a.out/'DLYA_SVOIH_v0.3.134-render-fixed-unsigned.apk'
    with zipfile.ZipFile(a.apk) as original:
        fixed=patched_bundle(original.read(ASSET))
        with zipfile.ZipFile(target,'w') as output:
            for info in original.infolist():output.writestr(copy.copy(info),fixed if info.filename==ASSET else original.read(info.filename))
        with zipfile.ZipFile(target) as output:
            assert original.namelist()==output.namelist()
            assert [n for n in original.namelist() if original.read(n)!=output.read(n)]==[ASSET]
    (a.out/'viewer.bundle.js').write_bytes(fixed)
    r={'inputApkSha256':INPUT_SHA,'renderFixedUnsignedApkSha256':digest(target.read_bytes()),'originalViewerBundleSha256':BUNDLE_SHA,'viewerBundleSha256':digest(fixed),'onlyEntryChangedFromSearchFixedApk':ASSET,'allGlbAndAttributionBytesUnchanged':True,'behavior':'Synchronize GPU before canvas copy; retry at most eight blank initial frames before showing render failure'}
    (a.out/'renderer-repair-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

if __name__=='__main__':main()
