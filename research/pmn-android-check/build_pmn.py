#!/usr/bin/env python3
"""Restore the photograph-informed PMN exterior display prototype from chat.
Only visible outer appearance, arbitrary normalized units, no internal parts.
"""
from __future__ import annotations
import os, json, math, hashlib
from pathlib import Path
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image, ImageDraw, ImageFont
import trimesh
from trimesh.visual.material import PBRMaterial
from trimesh.visual.texture import TextureVisuals

OUT=Path(__file__).resolve().parent/'deliverables'
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
SOURCE='https://commons.wikimedia.org/wiki/File:PMN_anti-personnel_mine.jpg'
LICENSE='https://creativecommons.org/licenses/by-sa/3.0/'
RNG=np.random.default_rng(240710)

def field(n,sigma):
    a=gaussian_filter(RNG.normal(size=(n,n)),sigma=sigma,mode='wrap')
    return a/max(float(a.std()),1e-7)

def rubber_texture(markings=True,n=1536):
    yy,xx=np.mgrid[:n,:n]
    r=np.sqrt(((xx-n/2)/(n/2))**2+((yy-n/2)/(n/2))**2)
    broad=field(n,46); medium=field(n,8); fine=field(n,.55)
    grain=broad*2.4+medium*1.5+fine*.8
    dust=np.clip(field(n,17)-.7,0,2)*1.9
    rim=np.exp(-((r-.90)/.035)**2)*2.3
    rgb=np.clip(np.array([72.,76.,61.])[None,None,:]+grain[:,:,None]+dust[:,:,None]+rim[:,:,None],0,255)
    mask=Image.new('L',(n,n),0); d=ImageDraw.Draw(mask)
    font=ImageFont.truetype(FONT,146)
    if markings:
        d.text((n/2,n*.405),'ПМН',font=font,anchor='mm',fill=255,stroke_width=0)
        d.text((n/2,n*.535),'15-7-78',font=font,anchor='mm',fill=255,stroke_width=0)
    m=np.asarray(mask,dtype=float)/255
    m*=np.clip(.90+field(n,1.8)*.075,.58,1)
    m*=.92
    rgb=rgb*(1-m[:,:,None])+np.array([192.,175.,104.])[None,None,:]*m[:,:,None]
    packed=np.zeros((n,n,3),dtype=np.uint8); packed[:,:,0]=255
    packed[:,:,1]=np.uint8(np.clip(226+medium*3,212,239))
    return Image.fromarray(np.uint8(np.clip(rgb,0,255)),'RGB'),Image.fromarray(packed,'RGB')

def bakelite_texture():
    n=1024; yy,xx=np.mgrid[:n,:n]
    broad=field(n,30); medium=field(n,5); fine=field(n,.7)
    streak=np.sin(xx*.055+broad*.9+yy*.004)*1.3
    cloud=broad*3.5+medium*1.6+fine*.65+streak
    rgb=np.array([114.,56.,34.])[None,None,:]+cloud[:,:,None]*np.array([1.6,.75,.42])
    rgb+=np.maximum(field(n,12)-1.2,0)[:,:,None]*np.array([5,3,1])
    packed=np.zeros((n,n,3),dtype=np.uint8); packed[:,:,0]=255
    packed[:,:,1]=np.uint8(np.clip(155+medium*5,140,177))
    return Image.fromarray(np.uint8(np.clip(rgb,0,255)),'RGB'),Image.fromarray(packed,'RGB')

def metal_texture():
    n=512; a=field(n,.65)*2.1+field(n,7)*1.6
    rgb=np.array([122.,124.,107.])[None,None,:]+a[:,:,None]
    return Image.fromarray(np.uint8(np.clip(rgb,0,255)),'RGB')

def lathe(name,profile,mat,segments=128,planar=False,ribs=0):
    vertices=[]; uv=[]
    for j,(r,y) in enumerate(profile):
        for i in range(segments+1):
            t=2*math.pi*i/segments
            rr=r*(1+(.017*math.cos(t*ribs) if ribs and r>.1 else 0))
            x,z=rr*math.cos(t),rr*math.sin(t)
            vertices.append([x,y,z])
            uv.append([.5+x/2.035,.5-z/2.035] if planar else [i/segments,j/max(1,len(profile)-1)])
    vertices=np.asarray(vertices,dtype=np.float64); faces=[]
    for j in range(len(profile)-1):
        for i in range(segments):
            a=j*(segments+1)+i; b=a+segments+1
            for f in ([a,b,b+1],[a,b+1,a+1]):
                p=vertices[f]
                if np.linalg.norm(np.cross(p[1]-p[0],p[2]-p[0]))>1e-10: faces.append(f)
    mesh=trimesh.Trimesh(vertices=vertices,faces=faces,process=False)
    mesh.visual=TextureVisuals(uv=np.asarray(uv),material=mat)
    mesh.metadata={'name':name,'purpose':'closed external appearance surface'}
    return mesh

