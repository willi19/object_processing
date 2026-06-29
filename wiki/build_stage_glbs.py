#!/usr/bin/env python3
"""Build the web-viewer GLBs from the processed pipeline output.

This is the CORRECT source for the wiki meshes: the per-object pipeline output
under ``$OBJECT_ROOT`` (default ~/shared_data/object_processing), NOT the raw
paradex capture folder.

Per object:
    raw_mesh/<name>.obj                       -> objects/<name>/mesh.glb   (display)
    processed_data/mesh/{raw,manifold,         -> objects/<name>/stages/<stage>.glb
                        coacd,simplified}.obj

Usage:
    python build_stage_glbs.py [object_root] [output] [--only a,b,c]

Defaults: object_root=$OBJECT_ROOT or ~/shared_data/object_processing, output=output
"""

import argparse
import os
import sys

try:
    import trimesh
except ImportError:
    print("Error: trimesh is required (pip install trimesh[easy])")
    sys.exit(1)

# Viewer stages, in pipeline order. Files live in processed_data/mesh/.
STAGES = ["raw", "manifold", "coacd", "simplified"]


def obj_to_glb(obj_path, glb_path):
    os.makedirs(os.path.dirname(glb_path), exist_ok=True)
    trimesh.load(obj_path, force="scene").export(glb_path, file_type="glb")
    return os.path.getsize(glb_path)


def find_display_obj(obj_dir):
    """The textured display mesh used for mesh.glb (raw_mesh/<name>.obj)."""
    rm = os.path.join(obj_dir, "raw_mesh")
    if not os.path.isdir(rm):
        return None
    objs = [f for f in sorted(os.listdir(rm))
            if f.lower().endswith(".obj") and "remeshed" not in f.lower()]
    return os.path.join(rm, objs[0]) if objs else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    default_root = os.environ.get("OBJECT_ROOT",
                                  os.path.expanduser("~/shared_data/object_processing"))
    ap.add_argument("object_root", nargs="?", default=default_root)
    ap.add_argument("output", nargs="?", default="output")
    ap.add_argument("--only", help="comma-separated object names to build")
    args = ap.parse_args()

    if not os.path.isdir(args.object_root):
        print(f"Error: object_root '{args.object_root}' not found")
        sys.exit(1)

    only = set(args.only.split(",")) if args.only else None
    names = sorted(d for d in os.listdir(args.object_root)
                   if os.path.isdir(os.path.join(args.object_root, d)))

    total = errors = 0
    for name in names:
        if only and name not in only:
            continue
        odir = os.path.join(args.object_root, name)
        out = os.path.join(args.output, "objects", name)
        try:
            disp = find_display_obj(odir)
            if disp:
                obj_to_glb(disp, os.path.join(out, "mesh.glb"))
            mesh_dir = os.path.join(odir, "processed_data", "mesh")
            built = []
            for s in STAGES:
                sp = os.path.join(mesh_dir, f"{s}.obj")
                if os.path.isfile(sp):
                    obj_to_glb(sp, os.path.join(out, "stages", f"{s}.glb"))
                    built.append(s)
            print(f"  OK   {name}  (mesh{' +' if disp else ' (none) '}{'+'.join(built)})")
            total += 1
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            errors += 1

    print(f"\nDone: {total} objects built, {errors} errors -> {args.output}/objects/")


if __name__ == "__main__":
    main()
