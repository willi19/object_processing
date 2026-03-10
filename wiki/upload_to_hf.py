#!/usr/bin/env python3
"""
Upload GLB files to HuggingFace dataset repo.

Usage:
    python upload_to_hf.py <glb_dir>

Example:
    python upload_to_hf.py output

This uploads output/objects/*/mesh.glb to:
    willi19/autodex-objects  (dataset repo)
    → objects/{name}/mesh.glb
"""

import argparse
import os
import sys

from huggingface_hub import HfApi

REPO_ID = "willi19/autodex-objects"
REPO_TYPE = "dataset"


def upload(glb_dir):
    api = HfApi()

    # Ensure repo exists
    try:
        api.create_repo(repo_id=REPO_ID, repo_type=REPO_TYPE, exist_ok=True)
    except Exception as e:
        print(f"Warning: could not create repo: {e}")

    objects_dir = os.path.join(glb_dir, "objects")
    if not os.path.isdir(objects_dir):
        print(f"Error: {objects_dir} not found")
        sys.exit(1)

    items = sorted(os.listdir(objects_dir))
    total = len(items)

    print(f"Uploading {total} objects to {REPO_ID}...")

    # Upload entire folder at once (much faster than individual files)
    api.upload_folder(
        folder_path=objects_dir,
        path_in_repo="objects",
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        commit_message=f"Add {total} object meshes (GLB)",
    )

    print(f"\nDone! {total} objects uploaded to:")
    print(f"  https://huggingface.co/datasets/{REPO_ID}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload GLB files to HuggingFace")
    parser.add_argument("glb_dir", help="Directory containing objects/ subfolder with GLB files")
    args = parser.parse_args()

    upload(args.glb_dir)
