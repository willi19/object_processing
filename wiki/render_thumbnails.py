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
import traceback

import numpy as np
import trimesh
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from object_processing.visualization import render as R

_VIEW_DIR = np.array([0.65, -1.0, 0.55])   # match render.py's 3/4 view

# Per-object pose override: use a specific tabletop pose (.npy filename stem in
# processed_data/info/tabletop/) instead of the auto-selected tallest pose.
POSE_OVERRIDE = {
    "blue_alarm": "000",   # stands the clock up on its legs (vs 011 lying flat)
}

# Per-object camera-direction override (object frame, +z up), for objects whose
# default 3/4 view faces an uninteresting side.
VIEW_OVERRIDE = {
    "blue_alarm": np.array([0.6, 1.0, 0.4]),   # front-3/4, shows the standing clock
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
    rnd = o3d.visualization.rendering.OffscreenRenderer(size, size)
    rnd.scene.set_background([*bg_rgb, 1.0])

    pts = []

    def add_two_sided(gname, g, mat):
        # Most scans are thin OPEN shells; the offscreen renderer culls backfaces,
        # so any camera angle that looks into a cavity shows dark backface "holes".
        # Add a winding-flipped copy so the inside renders lit too (two-sided),
        # matching Babylon / the interactive Open3D viewer.
        g.compute_vertex_normals()
        rnd.scene.add_geometry(gname, g, mat)
        # The back copy is coplanar with the front, so it z-fights it. Make it an
        # IDENTICAL clone (reversed winding + matching UVs/textures/colors) so the
        # z-fight is invisible — otherwise it washes out the front's texture/color.
        tri = np.asarray(g.triangles)[:, ::-1]
        back = o3d.geometry.TriangleMesh(g.vertices, o3d.utility.Vector3iVector(tri))
        if g.has_vertex_colors():
            back.vertex_colors = g.vertex_colors
        if g.has_triangle_uvs():
            uv = np.asarray(g.triangle_uvs).reshape(-1, 3, 2)[:, ::-1, :].reshape(-1, 2)
            back.triangle_uvs = o3d.utility.Vector2dVector(uv)
        if g.textures:
            back.textures = g.textures
        back.compute_vertex_normals()
        rnd.scene.add_geometry(gname + "_back", back, mat)
        pts.append(np.asarray(g.vertices))

    # Textured objects carry albedo via read_triangle_model (multi-material). But
    # that reader DROPS vertex colors — and the untextured objects (apple, banana,
    # ... the no-texture list) are colored *only* by vertex colors. So load those
    # with _load, which keeps the vertex colors, and let them drive the shading.
    raw_dir = os.path.dirname(obj_path)
    textured = os.path.isdir(raw_dir) and any(
        f.lower().endswith((".png", ".jpg", ".jpeg")) for f in os.listdir(raw_dir))
    if textured:
        model = o3d.io.read_triangle_model(obj_path)
        for i, mi in enumerate(model.meshes):
            g = mi.mesh
            if P is not None:
                g.transform(P)
            add_two_sided(f"m{i}", g, model.materials[mi.material_idx])
    else:
        # Open3D's OBJ reader ignores per-vertex colors, so load with trimesh
        # (which reads them) and copy the colors onto an Open3D mesh.
        tm = trimesh.load(obj_path, force="mesh")
        g = o3d.geometry.TriangleMesh(
            o3d.utility.Vector3dVector(np.asarray(tm.vertices, float)),
            o3d.utility.Vector3iVector(np.asarray(tm.faces, np.int32)))
        vc = getattr(tm.visual, "vertex_colors", None)
        if vc is not None and len(vc) == len(tm.vertices):
            g.vertex_colors = o3d.utility.Vector3dVector(np.asarray(vc)[:, :3] / 255.0)
        if P is not None:
            g.transform(P)
        mat = o3d.visualization.rendering.MaterialRecord()
        mat.shader = "defaultLit"
        mat.base_color = [1.0, 1.0, 1.0, 1.0] if g.has_vertex_colors() else [*base_color, 1.0]
        add_two_sided("mesh", g, mat)

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
    failed = []
    for name in names:
        if only and name not in only:
            continue
        try:
            base = os.path.join(args.object_root, name)
            obj = os.path.join(base, "raw_mesh", f"{name}.obj")
            if not os.path.exists(obj):
                cands = [f for f in os.listdir(os.path.join(base, "raw_mesh"))
                         if f.lower().endswith(".obj")] if os.path.isdir(os.path.join(base, "raw_mesh")) else []
                if not cands:
                    raise FileNotFoundError("no .obj in raw_mesh/")
                obj = os.path.join(base, "raw_mesh", cands[0])
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
        except Exception:
            # Catch per-object so one bad object doesn't block the rest — but NEVER
            # silently: print the full traceback now and exit non-zero at the end.
            traceback.print_exc()
            print(f"  ERROR {name} — see traceback above", file=sys.stderr)
            failed.append(name)
    print(f"\nDone: {n} rendered, {len(failed)} failed")
    if failed:
        raise SystemExit(f"{len(failed)} object(s) FAILED: {failed}")


if __name__ == "__main__":
    main()
