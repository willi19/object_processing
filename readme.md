# Object Processing

Object mesh processing pipeline and web-based 3D object browser.

## How to Add New Objects

### Step 1: Convert OBJ to GLB

```bash
cd wiki/
python convert_objects.py <input_dir> output
```

- Input: `<input_dir>/{name}/raw_mesh/{name}.obj` (+ `.mtl` + texture if available)
- Output: `output/objects/{name}/mesh.glb` and `catalog.json`

### Step 2: Generate Thumbnails

```bash
python generate_thumbnails.py <input_dir> output
```

- Requires: `trimesh`, `pyrender`, `PyOpenGL>=3.1.10`, `Pillow`
- Uses EGL for headless rendering (no display needed)
- Output: `output/objects/{name}/thumb.png` (256x256)

### Step 3: Upload to HuggingFace

```bash
python upload_to_hf.py output
```

- Uploads `output/objects/` to the HuggingFace dataset repo
- Requires: `huggingface_hub` (run `huggingface-cli login` first)

### Step 4: Deploy Website

```bash
cp wiki/index.html wiki/viewer.html wiki/catalog.json docs/
cp wiki/js/viewer.js docs/js/
git add docs/ && git commit -m "Update wiki" && git push
```

GitHub Pages serves the site from the `docs/` folder.
