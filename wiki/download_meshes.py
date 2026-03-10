#!/usr/bin/env python3
"""
Download object meshes from HuggingFace.

Usage:
    python download_meshes.py --all                     # download all OBJ meshes
    python download_meshes.py apple banana baseball     # download specific objects
    python download_meshes.py --all --format glb        # download GLB instead
    python download_meshes.py --list                    # list available objects
    python download_meshes.py --output ./meshes --all   # custom output directory
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

HF_BASE = "https://huggingface.co/datasets/willi19/object_processing/resolve/main/"


def fetch_catalog():
    """Fetch catalog.json from local copy or HuggingFace."""
    local = os.path.join(os.path.dirname(__file__), "catalog.json")
    if os.path.exists(local):
        with open(local) as f:
            return json.load(f)

    print("Fetching catalog from HuggingFace...")
    with urllib.request.urlopen(HF_BASE + "catalog.json") as resp:
        return json.loads(resp.read().decode())


def download_file(url, dest):
    """Download a file from URL to dest path."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def download_glb(obj_id, output_dir):
    """Download GLB file for an object."""
    url = f"{HF_BASE}objects/{obj_id}/mesh.glb"
    dest = os.path.join(output_dir, obj_id, "mesh.glb")
    if download_file(url, dest):
        size_kb = os.path.getsize(dest) / 1024
        print(f"  {obj_id}/mesh.glb ({size_kb:.0f} KB)")
        return True
    else:
        print(f"  {obj_id}/mesh.glb — not found")
        return False


def download_obj(obj_id, output_dir):
    """Download OBJ + MTL + texture files for an object."""
    base_url = f"{HF_BASE}objects/{obj_id}/raw/"
    dest_dir = os.path.join(output_dir, obj_id)
    os.makedirs(dest_dir, exist_ok=True)

    downloaded = []

    # Download OBJ
    obj_name = f"{obj_id}.obj"
    if download_file(base_url + obj_name, os.path.join(dest_dir, obj_name)):
        downloaded.append(obj_name)
    else:
        print(f"  {obj_id} — OBJ not found")
        return False

    # Try MTL files
    for mtl_name in [f"{obj_id}.mtl", "material.mtl"]:
        if download_file(base_url + mtl_name, os.path.join(dest_dir, mtl_name)):
            downloaded.append(mtl_name)
            break

    # Try texture files (up to 5 per pattern)
    for pattern_fn in [
        lambda i: f"{obj_id}_{i}.png",
        lambda i: f"material_{i}.png",
    ]:
        for i in range(5):
            tex_name = pattern_fn(i)
            if download_file(base_url + tex_name, os.path.join(dest_dir, tex_name)):
                downloaded.append(tex_name)
            else:
                break

    print(f"  {obj_id}: {', '.join(downloaded)}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Download object meshes from HuggingFace"
    )
    parser.add_argument("objects", nargs="*", help="Object IDs to download")
    parser.add_argument("--all", action="store_true", help="Download all objects")
    parser.add_argument("--format", choices=["obj", "glb"], default="obj",
                        help="Mesh format (default: obj)")
    parser.add_argument("--output", "-o", default="./downloaded_meshes",
                        help="Output directory (default: ./downloaded_meshes)")
    parser.add_argument("--list", action="store_true", help="List available objects")
    args = parser.parse_args()

    catalog = fetch_catalog()
    all_ids = [o["id"] for o in catalog["objects"]]

    if args.list:
        print(f"Available objects ({len(all_ids)}):")
        for obj in catalog["objects"]:
            print(f"  {obj['id']:40s} {obj['label']}")
        return

    if not args.all and not args.objects:
        parser.print_help()
        sys.exit(1)

    ids = all_ids if args.all else args.objects

    invalid = [oid for oid in ids if oid not in all_ids]
    for oid in invalid:
        print(f"Warning: '{oid}' not found in catalog, skipping.")
    ids = [oid for oid in ids if oid in all_ids]

    download_fn = download_glb if args.format == "glb" else download_obj
    fmt_label = "GLB" if args.format == "glb" else "OBJ"

    print(f"Downloading {len(ids)} meshes ({fmt_label}) to {args.output}/\n")

    success = 0
    for oid in ids:
        if download_fn(oid, args.output):
            success += 1

    print(f"\nDone! {success}/{len(ids)} objects downloaded to {args.output}/")


if __name__ == "__main__":
    main()
