# Object Processing - Project Guide

## Repository Structure

```
object_processing/
├── CLAUDE.md
├── docs/                  # GitHub Pages (served from /docs)
│   ├── index.html         # Gallery page (search, filter, thumbnail grid)
│   ├── viewer.html        # 3D viewer page (Babylon.js)
│   ├── catalog.json       # Object metadata
│   └── js/viewer.js       # Viewer logic
├── wiki/                  # Source + scripts (docs/ is a deploy copy)
│   ├── index.html
│   ├── viewer.html
│   ├── catalog.json
│   ├── js/viewer.js
│   ├── convert_objects.py
│   ├── generate_thumbnails.py
│   ├── upload_to_hf.py
│   └── output/            # (gitignored) GLB + thumbnail output
├── visualization/         # MuJoCo table-top scene scripts
└── MeshProcess/           # (gitignored) local mesh processing
```

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
python upload_to_hf.py output
# Uploads output/objects/ to willi19/object_processing dataset repo
```

### 4. Deploy Website
```bash
# Copy updated wiki files to docs/
cp wiki/index.html wiki/viewer.html wiki/catalog.json docs/
cp wiki/js/viewer.js docs/js/
git add docs/ && git commit && git push
# GitHub Pages serves from docs/ on main branch
```

## Key Technical Details

- **GLB loading**: Viewer fetches GLB as blob first, then passes blob URL to Babylon.js (workaround for HuggingFace redirect issues)
- **Thumbnails**: Rendered via pyrender with EGL backend (headless). Camera at distance 2.0, slightly above center
- **HuggingFace URL pattern**: `https://huggingface.co/datasets/willi19/object_processing/resolve/main/objects/{name}/mesh.glb`
- **Mesh source path**: `/home/mingi/shared_data/RSS2026_Mingi/object/paradex/{name}/raw_mesh/{name}.obj`

## Gitignored
- `wiki/output/` — GLB + thumbnail build output (hosted on HuggingFace)
- `MeshProcess/` — local mesh data
