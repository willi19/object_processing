#!/usr/bin/env python3
"""Render the per-feature showcase images for the landing page, from one object.

For the "What you get for every object" section of index.html: one image per
feature (textured / collision / watertight / simplified / bounding box /
symmetry / tabletop), rendered from a single demo object in its teaser pose so
every tile shares a pose and camera. Writes to <out>/<feature>.png on white.

Run with the Open3D + EGL env (no mujoco needed — poses are precomputed):
    ~/miniconda3/envs/object_processing/bin/python wiki/render_features.py \
        ~/shared_data/object_processing docs/img/features --object french_mustard
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from object_processing.visualization import render as R
from object_processing.visualization.poses import teaser_pose

_WHITE = [1.0, 1.0, 1.0, 1.0]
_AXIS_COLORS = [(1.0, 0.82, 0.1), (0.2, 0.85, 0.4), (0.36, 0.62, 0.95)]


def _key_white(img):
    """Key the uniform corner background to pure white for clean compositing."""
    corner = img[1, 1].astype(int)
    img[np.abs(img.astype(int) - corner).max(2) <= 10] = 255
    return img


def _textured(o3d, base, name, P, center, radius, size, overlays=()):
    """Render the textured display mesh (posed) on white, with optional overlay
    linesets (already in object frame; transformed by P here)."""
    rnd = o3d.visualization.rendering.OffscreenRenderer(size, size)
    rnd.scene.set_background(_WHITE)
    rnd.scene.set_lighting(rnd.scene.LightingProfile.SOFT_SHADOWS, [0.3, -0.5, -0.8])
    rnd.scene.scene.set_indirect_light_intensity(75000)
    rnd.scene.scene.set_sun_light([0.3, -0.5, -0.8], [1.0, 1.0, 1.0], 100000)
    R._add_textured(o3d, rnd, base, name, P)
    for gname, ls in overlays:
        ls.transform(P)
        rnd.scene.add_geometry(gname, ls, R._line_material(o3d, 5.0))
    eye = np.asarray(center) + R._VIEW_DIR / np.linalg.norm(R._VIEW_DIR) * radius * 2.3
    rnd.setup_camera(55.0, list(center), eye.tolist(), [0.0, 0.0, 1.0])
    img = np.asarray(rnd.render_to_image()).copy()
    del rnd
    return _key_white(img)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("object_root")
    ap.add_argument("out", help="output dir for <feature>.png")
    ap.add_argument("--object", default="french_mustard")
    ap.add_argument("--size", type=int, default=640)
    a = ap.parse_args()

    o3d = R._o3d()
    name, base, size = a.object, os.path.join(a.object_root, a.object), a.size
    os.makedirs(a.out, exist_ok=True)
    Pt = teaser_pose(name, base)
    P = np.asarray(Pt) if Pt is not None else np.eye(4)

    def posed(rel):
        m = R._load(o3d, os.path.join(base, rel))
        m.transform(P)
        return m

    def save(img, fn):
        Image.fromarray(img).save(os.path.join(a.out, fn))
        print("  wrote", fn)

    # Shared framing from the posed raw mesh (full extent).
    raw = posed(f"raw_mesh/{name}.obj")
    center, radius = R._bounds(raw)
    center = list(center)

    # Textured display mesh.
    save(_textured(o3d, base, name, P, center, radius, size), "textured.png")

    # Collision mesh — convex decomposition, colored per piece.
    pieces = os.path.join(base, "processed_data", "urdf", "meshes")
    colored = R._coacd_colored(o3d, pieces)
    cm = colored if colored is not None else \
        R._paint_components(o3d, R._load(o3d, os.path.join(base, "processed_data/mesh/coacd.obj")))
    cm.transform(P)
    save(R.render_mesh(cm, size, size, center=center, radius=radius,
                       base_color=(1.0, 1.0, 1.0)), "collision.png")

    # Watertight (manifold) — solid, so the closed surface reads.
    save(R.render_mesh(posed("processed_data/mesh/manifold.obj"), size, size,
                       center=center, radius=radius,
                       base_color=(0.78, 0.80, 0.83)), "watertight.png")

    # Simplified — wireframe, so the decimation is visible.
    save(R.render_mesh(posed("processed_data/mesh/simplified.obj"), size, size,
                       center=center, radius=radius, wireframe=True), "simplified.png")

    # Bounding box — textured mesh + oriented bounding box (blue).
    info_dir = os.path.join(base, "processed_data", "info")
    simp = os.path.join(info_dir, "simplified.json")
    obb_ov = []
    if os.path.exists(simp):
        s = json.load(open(simp))
        obb_ov = [("obb", R._obb_lineset(o3d, s["obb"], s["obb_transform"], (0.20, 0.45, 1.0)))]
    save(_textured(o3d, base, name, P, center, radius, size, overlays=obb_ov), "bbox.png")

    # Symmetry — textured mesh + rotational symmetry axes.
    sym_path = os.path.join(info_dir, "symmetry.json")
    sym_ov = []
    if os.path.exists(sym_path):
        sym = json.load(open(sym_path))
        ctr = np.asarray(sym["center"]); L = sym["scale"] * 0.6
        for i, ax in enumerate(sym.get("axes", [])):
            d = np.asarray(ax["axis"])
            ls = o3d.geometry.LineSet()
            ls.points = o3d.utility.Vector3dVector([ctr - d * L, ctr + d * L])
            ls.lines = o3d.utility.Vector2iVector([[0, 1]])
            ls.paint_uniform_color(list(_AXIS_COLORS[i % len(_AXIS_COLORS)]))
            sym_ov.append((f"axis_{i}", ls))
    save(_textured(o3d, base, name, P, center, radius, size, overlays=sym_ov), "symmetry.png")

    # Tabletop — every stable resting pose on a ground plane.
    R.render_tabletop_figure(name, os.path.join(a.out, "tabletop.png"),
                             root=a.object_root, width=size, height=size)
    print("  wrote tabletop.png")
    print("DONE ->", a.out)


if __name__ == "__main__":
    main()
