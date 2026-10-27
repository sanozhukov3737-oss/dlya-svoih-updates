"""Create review sheets from actual Android screenshots, retaining frame hashes."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image,ImageChops,ImageDraw,ImageFont,ImageOps

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('proof',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    frames={}
    for result in a.proof.rglob('result.json'):
        data=json.loads(result.read_text())
        for m in data.get('models',[]):
            assert m['id'] not in frames,m['id']
            frames[m['id']]=(result.parent,m)
    assert len(frames)==615,len(frames)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
    audit=[];sheets=[]
    for offset in range(0,len(frames),16):
        page=Image.new('RGB',(2080,1440),'#d9ddd6');draw=ImageDraw.Draw(page)
        ids=list(frames)[offset:offset+16]
        for index,model_id in enumerate(ids):
            directory,m=frames[model_id]
            x=(index%4)*520;y=(index//4)*360
            draw.text((x+8,y+5),model_id[:51],font=font,fill='black')
            hashes={};images=[]
            for i,key in enumerate(['initial','rotated']):
                path=directory/m[key];image=Image.open(path).convert('RGB');images.append(image)
                hashes[key]=hashlib.sha256(path.read_bytes()).hexdigest()
                thumb=ImageOps.contain(image,(252,325))
                page.paste(thumb,(x+i*260+(260-thumb.width)//2,y+29+(325-thumb.height)//2))
            region=(20,60,images[0].width-20,images[0].height-40)
            diff=ImageChops.difference(images[0],images[1]).crop(region)
            assert diff.getbbox(),model_id
            pixels=list(images[0].crop(region).getdata())
            body=[p for p in pixels if max(abs(p[0]-231),abs(p[1]-233),abs(p[2]-228))>35]
            audit.append({'id':model_id,'hashes':hashes,'bodyPixels':len(body),
                'bodyColors':len(set(body)),'rotationChangesPixels':True,'humanReview':'pending'})
        name=f'sheet-{offset//16+1:02}.jpg';page.save(a.out/name,quality=94);sheets.append(name)
    (a.out/'review.json').write_text(json.dumps({'status':'pending','models':audit,'sheets':sheets},indent=2)+'\n')
    print('Created',len(sheets),'review sheets for 1230 Android views')

if __name__=='__main__':main()
