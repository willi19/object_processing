#!/usr/bin/env python3
"""
Upload original OBJ meshes (with MTL + textures) to HuggingFace.

Source: <input_dir>/{name}/raw_mesh/
  - {name}.obj
  - *.mtl (material definitions)
  - *.png/*.jpg (texture images)

Uploads to: willi19/object_processing → objects/{name}/raw/

Usage:
    python upload_obj_to_hf.py <input_dir>
    python upload_obj_to_hf.py <input_dir> --dry-run
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

REPO_ID = "willi19/object_processing"
REPO_TYPE = "dataset"


def collect_raw_mesh_files(raw_mesh_dir):
    """Collect OBJ + MTL + texture files, skipping remeshed variants."""
    files = []
    for f in os.listdir(raw_mesh_dir):
        if "remeshed" in f.lower():
            continue
        if f.startswith("@"):
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext in (".obj", ".mtl", ".png", ".jpg", ".jpeg"):
            files.append(f)
    return files


def main():
    parser = argparse.ArgumentParser(description="Upload OBJ meshes to HuggingFace")
    parser.add_argument("input_dir", help="Directory containing object folders with raw_mesh/ subdirs")
    parser.add_argument("--dry-run", action="store_true", help="Preview without uploading")
    args = parser.parse_args()

    catalog_path = os.path.join(os.path.dirname(__file__), "catalog.json")
    with open(catalog_path) as f:
        catalog = json.load(f)

    object_ids = [o["id"] for o in catalog["objects"]]

    staging = tempfile.mkdtemp(prefix="obj_upload_")
    total = 0
    skipped = []

    for oid in sorted(object_ids):
        raw_mesh_dir = os.path.join(args.input_dir, oid, "raw_mesh")
        if not os.path.isdir(raw_mesh_dir):
            skipped.append(oid)
            continue

        files = collect_raw_mesh_files(raw_mesh_dir)
        obj_files = [f for f in files if f.endswith(".obj")]
        if not obj_files:
            skipped.append(oid)
            continue

        dest_dir = os.path.join(staging, "objects", oid, "raw")
        os.makedirs(dest_dir, exist_ok=True)

        for f in files:
            shutil.copy2(os.path.join(raw_mesh_dir, f), os.path.join(dest_dir, f))

        total += 1
        print(f"  [{total}] {oid}: {', '.join(files)}")

    if skipped:
        print(f"\nSkipped {len(skipped)} objects (no raw_mesh/ found): {skipped}")

    print(f"\nStaged {total} objects for upload.")

    if args.dry_run:
        print("Dry run — not uploading.")
        shutil.rmtree(staging)
        return

    from huggingface_hub import HfApi

    api = HfApi()
    print(f"Uploading to {REPO_ID}...")

    api.upload_large_folder(
        folder_path=staging,
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
    )

    print(f"\nDone! {total} objects uploaded to:")
    print(f"  https://huggingface.co/datasets/{REPO_ID}")

    shutil.rmtree(staging)


if __name__ == "__main__":
    main()
