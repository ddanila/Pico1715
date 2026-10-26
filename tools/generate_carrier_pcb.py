#!/usr/bin/env python3
"""Create the partially routed power/decoupling review board; requires system KiCad pcbnew and footprints."""
import json
from pathlib import Path
import uuid
import pcbnew as k
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'hardware/carrier'
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
 'R1':(62,60,180),'R2':(62,65,180),'R3':(80,60,180),'R4':(80,65,180),
 'R5':(160,66,180),'R6':(160,71,180),
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
for i,(x,y) in enumerate([(24,24),(176,24),(24,226),(176,226)],1):
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
text('Pico1715 / PARTIAL ROUTING - NOT FOR FABRICATION',100,196,k.F_SilkS,1.4)
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
# Only GND is poured. Host 5V, module 5V and both 3V3 sources remain distinct.
ground=k.ZONE(b);ground.SetLayer(k.B_Cu);ground.SetNet(nets['GND']);ground.SetZoneName('GND return - review layout')
ground.SetLocalClearance(k.FromMM(.25));ground.SetPadConnection(k.ZONE_CONNECTION_FULL)
ground.SetThermalReliefGap(k.FromMM(.25));ground.SetThermalReliefSpokeWidth(k.FromMM(.3))
outline=ground.Outline();outline.NewOutline()
for x,y in [(21,21),(179,21),(179,201),(21,201)]:outline.Append(int(k.FromMM(x)),int(k.FromMM(y)))
stable(ground,'gnd-plane');b.Add(ground)
b.BuildConnectivity();k.ZONE_FILLER(b).Fill(b.Zones())
k.SaveBoard(str(BASE/'carrier.kicad_pcb'),b)
plan={'schema':2,'fabrication_ready':False,'board_size_mm':[160,210],
 'unplaced_schematic_refs':['X2'],'mounting':'four provisional 3.2 mm M3 holes; no enclosure alignment claim',
 'fpga_attachment':'separate HX8K, three 1.27 mm 2x20 cables; mating candidate, bench continuity required',
 'placements':placement,'routing':'partial: local decoupling, ground returns and module power; signal routing incomplete',
 'decoupling':{cap:dict(device=d,supply_pin=p) for cap,(d,p) in decoupling.items()},
 'routes':routes,'vias':vias,'ground_plane':'B.Cu GND; excludes host reservation and all-layer SD hold',
 'sd_keepout':'all-copper routing hold; exact manufacturer restrictions still pending'}
(BASE/'pcb-placement.json').write_text(json.dumps(plan,indent=2)+'\n')
print('Created partially routed board:',len(routes),'tracks,',len(vias),'vias; X2 explicitly unplaced')
