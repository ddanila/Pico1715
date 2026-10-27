#!/usr/bin/env python3
"""Create the carrier review board with held SD and unplaced X2; requires system KiCad pcbnew and footprints."""
import json
import argparse
import hashlib
from pathlib import Path
import uuid
import pcbnew as k
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'hardware/carrier'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--additional',type=Path,default=BASE/'additional-routes.json')
parser.add_argument('--base-only',action='store_true')
parser.add_argument('--output-dir',type=Path,default=BASE)
args=parser.parse_args()
args.output_dir.mkdir(parents=True,exist_ok=True)
parts=json.loads((BASE/'connections.json').read_text())['parts']
b=k.BOARD()
def vec(x,y):return k.VECTOR2I(round(x*1000000),round(y*1000000))
def stable(item,key):item.SetUuid(k.KIID(str(uuid.uuid5(uuid.NAMESPACE_URL,'pico1715/pcb/'+key))))
def text(label,x,y,layer=k.Dwgs_User,size=1.2):
 t=k.PCB_TEXT(b);t.SetText(label);t.SetPosition(vec(x,y));t.SetTextSize(vec(size,size));t.SetTextThickness(k.FromMM(.15));t.SetLayer(layer);stable(t,label);b.Add(t)
def rect(x,y,w,h,layer):
 for i,(a,c) in enumerate([((x,y),(x+w,y)),((x+w,y),(x+w,y+h)),((x+w,y+h),(x,y+h)),((x,y+h),(x,y))]):
  s=k.PCB_SHAPE();s.SetShape(k.SHAPE_T_SEGMENT);s.SetStart(vec(*a));s.SetEnd(vec(*c));s.SetLayer(layer);s.SetWidth(k.FromMM(.1));stable(s,f'{layer}/{x}/{y}/{i}');b.Add(s)
nets={}
for name in sorted({p[3] for c in parts for p in c['pins'] if p[3]}):
 n=k.NETINFO_ITEM(b,"/"+name);b.Add(n);nets[name]=n
fixed={'EXT1':(32,32,90),'EXT2':(32,47,90),'EXT3':(32,62,90),'J1':(72,32,0),'J2':(139,54,0),'J3':(169,38,180),'J4':(107,30,0),'J5':(75,76,90),'SW1':(169,75,0),'D1':(121,26,180)}
fixed.update({**{f'RX{i}':(30+25*i,155,0) for i in range(1,6)},
 'U4':(65,125,0),'U5':(85,125,0),'U6':(45,100,0),'U7':(65,100,0),
 'U8':(85,100,0),'U9':(105,100,0),'U13':(85,78,0),
 'U10':(55,55,0),'U11':(75,55,0),'U12':(155,60,0),
 'ISO1':(108,45,0),'ISO2':(108,62,0),'ISO3':(108,79,0),
 'J5':(35,82,90), 'J4':(110,28,0)})
# Explicit capacitor-to-device mapping, matching the independent schematic rails.
decoupling={f'C{i}':(f'RX{i}','20') for i in range(1,6)}
decoupling.update(dict(zip([f'C{i}' for i in range(6,19)],
 [('U4','20'),('U5','5'),('U6','14'),('U7','14'),('U8','14'),
 ('U13','14'),('U9','14'),('U10','3'),('U11','3'),('U12','3'),
 ('ISO1','20'),('ISO2','20'),('ISO3','20')])))
# SD C19 remains outside the unresolved connector keepout, not falsely routed.
fixed.update({'C19':(159,49,180),'C20':(33.27,37,270),'C21':(153,40.03,0),
 'C22':(119,34,0),
 'R1':(62,60,180),'R2':(62,65,0),'R3':(80,60,180),'R4':(80,65,0),
 'R5':(160,66,180),'R6':(160,71,0),
 'R7':(160,77,0),'R8':(42,68,0),'R9':(116,82,0),
 'R10':(64,114,0),'R11':(84,114,0),'R12':(104,114,0),'R13':(85,131,0),
 'R14':(76,122,180),'R15':(90,122,180),'R16':(77,36,0),
 'R17':(93,72,180),'R18':(160,83,180),
 'R19':(117,65,0),'R20':(117,77,0),'R21':(117,71,180),
 'R22':(153,54,180),'R23':(159,55,180),'R24':(166,53,180)})
logic=passives=0
fps={}

