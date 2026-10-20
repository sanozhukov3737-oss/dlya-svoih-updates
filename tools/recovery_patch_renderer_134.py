#!/usr/bin/env python3
"""Sanitize transient GLSL debug names without altering any GLB, color or compiled app code."""
import argparse,copy,hashlib,json,zipfile
from pathlib import Path

INPUT_SHA='f7f7d1034c5dba4117629e384833f5ade7545a3aae617b5b3b9da6f53b36b07f'
BUNDLE_SHA='e2ec3b59df4076ef8f9cb0a099217de5f15b2de9c918a76d8c49a89944a7e034'
ASSET='assets/viewer3d/viewer.bundle.js'
REPLACEMENTS=[('yr=o.scene;let a=new Pt',
 'yr=o.scene;let recoveryMaterialIndex=0;yr.traverse(s=>{for(let e of Array.isArray(s.material)?s.material:[s.material])if(e&&/[^\\x20-\\x7E]/.test(e.name))e.name="offline_material_"+recoveryMaterialIndex++});let a=new Pt')]

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
    r={'inputApkSha256':INPUT_SHA,'renderFixedUnsignedApkSha256':digest(target.read_bytes()),'originalViewerBundleSha256':BUNDLE_SHA,'viewerBundleSha256':digest(fixed),'onlyEntryChangedFromSearchFixedApk':ASSET,'allGlbAndAttributionBytesUnchanged':True,'behavior':'Replace only non-ASCII transient material debug names before Three.js constructs GLSL SHADER_NAME; preserve all source GLB bytes, PBR colors, geometry and Russian UI attribution'}
    (a.out/'renderer-repair-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

if __name__=='__main__':main()
