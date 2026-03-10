# docs/ — GitHub Pages Deploy Directory

## Overview
This is the static website served by GitHub Pages from the `docs/` folder on `main` branch.
Files here are copies from `wiki/` — edit source in `wiki/`, then copy here to deploy.

## Structure
```
docs/
├── index.html          # Gallery page (copy of wiki/index.html)
├── viewer.html         # 3D viewer page (copy of wiki/viewer.html)
├── catalog.json        # Object metadata (copy of wiki/catalog.json)
├── js/
│   └── viewer.js       # Viewer logic (copy of wiki/js/viewer.js)
└── objects/
    └── {name}/
        └── thumb.png   # Thumbnails — committed to git, served locally
```

## What loads from where
- **Thumbnails** (gallery page): Loaded locally from `objects/{id}/thumb.png` — fast, served by GitHub Pages
- **GLB meshes** (viewer page): Loaded from HuggingFace (`https://huggingface.co/datasets/willi19/object_processing/resolve/main/`)
- **Babylon.js**: Loaded from jsdelivr CDN (pinned v7.34.3)
- **catalog.json**: Loaded locally from this directory

## Deployment
After making changes in `wiki/`, copy the updated files here:
```bash
cp wiki/index.html wiki/viewer.html wiki/catalog.json docs/
cp wiki/js/viewer.js docs/js/

# Copy thumbnails (only needed when new objects are added)
for dir in wiki/output/objects/*/; do
  name=$(basename "$dir")
  mkdir -p "docs/objects/$name"
  [ -f "$dir/thumb.png" ] && cp "$dir/thumb.png" "docs/objects/$name/thumb.png"
done
```
Then commit and push. GitHub Pages will auto-deploy.

## Key Design Decisions
- Static files only — no build step, no bundler, no framework
- Babylon.js 7.34.3 loaded from CDN (pinned version, no local copy)
- GLB meshes hosted on HuggingFace (large files, not in this repo)
- Thumbnails committed to git and served locally (small files, ~6KB each, much faster than HuggingFace)
- GLB loading uses rootUrl + `'mesh.glb'` split so Babylon.js detects the `.glb` extension
- Camera: 3x slower rotation and panning (sensibility 3000), no beta limits for full 360 vertical rotation
