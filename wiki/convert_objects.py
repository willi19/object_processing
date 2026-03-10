#!/usr/bin/env python3
"""
OBJ → GLB conversion + catalog.json generation.

Usage:
    python convert_objects.py <input_dir> <output_dir>

Input structure (paradex):
    input_dir/
        object_name/
            raw_mesh/
                object_name.obj
                material.mtl
                material_0.png (or .jpeg)

Output structure:
    output_dir/
        objects/
            object_name/
                mesh.glb
    catalog.json (written to current directory)
"""

import argparse
import json
import os
import sys

try:
    import trimesh
except ImportError:
    print("Error: trimesh is required. Install with: pip install trimesh[easy]")
    sys.exit(1)


def find_obj_file(obj_dir):
    """Find the .obj file inside raw_mesh/ subdirectory."""
    raw_mesh_dir = os.path.join(obj_dir, 'raw_mesh')
    if not os.path.isdir(raw_mesh_dir):
        return None
    for f in os.listdir(raw_mesh_dir):
        if f.lower().endswith('.obj') and 'remeshed' not in f.lower():
            return os.path.join(raw_mesh_dir, f)
    # fallback: any .obj
    for f in os.listdir(raw_mesh_dir):
        if f.lower().endswith('.obj'):
            return os.path.join(raw_mesh_dir, f)
    return None


def name_to_label(name):
    """Convert snake_case name to Title Case label."""
    return name.replace('_', ' ').replace('-', ' ').title()


def guess_category(name):
    """Return empty string — user should fill in categories manually."""
    return ""


def convert_objects(input_dir, output_dir):
    if not os.path.isdir(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist.")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    catalog = {"objects": []}
    items = sorted(os.listdir(input_dir))
    total = 0
    errors = 0

    for name in items:
        obj_dir = os.path.join(input_dir, name)
        if not os.path.isdir(obj_dir):
            continue

        obj_file = find_obj_file(obj_dir)
        if obj_file is None:
            print(f"  SKIP {name}: no .obj file found")
            continue

        out_dir = os.path.join(output_dir, "objects", name)
        os.makedirs(out_dir, exist_ok=True)
        glb_path = os.path.join(out_dir, "mesh.glb")

        try:
            mesh = trimesh.load(obj_file, force='scene')
            mesh.export(glb_path, file_type='glb')
            size_kb = os.path.getsize(glb_path) / 1024
            print(f"  OK   {name} ({size_kb:.0f} KB)")
            total += 1
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            errors += 1
            continue

        catalog["objects"].append({
            "id": name,
            "label": name_to_label(name),
            "category": guess_category(name),
            "url": f"objects/{name}/mesh.glb",
            "thumb": f"objects/{name}/thumb.png"
        })

    # Write catalog
    catalog_path = os.path.join(".", "catalog.json")
    with open(catalog_path, "w") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(f"\nDone: {total} converted, {errors} errors")
    print(f"Catalog written to {catalog_path} ({len(catalog['objects'])} objects)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert OBJ meshes to GLB and generate catalog.json")
    parser.add_argument("input_dir", help="Directory containing object folders with OBJ files")
    parser.add_argument("output_dir", help="Output directory for GLB files")
    args = parser.parse_args()

    convert_objects(args.input_dir, args.output_dir)
