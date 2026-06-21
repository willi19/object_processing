"""Export per-object assets for the interactive web viewer.

Two products per object:

- **Stage GLBs** (``stages/{raw,coacd,simplified}.glb``) — the mid-pipeline
  meshes the viewer toggles between. ``coacd`` is colored per convex piece so the
  decomposition is visible. These are large and meant to be uploaded to
  HuggingFace alongside the existing ``mesh.glb``.

- **Web info JSON** (``info.json``) — small overlay data in the *object frame*
  (same frame as every stage mesh): the oriented bounding box, the rotational
  symmetry axes, and the stable tabletop poses. Small enough to commit to git and
  serve from GitHub Pages.

Both the meshes and the overlays share one coordinate frame, so the viewer can
draw the overlays directly without any frame conversion.
"""

import glob
import json
import os

import numpy as np
import trimesh

from object_processing.config import obj_dir
from object_processing.pipeline.symmetry import detect_symmetry

# Per-piece colors for the convex decomposition (RGB 0-255), matching render.py.
_PALETTE = [
    (229, 92, 92), (92, 158, 229), (117, 204, 102), (242, 184, 64),
    (178, 122, 219), (92, 204, 199), (237, 140, 77), (140, 166, 102),
    (217, 115, 178),
]

_STAGES = {
    "raw":        "raw_mesh/{obj}.obj",
    "coacd":      "processed_data/mesh/coacd.obj",
    "manifold":   "processed_data/mesh/manifold.obj",
    "simplified": "processed_data/mesh/simplified.obj",
}


def _color_components(mesh):
    """Paint each connected component of ``mesh`` a distinct palette color."""
    parts = mesh.split(only_watertight=False)
    if len(parts) <= 1:
        mesh.visual.face_colors = _PALETTE[0] + (255,)
        return mesh
    for i, part in enumerate(parts):
        part.visual.face_colors = _PALETTE[i % len(_PALETTE)] + (255,)
    return trimesh.util.concatenate(parts)


def export_stage_glbs(obj_name, out_dir, root=None, stages=("raw", "coacd", "simplified")):
    """Export the available stage meshes of one object to GLB. Returns the list
    of stage names written. Missing stage meshes are skipped."""
    base = obj_dir(obj_name) if root is None else os.path.join(root, obj_name)
    os.makedirs(out_dir, exist_ok=True)

    written = []
    for stage in stages:
        src = os.path.join(base, _STAGES[stage].format(obj=obj_name))
        if not os.path.exists(src):
            continue
        if stage == "coacd":
            mesh = trimesh.load(src, force="mesh")
            scene = _color_components(mesh).scene()
        else:
            # force='scene' keeps materials/texture (raw) intact.
            scene = trimesh.load(src, force="scene")
        out = os.path.join(out_dir, f"{stage}.glb")
        scene.export(out, file_type="glb")
        written.append(stage)
    return written


def export_web_info(obj_name, out_path, root=None, max_poses=24):
    """Bundle OBB + symmetry + tabletop poses into one small JSON (object frame).

    Returns the dict written.
    """
    base = obj_dir(obj_name) if root is None else os.path.join(root, obj_name)
    info_dir = os.path.join(base, "processed_data", "info")

    info = {"id": obj_name}

    # Oriented bounding box (from basic_info).
    simp = os.path.join(info_dir, "simplified.json")
    if os.path.exists(simp):
        with open(simp) as f:
            s = json.load(f)
        info["obb"] = {"extents": s["obb"], "transform": s["obb_transform"]}
        info["gravity_center"] = s.get("gravity_center")

    # Rotational symmetry (detect from the simplified mesh for consistency).
    simp_obj = os.path.join(base, "processed_data", "mesh", "simplified.obj")
    if os.path.exists(simp_obj):
        sym = detect_symmetry(simp_obj)
        info["symmetry"] = {
            "type": sym["type"],
            "center": sym["center"],
            "scale": sym["scale"],
            "axes": [{"axis": a["axis"], "fold": a["fold"]} for a in sym["axes"]],
        }

    # Stable tabletop poses (4x4 SE3 each).
    pose_files = sorted(glob.glob(os.path.join(info_dir, "tabletop", "*.npy")))
    poses = [np.load(p).tolist() for p in pose_files[:max_poses]]
    info["tabletop_poses"] = poses
    info["n_tabletop_poses"] = len(pose_files)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(info, f)
    return info


def export_object(obj_name, glb_out_root, info_out_root, root=None):
    """Export one object's stage GLBs (to ``glb_out_root/objects/{id}/stages``)
    and web info JSON (to ``info_out_root/objects/{id}/info.json``)."""
    stages_dir = os.path.join(glb_out_root, "objects", obj_name, "stages")
    info_path = os.path.join(info_out_root, "objects", obj_name, "info.json")
    written = export_stage_glbs(obj_name, stages_dir, root=root)
    info = export_web_info(obj_name, info_path, root=root)
    return written, info


def main(argv=None):
    import argparse
    import sys
    import traceback

    from object_processing.config import object_root

    p = argparse.ArgumentParser(prog="object_processing.webexport")
    p.add_argument("objects", nargs="*", help="object names (or use --all)")
    p.add_argument("--all", action="store_true")
    p.add_argument("--glb-out", default="wiki/output",
                   help="root for stage GLBs (gitignored; upload to HuggingFace)")
    p.add_argument("--info-out", default="docs",
                   help="root for info.json (committed; served by GitHub Pages)")
    a = p.parse_args(argv)

    if a.all:
        r = object_root()
        objs = sorted(d for d in os.listdir(r)
                      if os.path.isdir(os.path.join(r, d, "processed_data", "mesh")))
    elif a.objects:
        objs = a.objects
    else:
        raise SystemExit("specify object name(s) or --all")

    fails = []
    for o in objs:
        try:
            written, info = export_object(o, a.glb_out, a.info_out)
            sym = info.get("symmetry", {}).get("type", "?")
            print(f"  {o}: stages={written} sym={sym} "
                  f"poses={info.get('n_tabletop_poses', 0)}")
        except Exception:
            fails.append(o)
            print(f"  {o}: FAILED\n{traceback.format_exc()}", file=sys.stderr)
    print(f"\n{len(objs) - len(fails)}/{len(objs)} objects exported")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
