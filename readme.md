# Object Processing

Object mesh processing pipeline and web-based 3D object browser.

## Download Meshes

Download object meshes from HuggingFace:

```bash
cd wiki/

# List all available objects
python download_meshes.py --list

# Download all OBJ meshes (with MTL + textures)
python download_meshes.py --all

# Download specific objects
python download_meshes.py apple banana baseball

# Download GLB format instead
python download_meshes.py --all --format glb

# Custom output directory
python download_meshes.py --output ./my_meshes --all
```

No dependencies required — uses only Python standard library.

## How to Add New Objects

Anyone joining the project can follow the 4-step pipeline to add new objects:

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
# Upload GLB files (for the 3D viewer)
python upload_to_hf.py output

# Upload original OBJ files (for distribution)
python upload_obj_to_hf.py <input_dir>
```

- Requires: `huggingface_hub` (run `huggingface-cli login` first)

### Step 4: Deploy Website

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

GitHub Pages serves the site from the `docs/` folder.
