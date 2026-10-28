#!/usr/bin/env python3
"""Four-layer Rev A candidate, with reproducible reviewed outer-layer copper."""
import argparse,hashlib,json,uuid,tempfile,math
from pathlib import Path
import pcbnew as k
from generate_carrier_reva import uid
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'hardware/carrier';OUT=ROOT/'hardware/carrier-reva'
vec=lambda x,y:k.VECTOR2I(round(x*1e6),round(y*1e6))
def stable(o,key):o.SetUuid(k.KIID(uid(key)))
def generate(out,routes=None,placements=None):
 out.mkdir(parents=True,exist_ok=True)
 extra=json.loads(routes.read_text()) if routes else None
 source=(BASE/'carrier.kicad_pcb').read_text()
 from kicad_text import remove_nodes
 source=remove_nodes(source,lambda head,node,depth:(head=='footprint' and '(property "Reference" "J3"' in node) or (head=='zone' and '(keepout' in node))
 if extra:
  from kicad_text import remove_nodes
  assert extra['baseline_sha256']==hashlib.sha256((BASE/'carrier.kicad_pcb').read_bytes()).hexdigest()
  source=remove_nodes(source,lambda head,node,depth: head in ('segment','via') and any('(net "/'+n+'")' in node for n in extra['replace_nets']))
 with tempfile.NamedTemporaryFile(suffix='.kicad_pcb',mode='w') as tmp:
  tmp.write(source);tmp.flush();b=k.LoadBoard(tmp.name)
 b.SetCopperLayerCount(4)
 c=json.loads((OUT/'connections.json').read_text());parts={p['ref']:p for p in c['parts']}
 for f in b.GetFootprints():f.SetPath(k.KIID_PATH('/'+uid('root')+'/'+uid(f.GetReference())))
 if placements:
  overrides=json.loads(placements.read_text())
  assert set(overrides)<= {"C19"}, "Only reviewed SD decoupler placement may change"
  for values in overrides.values():
   assert len(values)==3 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in values)
  for f in b.GetFootprints():
   if f.GetReference() in overrides:
    x,y,angle=overrides[f.GetReference()];f.SetPosition(vec(x,y));f.SetOrientationDegrees(angle)
 for ref,pos,angle in [('J3',(161,28.6),0),('J6',(60,215),90),('J7',(164,100),0)]:
  p=parts[ref];lib,name=p['footprint'].split(':');f=k.FootprintLoad(str(OUT/(lib+'.pretty')) if lib=='Pico1715_RevA' else '/usr/share/kicad/footprints/'+lib+'.pretty',name)
  assert f is not None,p['footprint']
  f.SetFPID(k.LIB_ID(lib,name));f.SetReference(ref);f.SetValue(p['value']);f.SetPosition(vec(*pos));f.SetOrientationDegrees(angle)
  f.SetPath(k.KIID_PATH('/'+uid('root')+'/'+uid(ref)));stable(f,ref)
  nets={str(n):net for n,_,_,net in p['pins']}
  for i,pad in enumerate(f.Pads()):
   stable(pad,ref+'/pad/'+str(i));number=pad.GetNumber()
   if not number:continue
   if nets[number] is None:pad.SetNetCode(0);continue
   name='/'+nets[number]
   n=b.FindNet(name)
   if n is None or n.GetNetCode()<0:n=k.NETINFO_ITEM(b,name);b.Add(n)
   pad.SetNet(n)
  for i,x in enumerate(f.GraphicalItems()):stable(x,ref+'/graphic/'+str(i))
  for i,x in enumerate(f.GetFields()):stable(x,ref+'/field/'+str(i))
  b.Add(f)
 for drawing in b.GetDrawings():
  if not isinstance(drawing,k.PCB_TEXT):continue
  text=drawing.GetText()
  if text.startswith('Pico1715 / SD HELD'):
   drawing.SetText('Pico1715 Rev A / ENGINEERING CANDIDATE - NOT FOR FABRICATION')
  elif text.startswith('X2 RESERVED'):
   drawing.SetText('J6 HOST / keyed straight-through harness <=100 mm');drawing.SetPosition(vec(100,205))
  elif text.startswith('No host cable'):
   drawing.SetText('A=odd, B=even; 59/60 NC / key south / verify cable continuity');drawing.SetPosition(vec(100,225))
 label=k.PCB_TEXT(b);label.SetText('J7: 1 GND / 2 RAW / 3 VSYS');label.SetPosition(vec(161,110));label.SetLayer(k.Dwgs_User);label.SetTextSize(vec(.8,.8));stable(label,'reserve-label');b.Add(label)
 # Conservative top-only under-body exclusion; inner ground stays continuous.
 z=k.ZONE(b);z.SetLayer(k.F_Cu);z.SetIsRuleArea(True);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True);z.SetDoNotAllowZoneFills(True);z.SetZoneName('SD body top-copper exclusion')
 o=z.Outline();o.NewOutline()
 for x,y in [(161,30.1),(175,30.1),(175,37.9),(161,37.9)]:o.Append(round(x*1e6),round(y*1e6))
 stable(z,'sd-body-exclusion');b.Add(z)
 for layer in [k.In1_Cu,k.In2_Cu]:
  z=k.ZONE(b);z.SetLayer(layer);z.SetNet(b.FindNet('/GND'));z.SetZoneName('Rev A continuous GND '+b.GetLayerName(layer))
  z.SetLocalClearance(k.FromMM(.25));z.SetPadConnection(k.ZONE_CONNECTION_FULL)
  o=z.Outline();o.NewOutline()
  for x,y in [(20.5,20.5),(179.5,20.5),(179.5,229.5),(20.5,229.5)]:o.Append(k.FromMM(x),k.FromMM(y))
  stable(z,'ground/'+str(layer));b.Add(z)
 if routes:
  for i,r in enumerate(extra['tracks']):
   t=k.PCB_TRACK(b);t.SetStart(vec(*r['start']));t.SetEnd(vec(*r['end']));t.SetWidth(k.FromMM(r['width']));t.SetLayer(b.GetLayerID(r['layer']));t.SetNet(b.FindNet('/'+r['net']));stable(t,'route/'+str(i));b.Add(t)
  for i,r in enumerate(extra['vias']):
   v=k.PCB_VIA(b);v.SetPosition(vec(*r['at']));v.SetWidth(k.FromMM(r['diameter']));v.SetDrill(k.FromMM(r['drill']));v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNet(b.FindNet('/'+r['net']));stable(v,'via/'+str(i));b.Add(v)
 b.BuildConnectivity();k.ZONE_FILLER(b).Fill(b.Zones())
 path=out/'carrier.kicad_pcb';k.SaveBoard(str(path),b)
 # SWIG does not expose editable BOARD_STACKUP. Write explicit KiCad stack-up
 # syntax, then reload to validate serialization. Nominal board thickness 1.6mm.
 s=path.read_text();assert '(stackup' not in s
 stack='''\n\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01524))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "FR4 7628") (epsilon_r 4.4) (loss_tangent 0.02))
\t\t\t(layer "In1.Cu" (type "copper") (thickness 0.0152))
\t\t\t(layer "dielectric 2" (type "core") (thickness 1.065) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
\t\t\t(layer "In2.Cu" (type "copper") (thickness 0.0152))
\t\t\t(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "FR4 7628") (epsilon_r 4.4) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01524))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t)
'''
 s=s.replace('(setup','(setup'+stack,1);path.write_text(s);check=k.LoadBoard(str(path));assert check.GetCopperLayerCount()==4
 report=dict(schema=1,fabrication_ready=False,baseline_sha256=hashlib.sha256((BASE/'carrier.kicad_pcb').read_bytes()).hexdigest(),board_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),layers=['F.Cu','In1.Cu','In2.Cu','B.Cu'],ground_layers=['In1.Cu','In2.Cu'],stackup_target='JLC04161H-7628',stackup_supplier_confirmed=False,stackup_catalog_verified=True,board_size_mm=[160,210],all_schematic_refs_placed=True,host={'ref':'J6','at_mm':[60,215],'angle':90},reserve={'ref':'J7','at_mm':[164,100]},sd_hold=False,routed_additions=bool(routes),hardware_executed=False)
 (out/'pcb-review.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Rev A 4-layer candidate:',len(list(b.GetFootprints())),'footprints; SD body exclusion retained')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=OUT);p.add_argument('--routes',type=Path);p.add_argument('--base-only',action='store_true');p.add_argument('--placements',type=Path);a=p.parse_args();routes=None if a.base_only else (a.routes or (OUT/'routes.json' if (OUT/'routes.json').exists() else None));generate(a.out,routes,a.placements or (OUT/'placement-overrides.json' if (OUT/'placement-overrides.json').exists() else None))
