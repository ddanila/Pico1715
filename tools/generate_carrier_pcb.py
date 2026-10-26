#!/usr/bin/env python3
"""Create an unrouted review board; requires system KiCad pcbnew and footprints."""
import json
from pathlib import Path
import uuid
import pcbnew as k
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'hardware/carrier'
parts=json.loads((BASE/'connections.json').read_text())['parts']
b=k.BOARD()
def vec(x,y):return k.VECTOR2I(k.FromMM(x),k.FromMM(y))
def stable(item,key):item.SetUuid(k.KIID(str(uuid.uuid5(uuid.NAMESPACE_URL,'pico1715/pcb/'+key))))
def text(label,x,y,layer=k.Dwgs_User,size=1.2):
 t=k.PCB_TEXT(b);t.SetText(label);t.SetPosition(vec(x,y));t.SetTextSize(vec(size,size));t.SetTextThickness(k.FromMM(.15));t.SetLayer(layer);stable(t,label);b.Add(t)
def rect(x,y,w,h,layer):
 for i,(a,c) in enumerate([((x,y),(x+w,y)),((x+w,y),(x+w,y+h)),((x+w,y+h),(x,y+h)),((x,y+h),(x,y))]):
  s=k.PCB_SHAPE();s.SetShape(k.SHAPE_T_SEGMENT);s.SetStart(vec(*a));s.SetEnd(vec(*c));s.SetLayer(layer);s.SetWidth(k.FromMM(.1));stable(s,f'{layer}/{x}/{y}/{i}');b.Add(s)
nets={}
for name in sorted({p[3] for c in parts for p in c['pins'] if p[3]}):
 n=k.NETINFO_ITEM(b,"/"+name);b.Add(n);nets[name]=n
fixed={'EXT1':(32,32,90),'EXT2':(32,47,90),'EXT3':(32,62,90),'J1':(72,32,0),'J2':(139,54,0),'J3':(169,38,180),'J4':(107,30,0),'J5':(75,76,90),'SW1':(169,75,0),'D1':(118,43,0)}
logic=passives=0
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
 if ref in fixed:x,y,angle=fixed[ref]
 elif ref.startswith(('R','C')) and ref[1:].isdigit():
  x,y,angle=32+14*(passives%10),150+10*(passives//10),0;passives+=1
 else:
  x,y,angle=32+22*(logic%6),96+21*(logic//6),0;logic+=1
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
 if ref=='J4':fp.Reference().SetPosition(vec(x+6,y))
 fp.Reference().SetTextSize(vec(.9,.9));fp.Value().SetVisible(False)
 for i,field in enumerate(fp.GetFields()):stable(field,f'{ref}/field/{i}')
 b.Add(fp);placement[ref]=[x,y,angle]
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
text('X2 UNPLACED - mating connector dimensions required',100,210)
text('No host cable or edge-contact geometry implied',100,217)
text('Pico1715 / UNROUTED REVIEW ONLY',100,196,k.F_SilkS,1.4)
text('EXT1 / EXT2 / EXT3: separate HX8K via 1.27 mm cables',71,70,size=1)
text('5V ONLY',108,23,k.F_SilkS,1)
text('CDONE / GND',74,27,k.F_SilkS,.8)
# Reserve card travel and module access in the drawing, with a conservative
# temporary routing prohibition beneath the SD body pending current drawing.
rect(158,20,21,28,k.Dwgs_User)
text('SD access',166,17,size=1)
rect(126,23,26,61,k.Dwgs_User)
text('Pico USB / button access',139,16,size=1)
zone=k.ZONE(b);zone.SetIsRuleArea(True);zone.SetLayer(k.F_Cu)
zone.SetDoNotAllowTracks(True);zone.SetDoNotAllowVias(True);zone.SetDoNotAllowZoneFills(True)
zone.SetDoNotAllowPads(False);zone.SetDoNotAllowFootprints(False)
zone.SetZoneName('SD TEMPORARY HOLD: replace from current engineering drawing')
outline=zone.Outline();outline.NewOutline()
for x,y in [(161,30),(177,30),(177,46),(161,46)]:outline.Append(int(k.FromMM(x)),int(k.FromMM(y)))
stable(zone,'sd-hold');b.Add(zone)
k.SaveBoard(str(BASE/'carrier.kicad_pcb'),b)
plan={'schema':1,'fabrication_ready':False,'board_size_mm':[160,210],
 'unplaced_schematic_refs':['X2'],'mounting':'four provisional 3.2 mm M3 holes; no enclosure alignment claim',
 'fpga_attachment':'separate HX8K, three 1.27 mm 2x20 cables; mating candidate, bench continuity required',
 'placements':placement,'routing':'none','sd_keepout':'temporary F.Cu routing hold; exact multilayer restrictions pending engineering drawing'}
(BASE/'pcb-placement.json').write_text(json.dumps(plan,indent=2)+'\n')
print('Created unrouted board with',len(placement),'electrical footprints; X2 explicitly unplaced')
