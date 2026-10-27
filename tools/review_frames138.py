"""Create review sheets from actual Android screenshots, retaining frame hashes."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image,ImageChops,ImageDraw,ImageFont,ImageOps

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('proof',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--expected',type=int,default=615)
    p.add_argument('--compact',action='store_true',help='Crop background for visual inspection; original PNGs remain unchanged')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    frames={}
    for result in a.proof.rglob('result.json'):
        data=json.loads(result.read_text())
        for m in data.get('models',[]):
            assert m['id'] not in frames,m['id']
            frames[m['id']]=(result.parent,m)
    assert len(frames)==a.expected,len(frames)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
    audit=[];sheets=[]
    per_page=24 if a.compact else 16
    cell_h=200 if a.compact else 360
    cell_w=400 if a.compact else 520
    for offset in range(0,len(frames),per_page):
        page=Image.new('RGB',(4*cell_w,(per_page//4)*cell_h),'#d9ddd6');draw=ImageDraw.Draw(page)
        ids=list(frames)[offset:offset+per_page]
        for index,model_id in enumerate(ids):
            directory,m=frames[model_id]
            x=(index%4)*cell_w;y=(index//4)*cell_h
            draw.text((x+8,y+5),model_id[:51],font=font,fill='black')
            hashes={};images=[]
            for i,key in enumerate(['initial','rotated']):
                path=directory/m[key];image=Image.open(path).convert('RGB');images.append(image)
                hashes[key]=hashlib.sha256(path.read_bytes()).hexdigest()
                view=image
                if a.compact:
                    view=image.crop((16,80,image.width-16,image.height-80))
                    rgb=ImageChops.difference(view,Image.new('RGB',view.size,(231,233,228))).split()
                    mask=ImageChops.lighter(ImageChops.lighter(rgb[0],rgb[1]),rgb[2]).point(lambda v: 255 if v>35 else 0)
                    box=mask.getbbox()
                    if box:
                        box=(max(0,box[0]-12),max(0,box[1]-12),min(view.width,box[2]+12),min(view.height,box[3]+12))
                        view=view.crop(box)
                pane_w=cell_w//2;pane_h=cell_h-30
                thumb=ImageOps.contain(view,(pane_w-8,pane_h-6))
                page.paste(thumb,(x+i*pane_w+(pane_w-thumb.width)//2,y+26+(pane_h-thumb.height)//2))
            region=(20,60,images[0].width-20,images[0].height-40)
            diff=ImageChops.difference(images[0],images[1]).crop(region)
            assert diff.getbbox(),model_id
            pixels=list(images[0].crop(region).resize((128,128)).getdata())
            body=[p for p in pixels if max(abs(p[0]-231),abs(p[1]-233),abs(p[2]-228))>35]
            audit.append({'id':model_id,'hashes':hashes,'sampleBodyPixels':len(body),
                'bodyColors':len(set(body)),'rotationChangesPixels':True,'humanReview':'pending'})
        name=f'sheet-{offset//per_page+1:02}.jpg';page.save(a.out/name,quality=94);sheets.append(name)
    (a.out/'review.json').write_text(json.dumps({'status':'pending','models':audit,'sheets':sheets},indent=2)+'\n')
    print('Created',len(sheets),'review sheets for',2*len(frames),'Android views')

if __name__=='__main__':main()
