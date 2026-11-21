"""MediTrack v2: authoritative CSG geometry in millimetres; direct 0..160 drive."""
from pathlib import Path
import hashlib,json,math
import manifold3d as m
import numpy as np
import trimesh
P=dict(board_length=55,board_width=28,board_thickness=1.6,component_height=14,
 servo_length=23,servo_width=13,servo_height=29,servo_axis_offset=5.5,
 servo_tab_spacing=27.5,servo_axis_above_mount=7,horn_radius=9,horn_thickness=2,
 horn_hole_spacing=14,fit_clearance=.3,radial_clearance=.4,axial_clearance=.4,
 screw_clearance=3.4,gear_backlash=0,rotor_radius=92,inner_radius=55,outer_radius=82,
 chamber_angle=16,chamber_height=28,floor_z=150,floor_thickness=3,
 box_width=112,box_back=-40,box_front=84,box_height=88,wall=3,
 funnel_top_z=146,funnel_bottom_z=44,funnel_inner_radius=85.5,
 funnel_inner_back=8.5,funnel_wall=2.5,outlet_width=27,outlet_height=22,
 outlet_end_y=90,usb_width=14,usb_height=10,usb_center_z=17,probe_radius=6.2)
ANGLES=list(range(20,161,20))
def box(x,y,z,dx,dy,dz):return m.Manifold.cube((dx,dy,dz)).translate((x,y,z))
def cyl(r,h,z=0,x=0,y=0):return m.Manifold.cylinder(h,r,circular_segments=128).translate((x,y,z))
def ring(ri,ro,z,h):return cyl(ro,h,z)-cyl(ri,h+2,z-1)
def wedge(ri,ro,a,w,z,h):
 t=np.radians(np.linspace(a-w/2,a+w/2,33))
 pts=np.vstack((np.c_[ro*np.cos(t),ro*np.sin(t)],np.c_[ri*np.cos(t[::-1]),ri*np.sin(t[::-1])]))
 return m.CrossSection([pts]).extrude(h).translate((0,0,z))
def rim_points(r,back,z):
 a=np.linspace(math.asin(back/r),math.pi-math.asin(back/r),97)
 return [[r*math.cos(t),r*math.sin(t),z] for t in a]
def rectangle(x,y0,y1,z):return [[-x,y0,z],[x,y0,z],[x,y1,z],[-x,y1,z]]
def hopper(inner=False):
 if inner:
  return m.Manifold.hull_points(rim_points(P['funnel_inner_radius'],8.5,147)+rectangle(13.5,46.5,65.5,43.5))
 return m.Manifold.hull_points(rim_points(88,6,146)+rectangle(16,44,68,44))
def ramp_z(y):return 42-(y-44)*34/46
def ramp(inner=False):
 # A fully enclosed sloping tube; upper opening merges with hopper lumen.
 y0,y1=(44,91) if inner else (42,92)
 half=13.5 if inner else 16
 extra=0 if inner else 2.5
 pts=[]
 for x in [-half,half]:
  for y in [y0,y1]:
   for z in [ramp_z(y)-extra,ramp_z(y)+22+extra]:pts.append([x,y,z])
 return m.Manifold.hull_points(pts)
