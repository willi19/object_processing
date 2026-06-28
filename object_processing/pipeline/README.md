# `pipeline/` — mesh processing stages

Each stage is a plain function that takes explicit input/output paths, performs
one step, validates its output, and **raises on failure** (never logs-and-dies).
Compose them via [`cli.py`](../cli.py) or call them directly.

```
raw.obj → convex_decompose → manifold → simplify → basic_info → compute_symmetry → tabletop
```

| Module | Function(s) | Tool | Produces |
|--------|-------------|------|----------|
| [`convert.py`](convert.py) | `change_format`, `normalize` | trimesh | re-exported / normalized mesh |
| [`decompose.py`](decompose.py) | `convex_decompose`, `manifold` | **CoACD** | convex pieces + watertight mesh |
| [`export.py`](export.py) | `export_urdf`, `export_mjcf` | lxml | `coacd.urdf`, `coacd.xml` |
| [`simplify.py`](simplify.py) | `simplify` | **ACVD** | low-poly mesh (~2k verts) |
| [`info.py`](info.py) | `basic_info`, `complete_pc` | trimesh | OBB, center of mass, mass |
| [`symmetry.py`](symmetry.py) | `detect_symmetry`, `compute_symmetry` | trimesh + scipy | rotational symmetry (`Cn`/`Cinf`/`Dn`) |
| [`tabletop.py`](tabletop.py) | `generate_tabletop_poses` | **MuJoCo** | stable resting `SE(3)` poses |
| [`decimate.py`](decimate.py) | `decimate` | pymeshlab | lightweight textured mesh for viewing |

Run the whole chain for an object with `python src/process.py <obj>`
(see the [main README](../../readme.md#run-the-pipeline)).

## Symmetry detection

`compute_symmetry` finds the object's **proper rotational** symmetry group from
mesh geometry: the inertia tensor's principal axes are the only candidate axes,
and each is verified by rotating a surface sample and measuring the
point-to-surface residual. Reflections are ignored. Output (`info/symmetry.json`,
object frame, through the center of mass):

```json
{
  "type": "Dinf",
  "center": [x, y, z],
  "scale": 0.21,
  "axes": [{"axis": [0, 0, 1], "fold": "inf", "residual": 0.002}],
  "rel_tol": 0.01
}
```

`fold` is an integer (`Cn`, e.g. a hexagonal prism → 6) or `"inf"` (a body of
revolution — a can or bowl).

## External tools

`convex_decompose` / `manifold` (CoACD) and `simplify` (ACVD) shell out to native
binaries resolved by [`utils/tools.py`](../utils/tools.py) from `$COACD_BIN` /
`$ACVD_BIN`, else `third_party/` at the repo root. `tabletop` needs the `mujoco`
Python package; `decimate` needs `pymeshlab`.