def rotated_axis(mesh,angle,position):
    m=mesh.copy(); m.apply_transform(trimesh.transformations.rotation_matrix(angle,[0,0,1]))
    m.apply_translation(position); return m

def build():
    OUT.mkdir(parents=True,exist_ok=True)
    rubber,rubber_mr=rubber_texture()
    wall,wall_mr=rubber_texture(False,512)
    brown,brown_mr=bakelite_texture(); metal=metal_texture()
    rubber.save(OUT/'rubber-markings.png',optimize=True)
    brown.save(OUT/'bakelite.png',optimize=True)
    def textured(name,albedo,mr):
        return PBRMaterial(name=name,baseColorTexture=albedo,baseColorFactor=[255,255,255,255],
            metallicFactor=0,roughnessFactor=1,metallicRoughnessTexture=mr,alphaMode='OPAQUE')
    rubber_mat=textured('PMN_rubber_olive_charcoal',rubber,rubber_mr)
    wall_mat=textured('PMN_rubber_sidewall',wall,wall_mr)
    body_mat=textured('PMN_reddish_brown_bakelite',brown,brown_mr)
    metal_mat=PBRMaterial(name='PMN_dull_metal_band',baseColorTexture=metal,
        baseColorFactor=[255,255,255,255],metallicFactor=.63,roughnessFactor=.63,alphaMode='OPAQUE')
    dark_mat=PBRMaterial(name='PMN_recess_shadow',baseColorFactor=[41,34,26,255],
        metallicFactor=0,roughnessFactor=.86,alphaMode='OPAQUE')
    scene=trimesh.Scene()
    scene.add_geometry(lathe('body',[(0,-.487),(.83,-.487),(.918,-.485),(.952,-.465),(.965,-.424),
        (.968,-.07),(.968,.018),(.95,.072),(.90,.10),(0,.10)],body_mat),node_name='closed_bakelite_body')
    scene.add_geometry(lathe('rubber_sidewall',[(0,-.015),(.91,-.015),(.983,.006),(1.003,.042),
        (1.008,.11),(1.005,.25),(.997,.365),(.981,.426),(.947,.459),(0,.459)],wall_mat),
        node_name='rubber_sidewall_without_stretched_texture')
    scene.add_geometry(lathe('rubber_top',[(0,.455),(.947,.455),(.947,.459),(.87,.474),
        (.70,.482),(.43,.486),(.18,.487),(0,.487)],rubber_mat,planar=True),node_name='rubber_cover_with_verified_marking')
    scene.add_geometry(lathe('retaining_band',[(.999,.039),(1.016,.039),(1.022,.045),
        (1.022,.078),(1.016,.086),(.999,.086),(.999,.039)],metal_mat),node_name='dull_outer_band')
    scene.add_geometry(lathe('base_seam',[(.959,-.426),(.975,-.426),(.977,-.414),
        (.973,-.407),(.96,-.407),(.959,-.426)],body_mat),node_name='lower_moulding_seam')
    big=lathe('large_side_cap',[(0,0),(.19,0),(.224,.032),(.231,.073),
        (.231,.26),(.216,.296),(.183,.31),(0,.31)],body_mat,segments=96,ribs=9)
    scene.add_geometry(rotated_axis(big,-math.pi/2,[.925,-.218,0]),node_name='closed_large_side_cap')
    neck=lathe('cap_neck_shadow',[(0,0),(.173,0),(.178,.055),(0,.055)],dark_mat,segments=80)
    scene.add_geometry(rotated_axis(neck,-math.pi/2,[.941,-.218,0]),node_name='cap_neck_shadow')
    small=lathe('flat_side_cap',[(0,0),(.155,0),(.167,.021),(.167,.12),(.151,.14),(0,.14)],body_mat,segments=96)
    scene.add_geometry(rotated_axis(small,math.pi/2,[-.929,-.205,0]),node_name='closed_flat_side_cap')
    clasp=trimesh.creation.box(extents=[.07,.08,.135]);clasp.apply_translation([1.01,.074,-.27])
    clasp.visual=TextureVisuals(uv=np.zeros((len(clasp.vertices),2)),material=metal_mat)
    scene.add_geometry(clasp,node_name='outer_band_clasp')
    scene.metadata={
        'title':'ПМН — пробная реконструкция внешнего вида',
        'purpose':'Visual reference for the DLYA SVOIH offline application',
        'units':'arbitrary normalized display units; not a dimensional reference',
        'scope':'Exterior only; simplified photographic reconstruction',
        'reference':SOURCE,'referenceAuthor':'Bestalex','license':LICENSE,
        'markings':'ПМН / 15-7-78 — transcribed from the selected photograph',
        'colorNote':'Photo-informed illustrative materials; exact colour is not calibrated',
    }
    blob=scene.export(file_type='glb',include_normals=True)
    (OUT/'pmn-visual-prototype.glb').write_bytes(blob)
    meta={
        'id':'pmn-visual-prototype','title':'ПМН — пробная модель внешнего вида',
        'file':'pmn-visual-prototype.glb','status':'prototype_separate_collection','cardIds':[],
        'proposedCardId':'eng-pmn','author':'Проект «ДЛЯ СВОИХ» — процедурная реконструкция',
        'license':'CC BY-SA 3.0','licenseUrl':LICENSE,
        'referencePhotos':[
            {'url':SOURCE,'author':'Bestalex','license':'CC BY-SA 3.0'},
            {'url':'https://commons.wikimedia.org/wiki/File:PMN-1.jpg','author':'Johan Fredriksson / Esquilo','license':'CC BY-SA 3.0'}],
        'displayColorMode':'illustrative',
        'displayNote':'Реконструкция по фотографии: коричневый корпус, тёмная крышка и жёлтая маркировка. Точные оттенки не калиброваны.',
        'markingText':['ПМН','15-7-78'],
        'markingNote':'Надпись переписана с выбранного образца; положение и шрифт приближены. Нечитаемая белая наклейка не воспроизведена.',
        'geometryNote':'Только внешний вид в условном масштабе. Невидимая нижняя поверхность упрощена.',
        'resources':'All buffers and textures embedded; no external resources',
        'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),
        'triangles':sum(len(x.faces) for x in scene.geometry.values()),'meshCount':len(scene.geometry),
        'previousDeliveredSha256':'5875ba897efc6e62512238edb9b210705940e782fc8a37688fb1dbc72dd106fa',
        'validation':{'exportedGlbReloaded':False,'desktopRendered':False,'rotatedViewRendered':False,'browserFileTested':False,'androidRendered':False}}
    meta['byteIdenticalToPreviousDelivery']=meta['sha256']==meta['previousDeliveredSha256']
    (OUT/'model-metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:meta[k] for k in ['bytes','sha256','triangles','meshCount','byteIdenticalToPreviousDelivery']},ensure_ascii=False),flush=True)

def camera_pose(eye,target=(0,0,0)):
    eye=np.asarray(eye,dtype=float); target=np.asarray(target,dtype=float)
    z=eye-target;z/=np.linalg.norm(z)
    x=np.cross([0,1,0],z);x/=np.linalg.norm(x);y=np.cross(z,x)
    m=np.eye(4);m[:3,0]=x;m[:3,1]=y;m[:3,2]=z;m[:3,3]=eye
    return m

def render():
    if 'infty' not in np.__dict__: np.infty=np.inf
    import pyrender
    loaded=trimesh.load(OUT/'pmn-visual-prototype.glb',force='scene',process=False)
    scene=pyrender.Scene(bg_color=[.89,.90,.88,1],ambient_light=[.38,.38,.38])
    for name in loaded.graph.nodes_geometry:
        transform,geom=loaded.graph[name]
        scene.add(pyrender.Mesh.from_trimesh(loaded.geometry[geom],smooth=True),pose=transform)
    for pos,power in [([3.5,5.5,5],2.6),([-4,2.5,3],1.3),([1,3,-4],1.8)]:
        scene.add(pyrender.DirectionalLight(color=np.ones(3),intensity=power),pose=camera_pose(pos))
    cam=pyrender.PerspectiveCamera(yfov=math.radians(31),znear=.01,zfar=250)
    node=scene.add(cam,pose=camera_pose([1.65,3.3,4.25]))
    renderer=pyrender.OffscreenRenderer(1500,1200)
    for name,eye,target in [
        ('PMN-preview.png',[1.65,3.3,4.25],[.02,0,0]),
        ('PMN-rotated.png',[-3.5,2.7,-4],[0,0,0]),
        ('PMN-markings.png',[.05,5.4,2.25],[0,.08,0])]:
        scene.set_pose(node,pose=camera_pose(eye,target));color,depth=renderer.render(scene)
        Image.fromarray(color).save(OUT/name)
        print(name,flush=True)
    renderer.delete()
    meta=json.loads((OUT/'model-metadata.json').read_text())
    meta['validation'].update(exportedGlbReloaded=True,desktopRendered=True,rotatedViewRendered=True)
    (OUT/'model-metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__': build();render()