def path_void():return hopper(True)+ramp(True)
def parts():
 floor=P['floor_z'];deck=floor+3+P['axial_clearance'];mount=floor-7
 base=box(-56,-40,0,112,124,88)-box(-53,-37,3,106,118,87)
 # Front opening includes clearance for a separately bolted, enclosed chute.
 base-=box(-17,79,8,34,8,35)
 base-=box(-7,-42,12,14,9,10)
 # Rear PCB supports, edge stops and cable-tie slots.
 for x in [-24,24]:
  for y in [-29,-7]:base+=cyl(2,9,3,x,y)
 for x in [-29.4,27.8]:base+=box(x,-32.5,2.8,1.6,29,9.2)
 for y in [-34.1,-3.5]:base+=box(-29.4,y,2.8,58.8,1.6,9.2)
 for x in [-12,12]:
  for y in [-35,-1]:base-=box(x-2,y,-1,4,2,5)
 # Fixed sealed hopper wall separates the pill lumen from the rear electronics.
 # Two rear structural towers support the circular cassette above the compact box.
 for x in [-45,45]:
  base+=box(x-4,-32,3,8,8,143)
  base-=cyl(1.25,12,137,x,-28)
 for x in [-24,24]:
  base+=cyl(4,6,0,x,90)
  base+=box(x-3,82,0,6,9,4)
  base-=cyl(1.25,8,-1,x,90)
 carrier=ring(92.4,99,146,7.4)
 carrier+=cyl(99,3,146)^box(-100,-100,145,200,105,6)
 carrier-=box(-19,-9,145,27,18,6)
 for x in [-45,45]:carrier-=cyl(1.7,9,145,x,-28)
 for a in [20,90,160,250]:
  carrier+=wedge(88,96,a,7,149,1)
 # Bridge hangs below rear platform with M3x6 screws into 3 mm pilots.
 bridge=box(-27,-19,mount,54,23,3)
 bridge-=box(-17.3,-6.8,mount-1,23.6,13.6,5)
 for x in [-23,23]:
  bridge-=cyl(1.7,5,mount-1,x,-13)
  carrier-=cyl(1.25,5,145,x,-13)
 for x in [-19.25,8.25]:bridge-=cyl(1.2,5,mount-1,x,0)
 rotor=cyl(92,3,floor)-wedge(54,83,0,16,floor-1,5)
 rotor-=cyl(9.3,2.1,floor-.1)
 rotor-=cyl(1.4,5,floor-1)
 for x in [-7,7]:rotor-=cyl(1.2,5,floor-1,x,0)
 chambers=cyl(98,28,deck)-cyl(16,30,deck-1)
 for a in ANGLES:chambers-=wedge(55,82,a,16,deck-1,30)
 lid=cyl(100,3,deck+28)
 for x,y in [(-96,0),(96,0),(0,-96),(0,96)]:
  chambers-=cyl(1.7,30,deck-1,x,y)
  lid-=cyl(1.7,5,deck+27,x,y)
  carrier-=cyl(1.25,12,144,x,y)
 funnel=(hopper()+ramp())-path_void()
 # Bolted hanger ears on the front side, clear of rotor support ring.
 for x in [-30,30]:
  ear=box(x-4,78,142,8,18,4)-cyl(1.7,6,141,x,92)
  funnel+=ear
  carrier-=cyl(1.25,8,145,x,92)
 tray=box(-19,91,0,38,38,22)-box(-16.5,90,2.5,33,36.5,22)
 for x in [-24,24]:
  tray+=cyl(5,3,6,x,90)+box(18 if x>0 else -25,88,6,7,6,3)
  tray-=cyl(1.7,6,5,x,90)
 coupon=box(0,0,0,32,22,5)
 for x,r in [(6,1.6),(16,1.7),(26,1.8)]:coupon-=cyl(r,7,-1,x,11)
 return dict(enclosure=base,carrier=carrier,servo_bridge=bridge,rotating_floor=rotor,
  chambers=chambers,loading_cover=lid,funnel=funnel,collection_tray=tray,
  fit_coupon=coupon,horn_coupon=(rotor^cyl(13,3,floor)).translate((0,0,-floor)))
def references():
 return dict(esp32_board=box(-27.5,-32,12,55,28,1.6),
 esp32_components=box(-27.5,-32,13.6,55,28,14),
 sg90_body=box(-17,-6.5,114,23,13,29),
 servo_horn=cyl(9,2,150),
 usb_plug=box(-6,-57,13,12,25,8),
 wiring=box(-4,-22,28,8,6,110))
def mesh(s):
 v=s.simplify(.00001).to_mesh()
 return trimesh.Trimesh(np.asarray(v.vert_properties)[:,:3],np.asarray(v.tri_verts),process=True)
