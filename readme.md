# Object Processing

Mesh and object data-preparation pipeline for the AutoDex project, plus a
web-based 3D object browser.

The `object_processing` Python package turns a raw textured `.obj` per object
into everything downstream tasks need: a convex collision decomposition,
watertight & simplified meshes, URDF/MJCF, oriented bounding box + mass
properties, rotational symmetry, and stable tabletop poses. A browsable gallery
of the processed objects is served at
**https://willi19.github.io/object_processing/**.

## The process pipeline

Each object is processed from `{OBJECT_ROOT}/{obj}/raw_mesh/{obj}.obj` into
`{OBJECT_ROOT}/{obj}/processed_data/`. Stages run in dependency order; each one
validates its output and raises on failure (failures are never swallowed).

```
raw_mesh/{obj}.obj
   │
 1 change_format ───────────────► mesh/raw.obj            re-export, keep material
   │
 2 convex_decompose  (CoACD) ────► mesh/coacd.obj
   │                               urdf/meshes/*.obj      convex collision pieces
 3 export_urdf ─────────────────► urdf/coacd.urdf
 4 export_mjcf ─────────────────► urdf/coacd.xml
   │
 5 manifold          (CoACD) ────► mesh/manifold.obj      watertight
   │
 6 simplify          (ACVD) ─────► mesh/simplified.ply    ~2000 vertices
 7 change_format ───────────────► mesh/simplified.obj
   │
 8 basic_info ───────────────────► info/simplified.json   OBB, center of mass, mass
 9 compute_symmetry ─────────────► info/symmetry.json     rotational symmetry group
10 generate_tabletop_poses (MuJoCo) ► info/tabletop/*.npy stable resting SE(3) poses
```

| Stage | Tool | Output |
|---|---|---|
| `change_format` | trimesh | re-exported mesh in the target format |
| `convex_decompose` | **CoACD** | convex pieces for collision (`urdf/meshes/`) |
| `export_urdf` / `export_mjcf` | lxml | `coacd.urdf` / `coacd.xml` |
| `manifold` | **CoACD** | watertight mesh |
| `simplify` | **ACVD** | low-poly surface mesh |
| `basic_info` | trimesh | oriented bounding box, center of mass, mass |
| `compute_symmetry` | trimesh / scipy | `Cn` / `Cinf` / `Dn` rotational symmetry axes |
| `generate_tabletop_poses` | **MuJoCo** | stable poses found by physics settling |

### Output layout

```
{OBJECT_ROOT}/{obj}/
├── raw_mesh/{obj}.obj                              # input (+ .mtl + textures)
└── processed_data/
    ├── mesh/{raw,coacd,manifold,simplified}.obj
    ├── urdf/{coacd.urdf, coacd.xml, meshes/}
    └── info/
        ├── simplified.json                         # OBB, COM, mass
        ├── symmetry.json                           # rotational symmetry
        └── tabletop/*.npy                          # stable SE(3) poses
```

### Usage

```bash
# Full pipeline
python -m object_processing process <obj> [<obj> ...]
python -m object_processing process --all --workers 8     # everything, parallel
python -m object_processing process --all --skip          # skip stages already done

# Individual passes
python -m object_processing symmetry --all                # (re)detect symmetry only
python -m object_processing decimate --all                # lightweight meshes for the viewer
```

The per-object root is resolved from the `OBJECT_ROOT` environment variable
(falling back to `~/shared_data/AutoDex/object/paradex`).

### Symmetry detection

`compute_symmetry` finds the object's **proper rotational** symmetry group from
mesh geometry: the inertia tensor's principal axes are the only candidate axes,
and each is verified by rotating a surface sample and measuring the point-to-
surface residual. Results (`info/symmetry.json`) are reported in the object frame
through the center of mass:

```json
{
  "type": "Dinf",
  "center": [x, y, z],
  "scale": 0.21,
  "axes": [{"axis": [0, 0, 1], "fold": "inf", "residual": 0.002}],
  "rel_tol": 0.01
}
```

`fold` is an integer (`Cn`, e.g. a hexagonal prism → 6) or `"inf"` (body of
revolution, e.g. a can or bowl). Reflections are intentionally ignored.

### Installation

```bash
pip install -e .            # core pipeline
pip install -e .[viewers]   # + the Viser-based visualization scripts
```

The native tools **CoACD** and **ACVD** are resolved from `$COACD_BIN` /
`$ACVD_BIN`, otherwise from `third_party/` at the repo root (not vendored —
provisioned separately).

## Download meshes

Download object meshes from HuggingFace (no dependencies — Python standard
library only):

```bash
cd wiki/

python download_meshes.py --list                 # list all available objects
python download_meshes.py --all                   # all OBJ meshes (with MTL + textures)
python download_meshes.py apple banana baseball   # specific objects
python download_meshes.py --all --format glb      # GLB format instead
python download_meshes.py --output ./my_meshes --all
```

Files are saved to `downloaded_meshes/` by default (use `--output` to change):

```
downloaded_meshes/
├── apple/
│   └── apple.obj
├── baseball/
│   ├── baseball.obj
│   ├── material.mtl
│   └── material_0.png
...
```

## Adding objects to the gallery website

The gallery at https://willi19.github.io/object_processing/ is served from
`docs/` on `main`. To add new objects to it:

### Step 1: Convert OBJ to GLB

```bash
cd wiki/
python convert_objects.py <input_dir> output
```

- Input: `<input_dir>/{name}/raw_mesh/{name}.obj` (+ `.mtl` + texture if available)
- Output: `output/objects/{name}/mesh.glb` and `catalog.json`

### Step 2: Generate thumbnails

```bash
python generate_thumbnails.py <input_dir> output
```

- Requires: `trimesh`, `pyrender`, `PyOpenGL>=3.1.10`, `Pillow`
- Uses EGL for headless rendering (no display needed)
- Output: `output/objects/{name}/thumb.png` (256x256)

### Step 3: Upload to HuggingFace

```bash
python upload_to_hf.py output            # GLB files (for the 3D viewer)
python upload_obj_to_hf.py <input_dir>   # original OBJ files (for distribution)
```

- Requires: `huggingface_hub` (run `huggingface-cli login` first)

### Step 4: Deploy website

```bash
# Copy source files to deploy directory
cp wiki/index.html wiki/viewer.html wiki/catalog.json docs/
cp wiki/js/viewer.js docs/js/

# Copy thumbnails
for dir in wiki/output/objects/*/; do
  name=$(basename "$dir")
  mkdir -p "docs/objects/$name"
  [ -f "$dir/thumb.png" ] && cp "$dir/thumb.png" "docs/objects/$name/thumb.png"
done

git add docs/ && git commit -m "Update wiki" && git push
```
