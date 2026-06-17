#!/usr/bin/env python
"""Author-time bake: scene_template's ClearSkyEnvironment 5 geo params are the SOLE
hand-edited source of truth for the sun; this regenerates every derived value
(sky-level geo override + light rig rotations + sky-material inputs), statically.
No runtime solver. Run with --dry-run to compute+compare without writing.

Usage: python bake_clearsky_sun.py [scene_template.usda] [--dry-run]
"""
import sys, math, datetime
from pxr import Sdf

args = [a for a in sys.argv[1:] if not a.startswith("--")]
SCENE = args[0] if args else r"D:\RnD\KB_STATIC_ASSETS\slot_template\scene_template.usda"
DRY = "--dry-run" in sys.argv

ENV = "/World/EnvironmentVariants/ClearSkyEnvironment/Environment"
SKY = ENV + "/sky"
N   = SKY + "/AxisNorth"
SH  = SKY + "/Looks/SkyMaterial/Shader"

def day_of_year(date_str):
    return datetime.date.fromisoformat(str(date_str)).timetuple().tm_yday

def solar(lat, lon, day, time_h):
    g = math.radians((360.0/365.0)*(day-1))
    decl = math.degrees(0.006918 - 0.399912*math.cos(g) + 0.070257*math.sin(g)
        - 0.006758*math.cos(2*g) + 0.000907*math.sin(2*g)
        - 0.002697*math.cos(3*g) + 0.00148*math.sin(3*g))
    eot = 229.18*(0.000075 + 0.001868*math.cos(g) - 0.032077*math.sin(g)
        - 0.014615*math.cos(2*g) - 0.040849*math.sin(2*g))
    H = (time_h + eot/60.0 - 12.0)*15.0
    dr, lr, Hr = map(math.radians, [decl, lat, H])
    elev = math.degrees(math.asin(math.sin(lr)*math.sin(dr) + math.cos(lr)*math.cos(dr)*math.cos(Hr)))
    er = math.radians(elev)
    cosA = (math.sin(dr) - math.sin(er)*math.sin(lr)) / (math.cos(er)*math.cos(lr))
    az = math.degrees(math.acos(max(-1.0, min(1.0, cosA))))
    return dict(Declination=decl, SHA=H, Elevation=elev, Azimuth=az)

layer = Sdf.Layer.FindOrOpen(SCENE)
if layer is None:
    print("FATAL: cannot open", SCENE); sys.exit(1)

def get(path):
    a = layer.GetAttributeAtPath(path)
    return a.default if a is not None else None

date_str = get(ENV + ".date")
lat   = float(get(ENV + ".location:latitude"))
lon   = float(get(ENV + ".location:longitude"))
north = float(get(ENV + ".location:north_orientation"))
time_h= float(get(ENV + ".time:current"))
day   = day_of_year(date_str)
s = solar(lat, lon, day, time_h)
print(f"SOURCE  date={date_str} (day {day})  lat={lat}  lon={lon}  time={time_h}  north={north}")
print(f"DERIVED Decl={s['Declination']:.5f}  SHA={s['SHA']:.5f}  Elev={s['Elevation']:.5f}  Az={s['Azimuth']:.5f}")

D3 = Sdf.ValueTypeNames.Double3
D  = Sdf.ValueTypeNames.Double
F  = Sdf.ValueTypeNames.Float
B  = Sdf.ValueTypeNames.Bool
derived = [
    (SKY + ".DayOfYear", D, float(day)), (SKY + ".Latitude", D, lat),
    (SKY + ".Longitude", D, lon), (SKY + ".NorthOrientation", D, north),
    (SKY + ".TimeOfDay", D, time_h),
    (N + ".xformOp:rotateZYX", D3, (0.0, north + 180.0, 0.0)),
    (N + "/AxisLatitude.xformOp:rotateZYX", D3, (0.0, 0.0, lat)),
    (N + "/AxisLatitude/AxisSHA.xformOp:rotateZYX", D3, (180.0 - s["SHA"], 0.0, 0.0)),
    (N + "/AxisLatitude/AxisSHA/AxisDeclination.xformOp:rotateZYX", D3, (0.0, 0.0, s["Declination"])),
    (N + "/AxisAzimuth.xformOp:rotateZYX", D3, (0.0, s["Azimuth"], 0.0)),
    (N + "/AxisAzimuth/AxisElevation.xformOp:rotateZYX", D3, (0.0, 0.0, s["Elevation"])),
    (SH + ".inputs:Azimuth", F, s["Azimuth"]), (SH + ".inputs:Elevation", F, s["Elevation"]),
    (SH + ".inputs:Declination", F, s["Declination"]), (SH + ".inputs:SHA", F, s["SHA"]),
    (SH + ".inputs:Latitude", F, lat), (SH + ".inputs:Longitude", F, lon),
    (SH + ".inputs:DayOfYear", F, float(day)), (SH + ".inputs:TimeOfDay", F, time_h),
    (SH + ".inputs:NorthOrientation", F, north),
    (SH + ".inputs:SunPositionFromTOD", B, False), (SH + ".inputs:TimeOfDaySpeed", F, 0.0),
]

def fmt(v):
    if isinstance(v, (tuple, list)): return "(" + ", ".join(f"{x:.5f}" for x in v) + ")"
    if isinstance(v, float): return f"{v:.5f}"
    return str(v)

print("\nCOMPARE  attr : current -> baked")
for path, _t, val in derived:
    cur = get(path)
    name = path.split("/")[-1]
    print(f"  {name:34s} {fmt(cur) if cur is not None else 'NEW':>22s} -> {fmt(val)}")

if DRY:
    print("\n--dry-run: nothing written"); sys.exit(0)

def ensure(path, type_name, value):
    a = layer.GetAttributeAtPath(path)
    if a is None:
        prim_path, _, attr_name = path.rpartition(".")
        prim = layer.GetPrimAtPath(prim_path)
        if prim is None:
            prim = Sdf.CreatePrimInLayer(layer, prim_path)
            prim.specifier = Sdf.SpecifierOver
        a = Sdf.AttributeSpec(prim, attr_name, type_name)
    a.default = value

for path, t, val in derived:
    ensure(path, t, val)
layer.Save()
print("\nWROTE", SCENE)
