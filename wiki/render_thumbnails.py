#!/usr/bin/env python3
"""Render object thumbnails with Open3D (headless EGL) in standing pose.

Run with the env that has a working Open3D + EGL, e.g.:
    ~/miniconda3/envs/object_processing/bin/python wiki/render_thumbnails.py \
        ~/shared_data/object_processing OUT [--only a,b] [--bg 595c61]

Per object: load the textured display mesh (raw_mesh/<name>.obj), rotate it onto
its most-upright stable tabletop pose (from the committed info.json), and render a
square thumbnail on a flat background. Supersampled then downscaled for clean AA.
"""

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from object_processing.visualization import render as R

_VIEW_DIR = np.array([0.65, -1.0, 0.55])   # match render.py's 3/4 view

# Per-object pose override: use a specific tabletop pose (.npy filename stem in
# processed_data/info/tabletop/) instead of the auto-selected tallest pose.
POSE_OVERRIDE = {
    "blue_alarm": "011",
}

# Per-object camera-direction override (object frame, +z up), for objects whose
# default 3/4 view faces an uninteresting side.
VIEW_OVERRIDE = {
    "blue_alarm": np.array([-0.65, 1.0, 0.55]),   # show the display-window front
}


def standing_transform(info):
    """4x4 object->table transform for the most-upright stable pose, or None."""
    poses, obb = info.get("tabletop_poses"), info.get("obb")
    if not poses or not obb:
        return None
    e = obb["extents"]
    T = np.array(obb["transform"])
    hx, hy, hz = e[0] / 2, e[1] / 2, e[2] / 2
    local = np.array([[sx * hx, sy * hy, sz * hz, 1.0]
                      for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]).T
    cobj = T @ local
    best, best_h = None, -1e9
    for pose in poses:
        P = np.array(pose)
        w = P @ cobj
        h = w[2].max() - w[2].min()
        if h > best_h:
            best_h, best = h, P
    return best


def render_thumb(o3d, obj_path, P, size, bg_rgb, view_dir=_VIEW_DIR, base_color=(0.85, 0.86, 0.88)):
    """Render an object's OWN materials (handles multi-texture meshes), in the
    standing pose ``P`` (4x4 or None), on a flat ``bg_rgb`` background."""
    model = o3d.io.read_triangle_model(obj_path)
    rnd = o3d.visualization.rendering.OffscreenRenderer(size, size)
    rnd.scene.set_background([*bg_rgb, 1.0])

    pts = []
    if model.meshes:                       # textured / multi-material path
        for i, mi in enumerate(model.meshes):
            g = mi.mesh
            if P is not None:
                g.transform(P)
            g.compute_vertex_normals()
            rnd.scene.add_geometry(f"m{i}", g, model.materials[mi.material_idx])
            pts.append(np.asarray(g.vertices))
    else:                                  # fallback: bare geometry, no materials
        g = R._load(o3d, obj_path)
        if P is not None:
            g.transform(P)
            g.compute_vertex_normals()
        mat = o3d.visualization.rendering.MaterialRecord()
        mat.shader = "defaultLit"
        mat.base_color = [*base_color, 1.0]
        rnd.scene.add_geometry("mesh", g, mat)
        pts.append(np.asarray(g.vertices))

    # Sun + image-based fill light so the shadowed side isn't near-black.
    rnd.scene.set_lighting(rnd.scene.LightingProfile.SOFT_SHADOWS, [0.3, -0.5, -0.8])
    pts = np.vstack(pts)
    mn, mx = pts.min(0), pts.max(0)
    center = ((mn + mx) / 2).tolist()
    radius = float(np.linalg.norm(mx - mn) / 2)
    eye = np.asarray(center) + np.asarray(view_dir) / np.linalg.norm(view_dir) * radius * 2.3
    rnd.setup_camera(55.0, center, eye.tolist(), [0.0, 0.0, 1.0])
    img = np.asarray(rnd.render_to_image()).copy()
    del rnd
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("object_root")
    ap.add_argument("output", help="dir; writes <output>/objects/<name>/thumb.png")
    ap.add_argument("--only", help="comma-separated object names")
    ap.add_argument("--info-root", default="docs", help="where objects/<name>/info.json live")
    ap.add_argument("--bg", default="faf8f5", help="background hex (no #), default = page cream")
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--ss", type=int, default=3, help="supersample factor")
    args = ap.parse_args()

    bg = tuple(int(args.bg[i:i+2], 16) / 255 for i in (0, 2, 4))
    o3d = R._o3d()
    only = set(args.only.split(",")) if args.only else None
    names = sorted(d for d in os.listdir(args.object_root)
                   if os.path.isdir(os.path.join(args.object_root, d)))

    n = 0
    for name in names:
        if only and name not in only:
            continue
        base = os.path.join(args.object_root, name)
        obj = os.path.join(base, "raw_mesh", f"{name}.obj")
        if not os.path.exists(obj):
            cands = [f for f in os.listdir(os.path.join(base, "raw_mesh"))
                     if f.lower().endswith(".obj")] if os.path.isdir(os.path.join(base, "raw_mesh")) else []
            if not cands:
                raise FileNotFoundError(f"{name}: no .obj in raw_mesh/")
            obj = os.path.join(base, "raw_mesh", cands[0])
        # No try/except: let any failure raise with its full traceback rather than
        # swallowing it into a FAIL/SKIP line.
        if name in POSE_OVERRIDE:
            P = np.load(os.path.join(base, "processed_data", "info", "tabletop",
                                     f"{POSE_OVERRIDE[name]}.npy"))
        else:
            P = None
            info_path = os.path.join(args.info_root, "objects", name, "info.json")
            if os.path.exists(info_path):
                P = standing_transform(json.load(open(info_path)))
        img = render_thumb(o3d, obj, P, args.size * args.ss, bg,
                           view_dir=VIEW_OVERRIDE.get(name, _VIEW_DIR))
        thumb = Image.fromarray(img).resize((args.size, args.size), Image.LANCZOS)
        # The renderer's tone-mapping shifts the flat background a few levels;
        # flood-fill the corners back to the exact target so it matches the page.
        tgt = tuple(int(round(c * 255)) for c in bg)
        w, h = thumb.size
        for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
            ImageDraw.floodfill(thumb, seed, tgt, thresh=18)
        out_dir = os.path.join(args.output, "objects", name)
        os.makedirs(out_dir, exist_ok=True)
        thumb.save(os.path.join(out_dir, "thumb.png"))
        print(f"  OK   {name}")
        n += 1
    print(f"\nDone: {n} rendered")


if __name__ == "__main__":
    main()