placement={}
for c in parts:
 if not c['footprint']:continue
 ref=c['ref'];lib,name=c['footprint'].split(':')
 folder=BASE/(lib+'.pretty') if lib=='Pico1715_Carrier' else Path('/usr/share/kicad/footprints')/(lib+'.pretty')
 fp=k.FootprintLoad(str(folder),name);assert fp,c['footprint']
 fp.SetReference(ref);fp.SetValue(c['value']);fp.SetFPID(k.LIB_ID(lib,name))
 # Preserve schematic association for subsequent Update PCB from Schematic.
 root=str(uuid.uuid5(uuid.NAMESPACE_URL,'pico1715/carrier/root'))
 # Generator uses uid(ref) for the symbol instance.
 fp.SetPath(k.KIID_PATH('/'+root+'/'+str(uuid.uuid5(uuid.NAMESPACE_URL,'pico1715/carrier/'+ref))))
 stable(fp,ref)
 if ref in decoupling:
  device,pin=decoupling[ref]
  pp=next(p for p in fps[device].Pads() if p.GetNumber()==pin).GetPosition()
  # Capacitor supply pad points directly toward the top/right supply terminal.
  # A 90-degree capacitor sits above SO/TSSOP pin 20/14; SOT parts go right.
  if device in ['U5','U10','U11','U12']:
   x,y,angle=k.ToMM(pp.x)+3.0,k.ToMM(pp.y),0
  else:x,y,angle=k.ToMM(pp.x),k.ToMM(pp.y)-2.7,90
 elif ref in fixed:x,y,angle=fixed[ref]
 elif ref.startswith(('R','C')) and ref[1:].isdigit():
  x,y,angle=32+14*(passives%10),150+10*(passives//10),0;passives+=1
 else:
  x,y,angle=32+22*(logic%6),96+21*(logic//6),0;logic+=1
 x,y=round(x,6),round(y,6)
 fp.SetPosition(vec(x,y));fp.SetOrientationDegrees(angle)
 for i,item in enumerate(fp.GraphicalItems()):stable(item,f'{ref}/graphic/{i}')
 for i,zone in enumerate(fp.Zones()):stable(zone,f'{ref}/zone/{i}')
 pinmap={str(p[0]):p[3] for p in c['pins']}
 for i,pad in enumerate(fp.Pads()):
  stable(pad,f'{ref}/pad/{i}');net=pinmap.get(pad.GetNumber())
  if net:pad.SetNet(nets[net])
 fp.Reference().SetPosition(vec(x,y-8 if ref.startswith(('RX','U','ISO')) else y-3))
 fp.Reference().SetTextAngle(k.EDA_ANGLE(0,k.DEGREES_T))
 if ref.startswith('EXT'):fp.Reference().SetPosition(vec(x+12,y-4))
 if ref in ['U5','U10','U11','U12']:fp.Reference().SetPosition(vec(x,y-3))
 if ref in decoupling:fp.Reference().SetPosition(vec(x+3,y))
 if ref=='C11':fp.Reference().SetPosition(vec(x+3,y-2.5))
 if ref=='J4':fp.Reference().SetPosition(vec(x+6,y))
 fp.Reference().SetTextSize(vec(.9,.9));fp.Value().SetVisible(False)
 for i,field in enumerate(fp.GetFields()):stable(field,f'{ref}/field/{i}')
 b.Add(fp);fps[ref]=fp;placement[ref]=[x,y,angle]
# Deliberately roomy review outline, not a PC1715 enclosure-fit claim.
rect(20,20,160,210,k.Edge_Cuts)
for i,(x,y) in enumerate([(24,24),(157,24),(24,226),(176,226)],1):
 fp=k.FootprintLoad('/usr/share/kicad/footprints/MountingHole.pretty','MountingHole_3.2mm_M3')
 fp.SetReference('H'+str(i));fp.SetPosition(vec(x,y));stable(fp,'H'+str(i))
 for j,pad in enumerate(fp.Pads()):stable(pad,f'H{i}/pad/{j}')
 for j,item in enumerate(fp.GraphicalItems()):stable(item,f'H{i}/graphic/{j}')
 fp.Value().SetVisible(False);fp.Reference().SetPosition(vec(x,y+4 if y<50 else y-4))
 for j,field in enumerate(fp.GetFields()):stable(field,f'H{i}/field/{j}')
 b.Add(fp)
rect(26,203,148,20,k.Dwgs_User)
text('X2 RESERVED - installation and contact fit pending',100,210)
text('No host cable or edge-contact geometry implied',100,217)
text('Pico1715 / SD HELD, X2 UNPLACED - NOT FOR FABRICATION',100,196,k.F_SilkS,1.4)
text('EXT1 / EXT2 / EXT3: separate HX8K via 1.27 mm cables',100,180,size=1)
text('5V ONLY',108,23,k.F_SilkS,1)
text('CDONE / GND',74,27,k.F_SilkS,.8)
# Reserve card travel and module access in the drawing, with a conservative
# temporary routing prohibition beneath the SD body pending current drawing.
rect(158,20,21,28,k.Dwgs_User)
text('SD access',166,17,size=1)
rect(126,23,26,61,k.Dwgs_User)
text('Pico USB / button access',139,16,size=1)
zone=k.ZONE(b);zone.SetIsRuleArea(True);zone.SetLayerSet(k.LSET.AllCuMask())
zone.SetDoNotAllowTracks(True);zone.SetDoNotAllowVias(True);zone.SetDoNotAllowZoneFills(True)
zone.SetDoNotAllowPads(False);zone.SetDoNotAllowFootprints(False)
zone.SetZoneName('SD ALL-COPPER HOLD: current engineering drawing review pending')
outline=zone.Outline();outline.NewOutline()
for x,y in [(160,28),(178,28),(178,47),(160,47)]:outline.Append(int(k.FromMM(x)),int(k.FromMM(y)))
stable(zone,'sd-hold');b.Add(zone)
# Settled local routes; neither X2 nor SD signal routing is invented here.
routes=[];vias=[]
def pad(ref,num):return next(p for p in fps[ref].Pads() if p.GetNumber()==str(num))
def xy(p):return [round(k.ToMM(p.GetPosition().x),6),round(k.ToMM(p.GetPosition().y),6)]
def track(net,points,width=.3,layer=k.F_Cu,tag=''):
 points=[[round(v,6) for v in point] for point in points]
 for j,(a,c) in enumerate(zip(points,points[1:])):
  if a==c:continue
  t=k.PCB_TRACK(b);t.SetStart(vec(*a));t.SetEnd(vec(*c));t.SetWidth(k.FromMM(width));t.SetLayer(layer);t.SetNet(nets[net]);stable(t,f'route/{tag}/{j}');b.Add(t)
  routes.append(dict(net=net,start=a,end=c,width=width,layer='F.Cu' if layer==k.F_Cu else 'B.Cu',tag=tag))
def via(net,at,tag):
 at=[round(v,6) for v in at]
 v=k.PCB_VIA(b);v.SetPosition(vec(*at));v.SetWidth(k.FromMM(.6));v.SetDrill(k.FromMM(.3));v.SetViaType(k.VIATYPE_THROUGH);v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNet(nets[net]);stable(v,'via/'+tag);b.Add(v)
 vias.append(dict(net=net,at=at,diameter=.6,drill=.3,tag=tag))
for cap,(dev,pin) in decoupling.items():
 src=pad(dev,pin);dest=pad(cap,1);assert src.GetNetname()==dest.GetNetname()
 track(src.GetNetname()[1:],[xy(src),xy(dest)],tag=cap+'/supply')
 g=pad(cap,2);gx,gy=xy(g);at=[gx,gy-1.3] if placement[cap][2]==90 else [gx,gy+1.3]
 track('GND',[xy(g),at],tag=cap+'/ground');via('GND',at,cap)
# Individual ground pins escape outward into a continuous bottom return plane.
for ref in [*['RX'+str(i) for i in range(1,6)],*['U'+str(i) for i in range(4,14)],'ISO1','ISO2','ISO3']:
 for pp in fps[ref].Pads():
  if pp.GetNetname()!='/GND':continue
  x,y=xy(pp);cx=placement[ref][0];at=[round(x+(-1.15 if x<cx else 1.15),6),y]
  track('GND',[[x,y],at],.25,tag=ref+'/gnd/'+pp.GetNumber());via('GND',at,ref+'/'+pp.GetNumber())
# Local bulk capacitors and module supply path, separated from V5_HOST.
track('V3P3',[xy(pad('EXT1',3)),xy(pad('C20',1))],.5,tag='fpga-bulk')
track('V5_MODULE',[xy(pad('EXT1',1)),[29,32],[29,25.5],[106,25.5],[106,28],xy(pad('J4',1))],.8,tag='fpga-5v')
track('V5_MODULE',[xy(pad('J4',1)),[110,24.95],[119,24.95],xy(pad('D1',2))],.8,tag='module-5v')
track('V5_MODULE',[xy(pad('D1',2)),[119,31],xy(pad('C22',1))],.8,tag='module-bulk')
track('P_VSYS',[xy(pad('D1',1)),[153,26],[153,32.41],xy(pad('J2',39))],.8,tag='pico-vsys')
track('P3V3',[xy(pad('J2',36)),xy(pad('C21',1))],.5,tag='pico-bulk')
for ref in ['C20','C21','C22']:
 pp=pad(ref,2);x,y=xy(pp);at=[x,y+1.5]
 track('GND',[[x,y],at],.4,tag=ref+'/ground');via('GND',at,ref)
# Local supervisor pull-up/pull-down networks. Power distribution and the
# downstream qualification gates remain separate routing work.
for dev,up,down,rail,pg in [('U10','R1','R2','V3P3','PG3'),
                           ('U11','R3','R4','V5_HOST','PG5'),
                           ('U12','R5','R6','P3V3','PGP')]:
 sx,sy=xy(pad(dev,3));ux,uy=xy(pad(up,1))
 track(rail,[[sx,sy],[sx,sy+3],[ux,sy+3],[ux,uy]],tag=dev+'/pullup-supply')
 px,py=xy(pad(dev,2));ax,ay=xy(pad(up,2));dx,dy=xy(pad(down,1))
 junction=[ax,ay+2]
 track(pg,[[px,py],[px,sy+4],[ax,sy+4],[ax,ay]],tag=dev+'/sense')
 track(pg,[[ax,ay],junction,[dx,dy]],tag=dev+'/divider')
# Every resistor tied to ground receives a short independent plane return.
for ref in ['R2','R4','R6','R7','R8','R9','R10','R11','R12','R13','R16','R19','R20']:
 pp=pad(ref,2);assert pp.GetNetname()=='/GND'
 x,y=xy(pp);at=[x,y+1.5]
 track('GND',[[x,y],at],.3,tag=ref+'/ground');via('GND',at,ref)
# FPGA 3V3 distribution, entirely on the front to retain the bottom return plane.
track('V3P3',[xy(pad('C20',1)),[26,36.05],[26,51],[26,140],[122,140],[162.65,140]],.8,tag='3v3/trunk-west-south')
track('V3P3',[[122,140],[122,89],[122,69],[122,40.325]],.8,tag='3v3/trunk-east')
track('V3P3',[[26,51],[55.9375,51],xy(pad('U10',3))],.5,tag='3v3/supervisor')
for i in range(1,6):
 ref='C'+str(i);x,y=xy(pad(ref,1))
 track('V3P3',[[x+3,140],[x+3,y],[x,y]],.5,tag='3v3/'+ref)
track('V3P3',[[122,89],[50.475,89]],.5,tag='3v3/logic-spine')
for ref in ['C8','C9','C10','C12']:
 x,y=xy(pad(ref,1))
 track('V3P3',[[x+3,89],[x+3,y],[x,y]],.5,tag='3v3/'+ref)
for ref in ['C16','C17','C18']:
 x,y=xy(pad(ref,1))
 track('V3P3',[[122,y],[x,y]],.5,tag='3v3/'+ref)
x,y=xy(pad('C11',1))
track('V3P3',[[122,69],[x+3,69],[x+3,y],[x,y]],.5,tag='3v3/C11')
track('V3P3',[[110.475,94.44],[110.475,100],xy(pad('U9',11))],.3,tag='3v3/unused-inputs')
track('V3P3',[[110.475,97.46],xy(pad('U9',13))],.3,tag='3v3/unused-input-13')
track('V3P3',[[93.9125,69],xy(pad('R17',1))],.3,tag='3v3/link-pullup')
track('V3P3',[[114.5,69],[114.5,71],xy(pad('R21',2))],.3,tag='3v3/link-idle')
track('V3P3',[[70.56,89],xy(pad('J5',15))],.3,tag='3v3/probe')
track('V3P3',[[162.65,140],[174,140],[174,79],[171.5,79],xy(pad('SW1',3))],.5,tag='3v3/mode-switch')
# Pico-domain distribution stops outside the unresolved SD connector hold.
track('P3V3',[xy(pad('C21',1)),[152.05,43],[156,43],[156,51.5],[156,57],[155.9375,57],xy(pad('U12',3))],.5,tag='p3v3/trunk')
track('P3V3',[[153.9125,51.5],[166.9125,51.5]],.3,tag='p3v3/pullup-spine')
for ref in ['R22','R23','R24']:
 x,y=xy(pad(ref,1))
 track('P3V3',[[x,51.5],[x,y]],.3,tag='p3v3/'+ref)
track('P3V3',[[159.95,51.5],xy(pad('C19',1))],.3,tag='p3v3/sd-bypass')
x,y=xy(pad('C19',2));at=[x,y+1.5]
track('GND',[[x,y],at],.3,tag='C19/ground');via('GND',at,'C19')
# Host rail interconnect; source remains the unplaced X2, not module 5V.
track('V5_HOST',[xy(pad('R3',1)),[82,60],[82,68],[78,72],[78,87.5]],.5,tag='host5/north')
track('V5_HOST',[[78,90.5],[78,110],[79,117]],.5,tag='host5/south')
track('V5_HOST',[[79,117],[72.65,117],[72.65,117.535],xy(pad('C6',1))],.5,tag='host5/U4')
track('V5_HOST',[[79,117],[79,122],xy(pad('R14',1))],.3,tag='host5/data-pullup')
track('V5_HOST',[[79,117],[94,117],[94,122],xy(pad('R15',1))],.5,tag='host5/ieo-pullup')
track('V5_HOST',[[87.1875,117],xy(pad('C7',1))],.5,tag='host5/U5')
# Short bottom-layer crossings preserve isolation between the power domains.
def bridge(net,a,z,tag):
 via(net,a,tag+'/a');via(net,z,tag+'/z')
 track(net,[a,z],.5,k.B_Cu,tag=tag)
bridge('V5_HOST',[78,87.5],[78,90.5],'host5/logic-crossing')
track('V5_HOST',[[94,117],[120.5,117]],.5,tag='host5/priority-west')
bridge('V5_HOST',[120.5,117],[123.5,117],'host5/east-crossing')
track('V5_HOST',[[123.5,117],[172,117],[172,85],[160.9125,85],xy(pad('R18',1))],.5,tag='host5/priority-east')
# Probe supply passes between Pico header rows at 0.3 mm width, then crosses
# three independent front-layer branches with short bottom-layer bridges.
track('P3V3',[[152.05,41.3],[125,41.3],[125,86],[123.5,86]],.3,tag='p3v3/probe-east')
bridge('P3V3',[123.5,86],[120.5,86],'p3v3/east-crossing')
track('P3V3',[[120.5,86],[79.5,86]],.3,tag='p3v3/probe-middle')
bridge('P3V3',[79.5,86],[76.5,86],'p3v3/host-crossing')
track('P3V3',[[76.5,86],[72,86]],.3,tag='p3v3/probe-west')
bridge('P3V3',[72,86],[69,86],'p3v3/probe-crossing')
track('P3V3',[[69,86],[68.02,86],xy(pad('J5',14))],.3,tag='p3v3/probe-pad')
# Local control branches with settled footprints and no host/SD geometry.
track('CDONE',[xy(pad('J1',1)),[76.0875,32],xy(pad('R16',1))],.3,tag='control/cdone-pulldown')
track('MODE_CTL',[xy(pad('R7',1)),[159.0875,80],[169,80],xy(pad('SW1',2))],.3,tag='control/mode-pulldown')
track('H_PRIORITY',[xy(pad('R18',2)),[157,83],[157,73.8],xy(pad('SW1',5))],.3,tag='control/priority-pullup')
# Internal qualification-gate paths. Short crossovers keep independent gate
# outputs separate where the SOIC pin order requires a crossing.
track('POWER_GOOD',[xy(pad('U6',3)),[44,98.73],[45,98],[46,98],[46,98.73],xy(pad('U6',12))],.25,tag='interlock/power-good')
track('RAILS_OK',[xy(pad('U6',6)),[44,102.54],[45,101.8],[46,102.54],xy(pad('U6',9))],.25,tag='interlock/rails-ok')
track('LINK_OK',[xy(pad('U6',8)),[49,103.81],[49,97.46],xy(pad('U6',13))],.25,tag='interlock/link-feedback')
track('POWERED',[xy(pad('U6',11)),[48,100]],.25,tag='interlock/powered-exit')
bridge('POWERED',[48,100],[50,100],'interlock/powered-crossing')
track('POWERED',[[50,100],[53,100],[56.81,96.19],xy(pad('U7',1))],.25,tag='interlock/powered')
track('QUALIFIED',[xy(pad('U7',3)),[61.2,98.73],[61.2,100],xy(pad('U7',4))],.25,tag='interlock/qualified')
track('BACKEND_OK',[xy(pad('U7',6)),xy(pad('U7',9))],.25,tag='interlock/backend-ok')
track('RESET_OK',[xy(pad('U7',8)),[69.5,103.81],[69.5,98.73],xy(pad('U7',12))],.25,tag='interlock/reset-ok')
track('ARMED',[xy(pad('U7',11)),[68.5,100]],.25,tag='interlock/armed-exit')
bridge('ARMED',[68.5,100],[70.5,100],'interlock/armed-crossing')
track('ARMED',[[70.5,100],[73,100],[76.81,96.19],[77,96.19]],.25,tag='interlock/armed-west')
bridge('ARMED',[77,96.19],[79,96.19],'interlock/armed-host-crossing')
track('ARMED',[[79,96.19],xy(pad('U8',1)),[84,96.19],[84,97.46],[84,98.73],[84,100],[84,102.54],xy(pad('U8',9))],.25,tag='interlock/armed')
for pin in [4,12,13]:
 x,y=xy(pad('U8',pin))
 track('ARMED',[[84,y],[x,y]],.25,tag='interlock/armed-'+str(pin))
# FPGA and host supervisor outputs feed the probe header and both PG3 inputs.
track('PG3',[xy(pad('R2',1)),[58,65],[58,79],[37.54,79],xy(pad('J5',2)),[37.54,100],[40,100],xy(pad('U6',4))],.25,tag='interlock/pg3')
track('PG3',[[40,100],[40,96.19],xy(pad('U6',1))],.25,tag='interlock/pg3-input')
track('PG5',[xy(pad('R4',1)),[75,65],[75,77],[59.5,77]],.25,tag='interlock/pg5-source')
bridge('PG5',[59.5,77],[56.5,77],'interlock/pg5-pg3-crossing')
track('PG5',[[56.5,77],[40.08,77],[40.08,78]],.25,tag='interlock/pg5-probe-north')
bridge('PG5',[40.08,78],[40.08,80],'interlock/pg5-probe-crossing')
track('PG5',[[40.08,80],xy(pad('J5',3)),[40.08,93],[38.8,93],[38.8,97.46],[39,97.46]],.25,tag='interlock/pg5-probe-south')
bridge('PG5',[39,97.46],[41,97.46],'interlock/pg5-input-crossing')
track('PG5',[[41,97.46],xy(pad('U6',2))],.25,tag='interlock/pg5-input')
# Pico supervisor crosses the two supply spines and probe power branches.
track('PGP',[xy(pad('R6',1)),[153,71],[153,84],[126.5,84]],.25,tag='interlock/pgp-source')
bridge('PGP',[126.5,84],[120.5,84],'interlock/pgp-east-crossing')
track('PGP',[[120.5,84],[119.5,84.5],[114.5,84.5],[114,84],[79.5,84]],.25,tag='interlock/pgp-middle')
bridge('PGP',[79.5,84],[76.5,84],'interlock/pgp-host-crossing')
track('PGP',[[76.5,84],[72,84]],.25,tag='interlock/pgp-west')
bridge('PGP',[72,84],[66.5,84],'interlock/pgp-probe-crossing')
track('PGP',[[66.5,84],[44,84],[42.62,84],xy(pad('J5',4))],.25,tag='interlock/pgp-probe')
track('PGP',[[44,84],[44,94]],.25,tag='interlock/pgp-input-north')
bridge('PGP',[44,94],[44,101.27],'interlock/pgp-input-crossing')
track('PGP',[[44,101.27],xy(pad('U6',5))],.25,tag='interlock/pgp-input')
# Isolator disable distribution: U13 and the default-off pull-up R17 reach
# all three OE pins, with short back-layer rail crossings.
track('LINK_OE_N',[xy(pad('U13',3)),[84,76.73]],.25,tag='link-enable/gate-exit')
via('LINK_OE_N',[84,76.73],'link-enable/gate-a')
via('LINK_OE_N',[92.0875,74],'link-enable/gate-z')
track('LINK_OE_N',[[84,76.73],[84,73],[92.0875,73],[92.0875,74]],.25,k.B_Cu,tag='link-enable/gate-crossing')
track('LINK_OE_N',[xy(pad('R17',2)),[92.0875,74],[92.0875,82.8],[114,82.8],[114,76.725],[114,75.8]],.25,tag='link-enable/south')
track('LINK_OE_N',[xy(pad('ISO1',19)),[114,42.725],[114,55.8]],.25,tag='link-enable/north')
bridge('LINK_OE_N',[114,55.8],[114,58.8],'link-enable/middle-rail-crossing')
track('LINK_OE_N',[[114,58.8],[114,59.725],[114,67]],.25,tag='link-enable/middle')
bridge('LINK_OE_N',[114,67],[114,75.8],'link-enable/south-rail-crossing')
for ref,y in [('ISO2',59.725),('ISO3',76.725)]:
 track('LINK_OE_N',[[114,y],xy(pad(ref,19))],.25,tag='link-enable/'+ref)
# LINK_OK reaches its probe, FPGA header and both U13 inputs.
track('LINK_OK',[[49,97.46],[49,95.5],[52.78,95.5],[52.78,90.5]],.25,tag='link-ok/logic')
bridge('LINK_OK',[52.78,90.5],[52.78,83],'link-ok/probe-power-crossing')
track('LINK_OK',[[52.78,83],xy(pad('J5',8)),[52.78,80.5]],.25,tag='link-ok/probe')
bridge('LINK_OK',[52.78,80.5],[52.78,75.5],'link-ok/supervisor-crossing')
track('LINK_OK',[[52.78,75.5],[52.78,74.5],[49.78,74.5],[49.78,65.5]],.25,tag='link-ok/header-approach')
via('LINK_OK',[49.78,65.5],'link-ok/header')
track('LINK_OK',[[49.78,65.5],xy(pad('EXT3',29))],.25,k.B_Cu,tag='link-ok/header')
track('LINK_OK',[[52.78,74.5],[56.5,74.5]],.25,tag='link-ok/gate-west')
bridge('LINK_OK',[56.5,74.5],[59.5,74.5],'link-ok/pg3-crossing')
track('LINK_OK',[[59.5,74.5],[74,74.5]],.25,tag='link-ok/gate-middle')
bridge('LINK_OK',[74,74.5],[79.5,74.5],'link-ok/host-crossing')
track('LINK_OK',[[79.5,74.5],[81,74.5],[81,74.19],xy(pad('U13',1))],.25,tag='link-ok/gate-a')
track('LINK_OK',[[81,74.5],[81,75.46],xy(pad('U13',2))],.25,tag='link-ok/gate-b')
# CDONE from the module-status connector to probe and rail qualification.
track('CDONE',[xy(pad('J1',1)),[70,32],[70,70],[59.5,70]],.25,tag='cdone/source')
bridge('CDONE',[59.5,70],[48,70],'cdone/header-crossing')
track('CDONE',[[48,70],[45.16,70],[45.16,75.5]],.25,tag='cdone/probe-north')
bridge('CDONE',[45.16,75.5],[45.16,80.5],'cdone/supervisor-crossing')
track('CDONE',[[45.16,80.5],xy(pad('J5',5)),[45.16,83]],.25,tag='cdone/probe')
bridge('CDONE',[45.16,83],[45.16,85],'cdone/pgp-crossing')
track('CDONE',[[45.16,85],[45.16,93.5]],.25,tag='cdone/input-north')
bridge('CDONE',[45.16,93.5],[45.16,100.5],'cdone/input-crossing')
track('CDONE',[[45.16,100.5],[46.1,101.27],xy(pad('U6',10))],.25,tag='cdone/input')
# FPGA personality declaration and its pull-down/probe feed U7's qualifier.
track('PERSONALITY_CTL',[xy(pad('EXT2',38)),[54.86,44.4],[66,44.4],[66,68],[59.5,68]],.25,tag='personality/source')
bridge('PERSONALITY_CTL',[59.5,68],[48,68],'personality/header-crossing')
track('PERSONALITY_CTL',[[48,68],[48,66.5],[41.0875,66.5],xy(pad('R8',1))],.25,tag='personality/pulldown')
bridge('PERSONALITY_CTL',[66,68],[66,80.5],'personality/qualification-crossing')
track('PERSONALITY_CTL',[[66,80.5],[54,80.5]],.25,tag='personality/probe-east')
track('PERSONALITY_CTL',[[54,80.5],[54,79.6],[51.5,79.6],[50.24,80.5]],.25,tag='personality/link-crossing')
track('PERSONALITY_CTL',[[50.24,80.5],xy(pad('J5',7)),[50.24,83]],.25,tag='personality/probe')
via('PERSONALITY_CTL',[50.24,83],'personality/input-a')
via('PERSONALITY_CTL',[54,92],'personality/input-z')
track('PERSONALITY_CTL',[[50.24,83],[50.24,92],[54,92]],.25,k.B_Cu,tag='personality/power-crossing')
track('PERSONALITY_CTL',[[54,92],[60,92],[60,94.5]],.25,tag='personality/input-north')
bridge('PERSONALITY_CTL',[60,94.5],[60,97.46],'personality/powered-crossing')
track('PERSONALITY_CTL',[[60,97.46],xy(pad('U7',2))],.25,tag='personality/input')
# Reviewed supplemental routes are data, so regeneration does not depend on
# the router or repeat its heuristic search. Reject stale placement/hand copper.
base_route_sha256=hashlib.sha256(json.dumps(dict(placements=placement,routes=routes,vias=vias),sort_keys=True).encode()).hexdigest()
ground_layers=['B.Cu']
if not args.base_only:
 extra=json.loads(args.additional.read_text())
 assert extra['base_route_sha256']==base_route_sha256,'supplemental routes need re-review against changed base'
 assert extra['omitted_refs']==['J3'] and extra['unplaced_refs']==['X2']
 ground_layers=extra.get('ground_layers',['B.Cu'])
 assert ground_layers in [['B.Cu'],['B.Cu','F.Cu']]
 for i,t in enumerate(extra['routes']):
  assert t['layer'] in ['F.Cu','B.Cu'] and t['width']>=.25
  track(t['net'],[t['start'],t['end']],t['width'],k.F_Cu if t['layer']=='F.Cu' else k.B_Cu,tag='additional/'+str(i))
 for i,v in enumerate(extra['vias']):
  assert v['diameter']==.6 and v['drill']==.3
  via(v['net'],v['at'],'additional/'+str(i))
# Only GND is poured. Host 5V, module 5V and both 3V3 sources remain distinct.
for layer_name in ground_layers:
 layer=k.B_Cu if layer_name=='B.Cu' else k.F_Cu
 ground=k.ZONE(b);ground.SetLayer(layer);ground.SetNet(nets['GND']);ground.SetZoneName('GND return '+layer_name+' - review layout')
 ground.SetLocalClearance(k.FromMM(.25));ground.SetPadConnection(k.ZONE_CONNECTION_FULL)
 ground.SetThermalReliefGap(k.FromMM(.25));ground.SetThermalReliefSpokeWidth(k.FromMM(.3))
 outline=ground.Outline();outline.NewOutline()
 for x,y in [(21,21),(179,21),(179,201),(21,201)]:outline.Append(int(k.FromMM(x)),int(k.FromMM(y)))
 stable(ground,'gnd-plane' if layer_name=='B.Cu' else 'gnd-plane-front');b.Add(ground)
b.BuildConnectivity();k.ZONE_FILLER(b).Fill(b.Zones())
k.SaveBoard(str(args.output_dir/'carrier.kicad_pcb'),b)
plan={'base_route_sha256':base_route_sha256,'ground_layers':ground_layers,'schema':2,'fabrication_ready':False,'board_size_mm':[160,210],
 'unplaced_schematic_refs':['X2'],'mounting':'four provisional 3.2 mm M3 holes; no enclosure alignment claim',
 'fpga_attachment':'separate HX8K, three 1.27 mm 2x20 cables; mating candidate, bench continuity required',
 'placements':placement,'routing':('placed non-SD terminals connected; J3 held and X2 unplaced' if not args.base_only else 'hand-routed baseline only; signals incomplete'),
 'decoupling':{cap:dict(device=d,supply_pin=p) for cap,(d,p) in decoupling.items()},
 'routes':routes,'vias':vias,'ground_plane':' + '.join(ground_layers)+' GND; excludes host reservation and all-layer SD hold',
 'sd_keepout':'all-copper routing hold; exact manufacturer restrictions still pending'}
(args.output_dir/'pcb-placement.json').write_text(json.dumps(plan,indent=2)+'\n')
print('Created review board:',len(routes),'tracks,',len(vias),'vias; X2 explicitly unplaced')
