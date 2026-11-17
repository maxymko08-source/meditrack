"""Authoritative parametric CSG geometry, millimetres. No primitive mesh concatenation."""
from pathlib import Path
import json, hashlib, math
import manifold3d as m
import numpy as np
import trimesh
P = dict(board_length=55, board_width=28, board_thickness=1.6, component_height=14,
 servo_length=23, servo_width=13, servo_height=29, servo_axis_offset=5.5,
 servo_tab_spacing=27.5, horn_radius=9, horn_thickness=2, horn_hole_spacing=14,
 servo_axis_above_mount=7, board_support_height=8,
 fit_clearance=.3, radial_clearance=.4, axial_clearance=.4, screw_clearance=3.4,
 gear_backlash=0, usb_width=14, usb_height=10, usb_center_z=17,
 rotor_radius=92, inner_radius=55, outer_radius=82, chamber_angle=16,
 chamber_height=28, floor_z=64, floor_thickness=3)
ANGLES=list(range(20,161,20))
def box(x,y,z,dx,dy,dz): return m.Manifold.cube((dx,dy,dz)).translate((x,y,z))
def cyl(r,h,z=0,x=0,y=0): return m.Manifold.cylinder(h,r,circular_segments=128).translate((x,y,z))
def ring(ri,ro,z,h): return cyl(ro,h,z)-cyl(ri,h+2,z-1)
def wedge(ri,ro,angle,width,z,h):
 a=np.radians(np.linspace(angle-width/2,angle+width/2,33))
 pts=np.vstack((np.c_[ro*np.cos(a),ro*np.sin(a)],np.c_[ri*np.cos(a[::-1]),ri*np.sin(a[::-1])]))
 return m.CrossSection([pts]).extrude(h).translate((0,0,z))
