"""Run with FreeCADCmd tools/generate_efs58_coupon_cad.py (from repo root).

Independent experimental fixture, not a replica of the EFS housing.
All STL parts are translated to the print bed; STEP preserves assembly datums.
"""
import json
import hashlib
from pathlib import Path
import FreeCAD as A
import Part
import MeshPart

ROOT = Path.cwd()
OUT = ROOT / 'hardware/efs58-coupon'
p = json.loads((OUT / 'parameters.json').read_text())
V = A.Vector
report = {}
doc = A.newDocument('EFS58ContactCoupon')

def cylinder(d, z, h, x, y):
    return Part.makeCylinder(d/2, h, V(x, y, z))

def export(name, shape):
    assert shape.isValid() and len(shape.Solids) == 1, name
    obj = doc.addObject('PartDesign::Feature', name)
    obj.Shape = shape
    shape.exportStep(str(OUT / (name + '.step')))
    printable = shape.copy()
    printable.translate(V(0, 0, -shape.BoundBox.ZMin))
    mesh = MeshPart.meshFromShape(Shape=printable, LinearDeflection=0.025,
                                  AngularDeflection=0.15, Relative=False)
    assert mesh.isSolid(), name
    mesh.write(str(OUT / (name + '.stl')))
    report[name] = {'valid_solid': True, 'watertight_mesh': True,
                    'volume_mm3': round(shape.Volume, 6),
                    'triangles': mesh.CountFacets,
                    'bounds_mm': [round(v, 4) for v in
                                  (shape.BoundBox.XLength, shape.BoundBox.YLength,
                                   shape.BoundBox.ZLength)]}
    return obj

w, h = p['housing_size']
front = Part.makeBox(w, h, p['front_thickness'], V(-w/2, -h/2, 0))
for x, y in p['centres']:
    front = front.cut(cylinder(p['entry_diameter'], -0.1, 1.2, x, y))
    # Front funnel; no claim this gives the flat blade a qualified contact fit.
    front = front.cut(Part.makeCone(0.8, 0.6, 0.3, V(x, y, 0)))
for x, y in p['mounts']:
    front = front.cut(cylinder(p['screw_clearance'], -0.1, 1.2, x, y))
# One clipped corner indexes front/body/PCB even after turning the fixture over.
key = Part.makeBox(2, 2, 10, V(-w/2, -h/2, -1))
front = front.cut(key)
export('front', front)
for clearance in p['diametral_clearance_variants']:
    z = p['front_thickness']
    body = Part.makeBox(w, h, p['body_back_z']-z, V(-w/2, -h/2, z))
    for x, y in p['centres']:
        body = body.cut(cylinder(p['contact']['flange_diameter']+clearance,
                                  z-0.01, p['flange_pocket_depth']+0.01, x, y))
        body = body.cut(cylinder(p['contact']['body_diameter']+clearance,
                                  z-0.01, 6, x, y))
    for x, y in p['mounts']:
        body = body.fuse(cylinder(4.5, p['body_back_z'],
                                  p['pcb_front_z']-p['body_back_z'], x, y))
        body = body.cut(cylinder(p['screw_clearance'], z-0.1, 6, x, y))
    body = body.cut(key).removeSplitter()
    export('body_c%02d' % round(clearance*100), body)

# Assembly illustration: conservative outside envelopes, not internal spring CAD.
assembly = [front, doc.getObject('body_c25').Shape]
c = p['contact']
for x, y in p['centres']:
    contact = cylinder(c['body_diameter'], 1, c['body_length'], x, y)
    contact = contact.fuse(cylinder(c['flange_diameter'], 1, c['flange_height'], x, y))
    contact = contact.fuse(cylinder(c['tail_diameter'], 1+c['body_length'], c['tail_length'], x, y))
    assert front.common(contact).Volume < 1e-7
    assert doc.getObject('body_c25').Shape.common(contact).Volume < 1e-7
    assembly.append(contact)
ox, oy = p['pcb_origin']
pcb = Part.makeBox(*p['pcb_size'], p['pcb_thickness'], V(-ox, -oy, p['pcb_front_z']))
for x, y in p['centres']:
    pcb = pcb.cut(cylinder(p['contact_drill'], 5.8, 2, x, y))
for x, y in p['mounts']:
    pcb = pcb.cut(cylinder(p['screw_clearance'], 5.8, 2, x, y))
assembly.append(pcb)
Part.makeCompound(assembly).exportStep(str(OUT / 'assembly.step'))
for path in OUT.glob('*.step'):
    path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
(OUT / 'cad-checks.json').write_text(json.dumps(report, indent=2)+'\n')
(OUT / 'cad-inputs.json').write_text(json.dumps({str(path.relative_to(ROOT)):
    hashlib.sha256(path.read_bytes()).hexdigest() for path in
    [OUT/'parameters.json', ROOT/'tools/generate_efs58_coupon_cad.py']}, indent=2)+'\n')
print('Validated 4 printable solids, watertight meshes and nominal contact clearance')
A.closeDocument(doc.Name)
