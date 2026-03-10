# Object Processing - Project Guide

## Repository Structure

```
object_processing/
├── CLAUDE.md
├── docs/                  # GitHub Pages (served from /docs on main branch)
│   ├── index.html         # Gallery page (search, filter, thumbnail grid)
│   ├── viewer.html        # 3D viewer page (Babylon.js)
│   ├── catalog.json       # Object metadata
│   ├── js/viewer.js       # Viewer logic
│   └── objects/{name}/    # Thumbnail images (committed to git)
│       └── thumb.png
├── wiki/                  # Source files + processing scripts
│   ├── index.html         # Source gallery page (edit here, copy to docs/)
│   ├── viewer.html        # Source viewer page
│   ├── catalog.json       # Source catalog
│   ├── js/viewer.js       # Source viewer logic
│   ├── convert_objects.py
│   ├── generate_thumbnails.py
│   ├── upload_to_hf.py       # Upload GLBs to HuggingFace
│   ├── upload_obj_to_hf.py   # Upload OBJ+MTL+textures to HuggingFace
│   ├── download_meshes.py    # Download meshes from HuggingFace (OBJ or GLB)
│   └── output/            # (gitignored) GLB + thumbnail build output
├── visualization/         # MuJoCo table-top scene scripts
└── MeshProcess/           # (gitignored) local mesh processing
```

## What is stored where

| Asset | Stored in | Why |
|---|---|---|
| **GLB meshes** | HuggingFace (`willi19/object_processing`) `objects/{name}/mesh.glb` | For 3D viewer |
| **OBJ meshes** | HuggingFace (`willi19/object_processing`) `objects/{name}/raw/` | OBJ+MTL+textures, for distribution/download |
| **Thumbnails** | GitHub repo (`docs/objects/{name}/thumb.png`) | Small PNGs (~6KB each, ~600KB total), fast to serve from GitHub Pages |
| **HTML/JS/JSON** | GitHub repo (`docs/`) | Static site files served by GitHub Pages |
| **Python scripts** | GitHub repo (`wiki/`) | Source code for the processing pipeline |
| **catalog.json** | GitHub repo (`wiki/` source, `docs/` deploy copy) | Object metadata used by both gallery and viewer |

## How data flows

1. Raw OBJ meshes (local) → `convert_objects.py` → GLB files + catalog.json (`wiki/output/`)
2. Raw OBJ meshes (local) → `generate_thumbnails.py` → thumb.png (`wiki/output/`)
3. GLB files (`wiki/output/`) → `upload_to_hf.py` → HuggingFace `objects/{name}/mesh.glb`
4. Thumbnails (`wiki/output/`) → copied to `docs/objects/{name}/thumb.png` → committed to git
5. Source HTML/JS (`wiki/`) → copied to `docs/` → GitHub Pages serves the site

## Pipeline: Adding New Objects

### 1. Convert OBJ to GLB
```bash
cd wiki/
python convert_objects.py <input_dir> output
# Input: {name}/raw_mesh/{name}.obj (+.mtl +texture)
# Output: output/objects/{name}/mesh.glb + catalog.json
```

### 2. Generate Thumbnails
```bash
python generate_thumbnails.py <input_dir> output
# Requires: trimesh, pyrender, PyOpenGL>=3.1.10, Pillow
# Uses EGL for headless rendering (no display needed)
# Output: output/objects/{name}/thumb.png (256x256)
```

### 3. Upload to HuggingFace
```bash
python upload_to_hf.py output                # GLBs (for 3D viewer)
python upload_obj_to_hf.py <input_dir>       # OBJs (for distribution)
```

### 4. Deploy Website
```bash
# Copy source files to deploy directory
cp wiki/index.html wiki/viewer.html wiki/catalog.json docs/
cp wiki/js/viewer.js docs/js/

# Copy thumbnails (only needed when new objects are added)
for dir in wiki/output/objects/*/; do
  name=$(basename "$dir")
  mkdir -p "docs/objects/$name"
  [ -f "$dir/thumb.png" ] && cp "$dir/thumb.png" "docs/objects/$name/thumb.png"
done

git add docs/ && git commit && git push
# GitHub Pages auto-deploys from docs/ on main branch
```

## Key Technical Details

- **3D Viewer**: Babylon.js 7.34.3 (pinned UMD builds from jsdelivr CDN)
- **GLB loading**: URL split into rootUrl + `'mesh.glb'` so Babylon.js detects `.glb` extension
- **Camera**: ArcRotateCamera with no beta limits (full 360 vertical rotation), sensitivity set to 3000 (3x slower than default) for both rotation and panning
- **Thumbnails in gallery**: Loaded locally from `objects/{id}/thumb.png` (GitHub Pages), NOT from HuggingFace
- **GLBs in viewer**: Loaded from HuggingFace at `https://huggingface.co/datasets/willi19/object_processing/resolve/main/objects/{name}/mesh.glb`
- **Thumbnail rendering**: pyrender with EGL backend (headless), camera at distance 2.0, meshes centered and normalized to unit scale
- **Mesh source path**: `/home/mingi/shared_data/RSS2026_Mingi/object/paradex/{name}/raw_mesh/{name}.obj`

## Commit Rules
- NEVER add `Co-Authored-By` or any Claude/AI attribution to commit messages
- NEVER add Claude as a contributor anywhere (GitHub, HuggingFace, readme, etc.)

## Gitignored
- `wiki/output/` — GLB + thumbnail build output (GLBs go to HuggingFace, thumbnails copied to docs/)
- `MeshProcess/` — local mesh data
