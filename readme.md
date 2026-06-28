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

`object_processing/` is the importable **library** (the processing code); `src/`
holds the **runnable scripts** that drive it.

| Path | Role | Docs |
|------|------|------|
| [`object_processing/pipeline/`](object_processing/pipeline/) | mesh processing stage functions (decompose → simplify → measure → symmetry → tabletop) | [README](object_processing/pipeline/README.md) |
| [`object_processing/visualization/`](object_processing/visualization/) | headless figure / turntable / web-export functions | [README](object_processing/visualization/README.md) |
| [`object_processing/utils/`](object_processing/utils/) | data-root config, external-tool resolution, rotation math | [README](object_processing/utils/README.md) |
| [`src/run.py`](src/run.py) | pipeline CLI — `process` / `decimate` / `symmetry` | — |
| [`src/render.py`](src/render.py), [`src/webexport.py`](src/webexport.py) | figure + web-export CLIs | — |
| [`src/viewers/`](src/viewers/) | interactive desktop viewers (Viser) | [README](src/viewers/README.md) |

## How to

### Install

```bash
# Create and activate the environment (Python 3.10)
conda create -n object_processing python=3.10 -y
conda activate object_processing

# Install dependencies, then the package itself
pip install -r requirements.txt
pip install -e .            # core pipeline (editable, so AutoDex can import it)

pip install -e .[render]    # optional: + headless Open3D figures/GIFs
pip install -e .[viewers]   # optional: + the Viser desktop viewers (also needs `paradex`)
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
python src/run.py process <obj> [<obj> ...]
python src/run.py process --all --workers 8     # everything, parallel
python src/run.py process --all --skip          # skip stages already done

python src/run.py symmetry --all                # (re)detect symmetry only
python src/run.py decimate --all                # lightweight meshes for viewing
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

Three ways to inspect the processed data, by increasing setup.

**1. Interactive desktop viewers** — `src/viewers/` (Viser). Needs
`pip install -e ".[viewers]"` **and** the `paradex` package on `PYTHONPATH`. Each
opens a Viser server in your browser; the object root comes from `$OBJECT_ROOT`.

```bash
python src/viewers/object_viewer.py      # raw / coacd / simplified side by side + OBB
python src/viewers/table_top.py          # grid of all stable tabletop poses + OBB/axes
python src/viewers/tabletop_compare.py   # compare pose pairs (gravity-axis/yaw factored out)
python src/viewers/cylinder_axis.py      # rotate about a candidate axis, measure symmetry residual
```

**2. Headless figures / GIFs** — `src/render.py` (Open3D offscreen, no display).
Needs `pip install -e ".[render]"`.

```bash
python src/render.py pipeline  <obj> --out fig.png       # raw → coacd → manifold → simplified strip
python src/render.py tabletop  <obj> --out poses.png     # mesh in each stable pose on a ground plane
python src/render.py overlays  <obj> --out obb_sym.png   # mesh + OBB + symmetry axes
python src/render.py turntable <obj> --out spin.gif [--stage simplified]
```

| Tabletop poses | OBB + symmetry overlay |
|---|---|
| ![tabletop](docs/img/tabletop_french_mustard.png) | ![overlays](docs/img/overlays_blue_alarm.png) |

**3. Web gallery** — `src/webexport.py` bundles per-object assets for the static
site: stage GLBs (uploaded to HuggingFace) and small `info.json` overlays (OBB +
symmetry + tabletop poses, committed to `docs/`).

```bash
python src/webexport.py <obj> --all      # stage GLBs + info.json
```

Then serve `docs/` (see [Deploy the gallery website](#deploy-the-gallery-website)).
Live gallery: https://willi19.github.io/object_processing/

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