def flow_checks(solids):
 # Verify every release footprint point lies above receiving lumen, then
 # finite-size free-space paths from legal pill centres into the outlet.
 lumen=path_void()+m.Manifold.hull_points(rim_points(85.5,8.5,146.9)+rim_points(85.5,8.5,160));probe=P['probe_radius'];result=[]
 for number,a in enumerate(ANGLES,1):
  starts=[];catch_fail=[]
  for r in np.linspace(55.1,81.9,7):
   for offset in np.linspace(-7.9,7.9,7):
    t=math.radians(a+offset);p=np.array([r*math.cos(t),r*math.sin(t),145.8])
    if (cyl(.05,.05,p[2],p[0],p[1])-lumen).volume()>1e-6:catch_fail.append(p.tolist())
  failures=[];minimum_drop=999
  for r in [62,69,75]:
   for offset in [-2,0,2]:
    t=math.radians(a+offset);start=np.array([r*math.cos(t),r*math.sin(t),145])
    middle=np.array([0,56,ramp_z(56)+11]);end=np.array([0,83,ramp_z(83)+11])
    for first,last in [(start,middle),(middle,end)]:
     minimum_drop=min(minimum_drop,float(first[2]-last[2]))
     for fraction in np.linspace(0,1,41):
      p=first+(last-first)*fraction
      ball=m.Manifold.sphere(probe,24).translate(p.tolist())
      # Ball must stay in lumen, not merely miss its wall from outside.
      if (ball-lumen).volume()>.001:failures.append(p.tolist())
    starts.append(start.tolist())
  result.append(dict(compartment=number,angle=a,catch_samples=49,catch_failures=catch_fail,
   sphere_path_count=9,probe_diameter_mm=2*probe,path_failures=failures,minimum_segment_drop_mm=minimum_drop))
 return result
def render(solids,refs,out):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from mpl_toolkits.mplot3d.art3d import Poly3DCollection
 from matplotlib.patches import Patch
 colors=dict(enclosure='#6688aa',carrier='#506878',servo_bridge='#555555',
  rotating_floor='#d4a82c',chambers='#deb342',loading_cover='#e4c34b',
  funnel='#59b7bb',collection_tray='#d9b233',esp32_board='#239560',
  esp32_components='#224b37',sg90_body='#234db5',servo_horn='#eeeeee',usb_plug='#333333',wiring='#be3030')
 for mode in ['assembly','exploded','cutaway']:
  fig=plt.figure(figsize=(11,10));ax=fig.add_subplot(projection='3d')
  visible=dict(solids)
  if mode=='cutaway':
   visible.pop('loading_cover')
   # Remove front-right quadrant from stationary walls only; show real references.
   cut=box(0,-2,-1,150,160,230)
   for name in ['enclosure','funnel','chambers','carrier']:
    visible[name]=visible[name]-cut
   visible.update(refs)
  for i,(name,solid) in enumerate(visible.items()):
   if 'coupon' in name:continue
   triangles=mesh(solid).triangles.copy()
   if mode=='exploded':
    delta={'enclosure':(0,0,0),'carrier':(0,0,45),'servo_bridge':(-100,-40,30),
    'rotating_floor':(0,0,80),'chambers':(0,0,115),'loading_cover':(140,0,155),
    'funnel':(0,50,15),'collection_tray':(0,70,0)}.get(name,(0,0,0))
    triangles+=np.array(delta)
   ax.add_collection3d(Poly3DCollection(triangles,facecolor=colors.get(name,'gray'),
    alpha=.25 if mode=='cutaway' and name in ['chambers','rotating_floor'] else .9,linewidth=0))
  ax.set(xlim=(-120,250 if mode=='exploded' else 110),ylim=(-110,205 if mode=='exploded' else 135),
   zlim=(0,350 if mode=='exploded' else 195),xlabel='X, mm',ylabel='Y, mm',zlabel='Z, mm')
  ax.view_init(25,55);ax.set_box_aspect((1.2,1,1.5))
  fig.legend(handles=[Patch(color=colors[n],label=n) for n in visible if 'coupon' not in n],loc='lower center',ncol=3,fontsize=8)
  fig.subplots_adjust(bottom=.16);fig.savefig(out/(mode+'.png'),dpi=150);plt.close(fig)
 # Longitudinal centre section documents slope, elbow and separation.
 fig,ax=plt.subplots(figsize=(10,7))
 for name in ['enclosure','funnel','carrier','rotating_floor','chambers']:
  section=trimesh.intersections.mesh_plane(mesh(solids[name]),plane_normal=[1,0,0],plane_origin=[0,0,0])
  for path in section:ax.plot(path[:,1],path[:,2],color=colors[name],linewidth=1)
 ax.set(xlabel='Y, mm',ylabel='Z, mm',xlim=(-45,130),ylim=(0,190));ax.set_aspect('equal');ax.grid()
 fig.tight_layout();fig.savefig(out/'section.png',dpi=150);plt.close(fig)