def parts():
 floor=P["floor_z"]; thick=P["floor_thickness"]; deck=floor+thick+P["axial_clearance"]; mount=floor-P["servo_axis_above_mount"]
 board_l=P["board_length"]; board_w=P["board_width"]; fit=P["fit_clearance"]
 # Broad removable drawer catches all eight vertical drop paths, no hidden funnel.
 base=box(-102,-102,0,204,204,deck)-box(-98,-98,4,196,196,deck)
 base-=box(-95,96,4,190,10,43)
 base+=box(-98,-24,4,196,3,50) # sealed electronics partition
 base+=ring(P['rotor_radius']+P['radial_clearance'],99,floor-3,deck-floor+3) # radial guide; bonded to shell via four tabs
 for x,y in [(95,0),(-99,0),(0,95),(0,-99)]: base+=box(x,y,floor-5,4,4,deck-floor+5)
 # Outer sliding bearing pads support rotor weight independently of servo.
 for a in [10,170,250]:
  x,y=90*math.cos(math.radians(a)),90*math.sin(math.radians(a))
  base+=box(x-3,y-3,4,6,6,floor-4)
 # Rear ESP32 edge cradle: no invented PCB mounting holes.
 for x in [-board_l/2-fit-1.6,board_l/2+fit]: base+=box(x,-71-board_w/2-fit-.2,3.8,1.6,board_w+2*fit+.4,P["board_support_height"]+.2)
 for y in [-71-board_w/2-fit-1.6,-71+board_w/2+fit]: base+=box(-board_l/2-fit-1.6,y,3.8,board_l+2*fit+3.2,1.6,P["board_support_height"]+.2)
 for x in [-24,24]:
  for y in [-82,-60]:base+=cyl(2,P['board_support_height'],4,x,y)
 for x in [-12,12]:
  for y in [-90,-53]:base-=box(x-2,y,-1,4,2,6) # removable cable ties over PCB edges
 base-=box(-P['usb_width']/2,-104,P['usb_center_z']-P['usb_height']/2,P['usb_width'],25,P['usb_height'])
 # Removable servo bridge outside the pill annulus; tabs bolted into posts.
 for x in [-23,23]:
  base+=box(x-4,-19,4,8,12,mount-4)
  base-=cyl(1.25,20,mount-14,x,-13)
 base+=box(-99,87,floor-3,198,6,3)
 bridge=box(-27,-19,mount,54,32,3)
 bridge-=box(-P['servo_axis_offset']-P['servo_length']/2-P['fit_clearance'],-P['servo_width']/2-P['fit_clearance'],mount-1,P['servo_length']+2*P['fit_clearance'],P['servo_width']+2*P['fit_clearance'],5)
 for x in [-23,23]: bridge-=cyl(P["screw_clearance"]/2,5,mount-1,x,-13)
 for x in [-P['servo_axis_offset']-P['servo_tab_spacing']/2,-P['servo_axis_offset']+P['servo_tab_spacing']/2]: bridge-=cyl(1.2,5,mount-1,x,0)
 rotor=cyl(P['rotor_radius'],thick,floor)-wedge(P['inner_radius']-1,P['outer_radius']+1,0,P['chamber_angle'],floor-1,thick+2)
 rotor-=cyl(P['horn_radius']+P['fit_clearance'],P['horn_thickness']+.1,floor-.1)
 rotor-=cyl(1.4,thick+2,floor-1)
 for x in [-P['horn_hole_spacing']/2,P['horn_hole_spacing']/2]: rotor-=cyl(1.2,thick+2,floor-1,x,0)
 chambers=cyl(98,P['chamber_height'],deck)-cyl(16,P['chamber_height']+2,deck-1)
 for a in ANGLES: chambers-=wedge(P['inner_radius'],P['outer_radius'],a,P['chamber_angle'],deck-1,P['chamber_height']+2)
 # Four bolts secure stationary cassette; rim overlaps rotor with axial gap.
 for x,y in [(-96,0),(96,0),(0,-96),(0,96)]:
  chambers-=cyl(P['screw_clearance']/2,P['chamber_height']+2,deck-1,x,y)
  base-=cyl(1.25,12,deck-10.4,x,y) # M3 pilot into plastic; cassette has clearance holes
 lid=cyl(100,3,deck+P['chamber_height'])-cyl(3.2,5,deck+P['chamber_height']-1,0,-96)
 for x,y in [(-96,0),(96,0),(0,96)]: lid-=cyl(P['screw_clearance']/2,5,deck+P['chamber_height']-1,x,y)
 tray=box(-85,12,5,170,106,40)-box(-83,14,7,166,102,40)
 tray+=box(20,116,5,40,8,5)
 # Open-ended clearance for the front support post during drawer withdrawal.
 
 coupon=box(0,0,0,32,22,5)
 for x,r in [(6,1.6),(16,1.7),(26,1.8)]: coupon-=cyl(r,7,-1,x,11)
 horn_coupon=(rotor^cyl(13,thick,floor)).translate((0,0,-floor))
 return dict(enclosure=base,servo_bridge=bridge,rotating_floor=rotor,chambers=chambers,loading_cover=lid,collection_tray=tray,fit_coupon=coupon,horn_coupon=horn_coupon)
def mesh(s):
 v=s.simplify(0.00001).to_mesh(); return trimesh.Trimesh(np.asarray(v.vert_properties)[:,:3],np.asarray(v.tri_verts),process=True)
