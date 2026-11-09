"""Bounded fixed templates using the OpenCascade kernel installed with CadQuery."""
import json
import resource
import sys
import uuid
from pathlib import Path

resource.setrlimit(resource.RLIMIT_CPU, (35, 35))
resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.GProp import GProp_GProps
from OCP.Bnd import Bnd_Box
from OCP.gp import gp_Pnt, gp_Ax2, gp_Dir
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.STEPControl import STEPControl_Writer, STEPControl_Reader, STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone
from OCP.StlAPI import StlAPI_Writer

root = Path(__file__).resolve().parent
ident = str(uuid.UUID(sys.argv[1]))
directory = root / 'data/products' / ident
spec = json.loads((directory / 'spec.json').read_text())
w, d, h, t, hole = [spec[key] for key in ('width_mm', 'depth_mm', 'height_mm', 'wall_mm', 'hole_mm')]

def box(x, y, z, a, b, c): return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), a, b, c).Shape()

base = box(-w/2, -d/2, 0, w, d, t)
if spec['template'] == 'enclosure':
    model = BRepAlgoAPI_Cut(box(-w/2, -d/2, 0, w, d, h), box(-w/2+t, -d/2+t, t, w-2*t, d-2*t, h)).Shape()
elif spec['template'] == 'bracket':
    model = BRepAlgoAPI_Fuse(base, box(-w/2, -d/2, 0, w, t, h)).Shape()
else: model = base

holes = []
if hole and spec['template'] != 'enclosure':
    for x in [-w/2 + 2*hole, w/2 - 2*hole]:
        for y in [-d/2 + 2*hole, d/2 - 2*hole]:
            cutter = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, 0), gp_Dir(0, 0, 1)), hole/2, t+1).Shape()
            model = BRepAlgoAPI_Cut(model, cutter).Shape()
            holes.append((x, y))

solids = TopExp_Explorer(model, TopAbs_SOLID)
count = 0
while solids.More(): count += 1; solids.Next()
volume = GProp_GProps(); BRepGProp.VolumeProperties_s(model, volume)
area = GProp_GProps(); BRepGProp.SurfaceProperties_s(model, area)
if not BRepCheck_Analyzer(model).IsValid() or count != 1 or volume.Mass() <= 0: raise ValueError('Invalid CAD solid')

writer = STEPControl_Writer()
if writer.Transfer(model, STEPControl_AsIs) != IFSelect_RetDone: raise ValueError('STEP transfer failed')
if writer.Write(str(directory / 'model.step')) != IFSelect_RetDone: raise ValueError('STEP export failed')
BRepMesh_IncrementalMesh(model, .08, False, .15, False).Perform()
if not StlAPI_Writer().Write(model, str(directory / 'model.stl')): raise ValueError('STL export failed')
reader = STEPControl_Reader()
if reader.ReadFile(str(directory / 'model.step')) != IFSelect_RetDone: raise ValueError('STEP import failed')
reader.TransferRoots(); reloaded = reader.OneShape()
roundtrip = GProp_GProps(); BRepGProp.VolumeProperties_s(reloaded, roundtrip)
if not BRepCheck_Analyzer(reloaded).IsValid() or abs(roundtrip.Mass()-volume.Mass()) > max(.001, volume.Mass()*1e-6): raise ValueError('STEP roundtrip failed')

# DXF bottom-face outline with explicit millimetre insertion units.
dxf = ['0', 'SECTION', '2', 'HEADER', '9', '$ACADVER', '1', 'AC1015', '9', '$INSUNITS', '70', '4', '9', '$MEASUREMENT', '70', '1', '0', 'ENDSEC', '0', 'SECTION', '2', 'ENTITIES']
corners = [(-w/2, -d/2), (w/2, -d/2), (w/2, d/2), (-w/2, d/2)]
for i, (x, y) in enumerate(corners):
    endx, endy = corners[(i+1) % 4]
    dxf += ['0', 'LINE', '8', '0', '10', str(x), '20', str(y), '30', '0', '11', str(endx), '21', str(endy), '31', '0']
for x, y in holes: dxf += ['0', 'CIRCLE', '8', '0', '10', str(x), '20', str(y), '30', '0', '40', str(hole/2)]
dxf += ['0', 'ENDSEC', '0', 'EOF']
(directory / 'profile.dxf').write_text('\n'.join(dxf)+'\n')
bounds = Bnd_Box(); BRepBndLib.AddOptimal_s(model, bounds, False, False)
xmin, ymin, zmin, xmax, ymax, zmax = bounds.Get()
geometry = {'valid_solid': True, 'solid_count': count, 'volume_mm3': round(volume.Mass(), 5),
            'surface_area_mm2': round(area.Mass(), 5), 'bounds_mm': {'x': round(xmax-xmin, 6), 'y': round(ymax-ymin, 6), 'z': round(zmax-zmin, 6)},
            'effective_thickness_mm': t if spec['template'] == 'plate' else None,
            'step_roundtrip_valid': True, 'engine': 'OpenCascade via CadQuery OCP dependency',
            'profile_scope': 'Bottom-face footprint in mm; DXF is not a fully dimensioned fabrication drawing.'}
(directory / 'geometry.json').write_text(json.dumps(geometry))