def build():
 root=Path(__file__).parent;out=root/'final';out.mkdir(exist_ok=True)
 solids=parts();refs=references();report={};viewer=['// Generated viewer; authoritative source: design.py','PART="all";']
 for name,solid in solids.items():
  t=mesh(solid);counts=np.bincount(t.edges_unique_inverse)
  report[name]=dict(watertight=bool(t.is_watertight),winding=bool(t.is_winding_consistent),
   nonmanifold_edges=int(np.sum(counts!=2)),degenerate=int(np.sum(t.area_faces<1e-9)),
   components=len(solid.decompose()),volume_mm3=float(t.volume),bounds_mm=t.bounds.tolist())
  assert t.is_watertight and t.is_winding_consistent and np.all(counts==2) and np.all(t.area_faces>1e-9) and len(solid.decompose())==1,(name,report[name])
  printable=t.copy();printable.apply_translation(-t.bounds[0]);printable.export(out/(name+'.stl'))
  report[name]['stl_sha256']=hashlib.sha256((out/(name+'.stl')).read_bytes()).hexdigest()
  viewer.append('if(PART=="'+name+'"'+('' if 'coupon' in name else ' || PART=="all"')+') translate('+str(t.bounds[0].tolist())+') import("final/'+name+'.stl");')
 (root/'pill_dispenser.scad').write_text('\n'.join(viewer))
 items=[(n,s) for n,s in solids.items() if 'coupon' not in n]
 report['fixed_collisions']=[]
 for i,(n,s) in enumerate(items):
  for k,t in items[i+1:]:
   v=(s^t).volume()
   if v>1e-5:report['fixed_collisions'].append([n,k,v])
 report['reference_collisions']=[]
 for ref,s in refs.items():
  for name,t in items:
   v=(s^t).volume()
   if v>1e-5:report['reference_collisions'].append([ref,name,v])
 report['motion_collisions']=[]
 for angle in range(161):
  rotor=solids['rotating_floor'].rotate((0,0,angle))
  for name,s in items:
   if name=='rotating_floor':continue
   v=(rotor^s).volume()
   if v>1e-5:report['motion_collisions'].append([angle,name,v])
 report['flow']=flow_checks(solids)
 report['limits']='Geometry and free-space path checks, not a friction/bridging/bounce simulation.'
 (out/'validation.json').write_text(json.dumps(report,indent=2))
 (root/'mechanism.json').write_text(json.dumps(dict(protocol_version=1,home_angle_deg=0,
  compartment_angles_deg=ANGLES,parameters=P,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2))
 render(solids,refs,out)
 issues=report['fixed_collisions']+report['reference_collisions']+report['motion_collisions']
 bad_paths=sum(len(x['catch_failures'])+len(x['path_failures']) for x in report['flow'])
 print(json.dumps(dict(parts=len(solids),collisions=issues[:30],path_failures=bad_paths)))
 if issues or bad_paths:raise SystemExit('Geometry needs correction')
if __name__=='__main__':build()



