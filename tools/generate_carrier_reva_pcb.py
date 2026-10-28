#!/usr/bin/env python3
"""Four-layer Rev A candidate, with reproducible reviewed outer-layer copper."""
import argparse,hashlib,json,uuid,tempfile
from pathlib import Path
import pcbnew as k
from generate_carrier_reva import uid
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'hardware/carrier';OUT=ROOT/'hardware/carrier-reva'
vec=lambda x,y:k.VECTOR2I(round(x*1e6),round(y*1e6))
def stable(o,key):o.SetUuid(k.KIID(uid(key)))
def generate(out,routes=None):
 out.mkdir(parents=True,exist_ok=True)
 extra=json.loads(routes.read_text()) if routes else None
 source=(BASE/'carrier.kicad_pcb').read_text()
 if extra:
  from kicad_text import remove_nodes
  assert extra['baseline_sha256']==hashlib.sha256((BASE/'carrier.kicad_pcb').read_bytes()).hexdigest()
  source=remove_nodes(source,lambda head,node,depth: head in ('segment','via') and any('(net "/'+n+'")' in node for n in extra['replace_nets']))
 with tempfile.NamedTemporaryFile(suffix='.kicad_pcb',mode='w') as tmp:
  tmp.write(source);tmp.flush();b=k.LoadBoard(tmp.name)
 b.SetCopperLayerCount(4)
 c=json.loads((OUT/'connections.json').read_text());parts={p['ref']:p for p in c['parts']}
 for f in b.GetFootprints():f.SetPath(k.KIID_PATH('/'+uid('root')+'/'+uid(f.GetReference())))
 for ref,pos,angle in [('J6',(60,215),90),('J7',(164,100),0)]:
  p=parts[ref];lib,name=p['footprint'].split(':');f=k.FootprintLoad('/usr/share/kicad/footprints/'+lib+'.pretty',name)
  assert f is not None,p['footprint']
  f.SetFPID(k.LIB_ID(lib,name));f.SetReference(ref);f.SetValue(p['value']);f.SetPosition(vec(*pos));f.SetOrientationDegrees(angle)
  f.SetPath(k.KIID_PATH('/'+uid('root')+'/'+uid(ref)));stable(f,ref)
  nets={str(n):net for n,_,_,net in p['pins']}
  for i,pad in enumerate(f.Pads()):
   stable(pad,ref+'/pad/'+str(i));number=pad.GetNumber()
   if not number:continue
   name='/'+nets[number] if nets[number] else f'unconnected-({ref}-Pad{number})'
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
   drawing.SetText('A=odd, B=even; 59/60 NC / mating orientation pending');drawing.SetPosition(vec(100,225))
 label=k.PCB_TEXT(b);label.SetText('J7: 1 GND / 2 RAW / 3 VSYS');label.SetPosition(vec(161,110));label.SetLayer(k.Dwgs_User);label.SetTextSize(vec(.8,.8));stable(label,'reserve-label');b.Add(label)
 # Existing hold must cover the added layers too. No hidden ground under an
 # unapproved socket footprint. Keep prior outer ground and approved copper.
 for z in b.Zones():
  if z.GetIsRuleArea():z.SetLayerSet(k.LSET.AllCuMask(4))
 for layer in [k.In1_Cu,k.In2_Cu]:
  z=k.ZONE(b);z.SetLayer(layer);z.SetNet(b.FindNet('/GND'));z.SetZoneName('Rev A continuous GND '+b.GetLayerName(layer))
  z.SetLocalClearance(k.FromMM(.25));z.SetPadConnection(k.ZONE_CONNECTION_FULL)
  o=z.Outline();o.NewOutline()
  for x,y in [(21,21),(179,21),(179,229),(21,229)]:o.Append(k.FromMM(x),k.FromMM(y))
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
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "FR4 7628") (epsilon_r 4.4) (loss_tangent 0.02))
\t\t\t(layer "In1.Cu" (type "copper") (thickness 0.0152))
\t\t\t(layer "dielectric 2" (type "core") (thickness 1.065) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
\t\t\t(layer "In2.Cu" (type "copper") (thickness 0.0152))
\t\t\t(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "FR4 7628") (epsilon_r 4.4) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t)
'''
 s=s.replace('(setup','(setup'+stack,1);path.write_text(s);check=k.LoadBoard(str(path));assert check.GetCopperLayerCount()==4
 report=dict(schema=1,fabrication_ready=False,baseline_sha256=hashlib.sha256((BASE/'carrier.kicad_pcb').read_bytes()).hexdigest(),board_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),layers=['F.Cu','In1.Cu','In2.Cu','B.Cu'],ground_layers=['In1.Cu','In2.Cu'],stackup_target='JLC04161H-7628',stackup_supplier_confirmed=False,board_size_mm=[160,210],all_schematic_refs_placed=True,host={'ref':'J6','at_mm':[60,215],'angle':90},reserve={'ref':'J7','at_mm':[164,100]},sd_hold=True,routed_additions=bool(routes),hardware_executed=False)
 (out/'pcb-review.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Rev A 4-layer candidate:',len(list(b.GetFootprints())),'footprints; SD hold retained')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=OUT);p.add_argument('--routes',type=Path);p.add_argument('--base-only',action='store_true');a=p.parse_args();routes=None if a.base_only else (a.routes or (OUT/'routes.json' if (OUT/'routes.json').exists() else None));generate(a.out,routes)