def build():
 root=Path(__file__).parent; out=root/'final';out.mkdir(exist_ok=True)
 solids=parts(); report={}; meshes={}
 for name,s in solids.items():
  t=mesh(s); meshes[name]=t
  counts=np.bincount(t.edges_unique_inverse)
  report[name]=dict(watertight=bool(t.is_watertight),winding=bool(t.is_winding_consistent),
   nonmanifold_edges=int(np.sum(counts!=2)),degenerate=int(np.sum(t.area_faces<1e-9)),
   components=len(s.decompose()),volume_mm3=float(t.volume),bounds_mm=t.bounds.tolist(),csg_status=str(s.status()))
  assert t.is_watertight and t.is_winding_consistent and np.all(counts==2) and np.all(t.area_faces>1e-9) and len(s.decompose())==1,(name,report[name])
  printable=t.copy(); printable.apply_translation(-printable.bounds[0]); printable.export(out/(name+'.stl'))
  report[name]['stl_sha256']=hashlib.sha256((out/(name+'.stl')).read_bytes()).hexdigest()
 viewer=['// Generated STL viewer; edit design.py, then regenerate.','PART="all";']
 for name,t in meshes.items():
  viewer.append('if(PART=="'+name+'"'+('' if 'coupon' in name else ' || PART=="all"')+') translate('+str(t.bounds[0].tolist())+') import("final/'+name+'.stl");')
 (root/'pill_dispenser.scad').write_text('\n'.join(viewer))
 # Interference at every integer degree, with analytic constant z clearance between floor and cassette.
 collisions=[]
 for a in range(161):
  rotor=solids['rotating_floor'].rotate((0,0,a))
  for name in ['enclosure','servo_bridge','chambers','loading_cover','collection_tray']:
   volume=(rotor^solids[name]).volume()
   if volume>1e-5: collisions.append([a,name,volume])
 report['motion']={'sample_step_deg':1,'collisions':collisions,'axial_gap_mm':.4,
  'future_chambers_open_at_dwell':False,'return_requires_empty':True,
  'self_intersections':'Run validate_intersections.py; independent MeshLab results are in self_intersections.json'}
 fixed_collisions=[]
 items=[(n,s) for n,s in solids.items() if 'coupon' not in n]
 for i,(n,s) in enumerate(items):
  for k,t in items[i+1:]:
   v=(s^t).volume()
   if v>1e-5: fixed_collisions.append([n,k,v])
 report['fixed_part_collisions']=fixed_collisions
 drawer_collisions=[]
 for dy in range(0,205,2):
  if (solids['collection_tray'].translate((0,dy,0))^solids['enclosure']).volume()>1e-5: drawer_collisions.append(dy)
 report['drawer_collision_offsets_mm']=drawer_collisions
 references={'esp32_board':box(-P['board_length']/2,-71-P['board_width']/2,4+P['board_support_height'],P['board_length'],P['board_width'],P['board_thickness']),
 'sg90_body':box(-P['servo_axis_offset']-P['servo_length']/2,-P['servo_width']/2,P['floor_z']-P['servo_axis_above_mount']-P['servo_height'],P['servo_length'],P['servo_width'],P['servo_height'])}
 report['reference_envelope_collisions']=[]
 for ref,shape in references.items():
  for name,solid in items:
   v=(shape^solid).volume()
   if v>1e-5:report['reference_envelope_collisions'].append([ref,name,v])
 (out/'validation.json').write_text(json.dumps(report,indent=2))
 (root/'mechanism.json').write_text(json.dumps(dict(protocol_version=1,home_angle_deg=0,compartment_angles_deg=ANGLES,parameters=P,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2))
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from mpl_toolkits.mplot3d.art3d import Poly3DCollection
 for exploded in [False,True]:
  fig=plt.figure(figsize=(10,9));ax=fig.add_subplot(projection='3d')
  for i,(name,t) in enumerate(meshes.items()):
   if 'coupon' in name:continue
   triangles=t.triangles.copy()
   if exploded:
    if name=='collection_tray':triangles[:,:,1]+=140
    elif name=='loading_cover':triangles[:,:,0]+=180;triangles[:,:,2]+=100
    else:triangles[:,:,2]+=i*25
   ax.add_collection3d(Poly3DCollection(triangles,alpha=.45 if name=='enclosure' else .8,facecolor=plt.cm.tab10(i),linewidth=.02))
  ax.set(xlim=(-115,290 if exploded else 115),ylim=(-110,280 if exploded else 130),zlim=(0,230 if exploded else 110),xlabel='X, mm',ylabel='Y, mm',zlabel='Z, mm')
  ax.view_init(50 if exploded else 30,-55);fig.tight_layout();fig.savefig(out/('exploded.png' if exploded else 'assembly.png'));plt.close(fig)
 from matplotlib.patches import Wedge,Circle
 fig,ax=plt.subplots(figsize=(9,6));ax.add_patch(Circle((0,0),98,fill=False))
 for i,a in enumerate(ANGLES):
  ax.add_patch(Wedge((0,0),82,a-8,a+8,width=27,color=plt.cm.tab10(i)))
  ax.text(70*math.cos(math.radians(a)),70*math.sin(math.radians(a)),str(i+1),ha='center',va='center')
 ax.add_patch(Wedge((0,0),83,-8,8,width=29,fill=False,hatch='//'))
 ax.text(70,-12,'Home 0°',ha='center');ax.set_aspect('equal');ax.set(xlim=(-105,105),ylim=(-25,105),xlabel='X, mm',ylabel='Y, mm');fig.tight_layout();fig.savefig(out/'compartments.png');plt.close(fig)
 print(json.dumps({'parts':len(solids),'motion_collisions':len(collisions)}))
 if collisions or fixed_collisions or drawer_collisions or report['reference_envelope_collisions']: raise SystemExit('Interference requires correction')
if __name__=='__main__': build()






