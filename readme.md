# Object Processing

Mesh and object data-preparation pipeline for the AutoDex project, with a
web-based 3D browser for the results.

Give it a raw textured `.obj` and it produces everything downstream needs:
a convex collision decomposition, watertight and simplified meshes, URDF/MJCF,
bounding box and mass properties, rotational symmetry, and stable tabletop poses.

**Gallery:** https://willi19.github.io/object_processing/

## Pipeline

A raw mesh is decomposed, simplified, and measured. Every stage takes explicit
input/output paths and raises on failure — nothing is silently swallowed.

![pipeline stages](docs/img/pipeline_french_mustard.png)

| # | Stage | Tool | Produces |
|---|-------|------|----------|
| 1 | `change_format` | trimesh | `mesh/raw.obj` |
| 2 | `convex_decompose` | CoACD | `mesh/coacd.obj`, `urdf/meshes/*.obj` |
| 3 | `export_urdf` / `export_mjcf` | lxml | `urdf/coacd.urdf`, `urdf/coacd.xml` |
| 4 | `manifold` | CoACD | `mesh/manifold.obj` (watertight) |
| 5 | `simplify` | ACVD | `mesh/simplified.obj` (~2k verts) |
| 6 | `basic_info` | trimesh | `info/simplified.json` (OBB, mass, center) |
| 7 | `compute_symmetry` | trimesh + scipy | `info/symmetry.json` |
| 8 | `generate_tabletop_poses` | MuJoCo | `info/tabletop/*.npy` |

Inputs live at `{OBJECT_ROOT}/{obj}/raw_mesh/`; outputs land under
`{OBJECT_ROOT}/{obj}/processed_data/`.

## Code layout

The package is split by role — each part has its own README:

| Module | Role | Docs |
|--------|------|------|
| [`pipeline/`](object_processing/pipeline/) | mesh processing stages (decompose → simplify → measure → symmetry → tabletop) | [README](object_processing/pipeline/README.md) |
| [`visualization/`](object_processing/visualization/) | headless figures, turntables, web export (GLB + `info.json`) | [README](object_processing/visualization/README.md) |
| [`viewers/`](object_processing/viewers/) | interactive desktop viewers (Viser) | [README](object_processing/viewers/README.md) |
| [`utils/`](object_processing/utils/) | data-root config, external-tool resolution, rotation math | [README](object_processing/utils/README.md) |

## How to

### Install

```bash
pip install -e .            # core pipeline
pip install -e .[render]    # + headless Open3D figures/GIFs
pip install -e .[viewers]   # + the Viser desktop viewers
```

CoACD and ACVD are native binaries, resolved from `$COACD_BIN` / `$ACVD_BIN`,
otherwise `third_party/` at the repo root (not vendored — provisioned separately).

### Where the data lives

Every command resolves the per-object root from the `OBJECT_ROOT` environment
variable (default `~/shared_data/AutoDex/object/paradex`). Point it at your own
copy so a dataset shared with other tools is never written to:

```bash
export OBJECT_ROOT=~/object_data/paradex
```

### Run the pipeline

```bash
python -m object_processing process <obj> [<obj> ...]
python -m object_processing process --all --workers 8     # everything, parallel
python -m object_processing process --all --skip          # skip stages already done

python -m object_processing symmetry --all                # (re)detect symmetry only
python -m object_processing decimate --all                # lightweight meshes for viewing
```

### Download meshes (no dependencies)

```bash
cd wiki/
python download_meshes.py --list                 # list all available objects
python download_meshes.py --all                   # all OBJ meshes (+ MTL + textures)
python download_meshes.py apple banana baseball   # specific objects
python download_meshes.py --all --format glb      # GLB instead of OBJ
```

Files are saved to `downloaded_meshes/{name}/` (override with `--output`).

### Visualize

```bash
python -m object_processing.visualization.render pipeline <obj> --out fig.png
python -m object_processing.visualization.render tabletop <obj> --out poses.png
python -m object_processing.visualization.render overlays <obj> --out obb_sym.png
```

| Tabletop poses | OBB + symmetry overlay |
|---|---|
| ![tabletop](docs/img/tabletop_french_mustard.png) | ![overlays](docs/img/overlays_blue_alarm.png) |

### Deploy the gallery website

The gallery is served from `docs/` on `main`. To add or refresh objects:

```bash
cd wiki/
python convert_objects.py <input_dir> output      # OBJ -> GLB + catalog.json
python generate_thumbnails.py <input_dir> output   # 256x256 thumbnails
python upload_to_hf.py output                       # GLBs -> HuggingFace
python upload_obj_to_hf.py <input_dir>              # original OBJs -> HuggingFace

# copy the static site + new thumbnails into docs/, then commit & push
cp wiki/index.html wiki/viewer.html wiki/catalog.json docs/
cp wiki/js/viewer.js docs/js/
for dir in wiki/output/objects/*/; do
  name=$(basename "$dir")
  mkdir -p "docs/objects/$name"
  [ -f "$dir/thumb.png" ] && cp "$dir/thumb.png" "docs/objects/$name/thumb.png"
done
git add docs/ && git commit -m "Update gallery" && git push
```

GitHub Pages auto-deploys from `docs/` on `main`.
