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
    "apple": "004",
    "baby_beaker": "033",
    "beige_brush": "000",
    "colander_green": "000",
    "blue_vase": "003",
    "box_pink": "002",
    "brass_pot": "017",
    "brown_ramen": "003",
    "container_pink": "005",
    "french_mustard": "002",   # 025 was an impossible resting pose
    "frog_bowl": "000",
    "frog_cup": "002",         # 019 was an impossible resting pose
    "fruit_cutter_base": "004",
    "fruit_cutter_green": "001",   # 009/010/019 were impossible poses
    "fruit_cutter_light_green": "000",   # 010/028/001 were impossible poses
    "green_attached_container": "008",
    "green_lamp": "001",
    "green_soap_dispenser": "002",
    "icecream_scoop": "000",   # 002 was a duplicate pose
    "large_peg": "002",        # 017 was an impossible pose
    "lemon_squeezer": "003",
    "light_green_basket": "001",
    "open_box": "002",
    "organizer_beige": "001",
    "pastel_blue_cup": "000",
    "mug_holder": "009",
    "jja_ramen": "000",
    "pink_clock": "012",
    "paper_bowl": "001",
    "paper_cup": "025",
    "pepper_tuna": "019",
    "pepper_tuna_light": "010",
    "yellow_plastic_cup": "001",
    "wood_tray_big": "001",
    "wood_tray_small": "002",
    "soaptray": "001",
    "standing_frame": "030",   # 034/017 were impossible resting poses
    "yellow_funnel": "001",
    "plant_pot": "001",
    "toothbrush_holder": "024",   # 001 was an impossible resting pose
    "white_plastic_box": "001",
    "white_soap_dish": "002",
    "white_table_lamp": "012",    # 035 was an impossible resting pose
    "white_watering_can": "000",  # 004 was impossible; no truly upright pose exists, 000 is the best of {000,009,018}
    "magazine_file": "007",
    "shoe_organizer": "006",
    "smallbowl": "000",
    "spam_can": "006",
    "wateringcan": "003",
}

# Per-object camera-direction override (object frame, +z up), for objects whose
# default 3/4 view faces an uninteresting side.
VIEW_OVERRIDE = {
    "bamboo_box": np.array([-0.65, 1.0, 0.55]),   # 180deg: clean face, avoids the texture's diagonal grain smear
    "blue_alarm": np.array([0.283, -1.131, 0.4]),  # 225deg from front base (315 + 270 relative)
    "blue_vase": np.array([1.0, 0.65, 0.55]),    # default view rotated 90deg about +z
    "clock": np.array([0.248, 1.166, 0.55]),     # default 3/4 view rotated 135deg about +z
    "donut_light": np.array([1.0, 0.65, 0.55]),  # default view rotated 90deg about +z
    "frame_oak": np.array([0.541, 1.063, 0.55]),    # 120deg from default (300 + 180 relative)
    "frog_cup": np.array([1.0, 0.65, 0.55]),       # default view rotated 90deg about +z
    "green_attached_container": np.array([0.247, 1.167, 0.55]),  # 135deg from default (45 + 90 relative)
    "balloon_whisk": np.array([1.0, 0.65, 0.55]),  # default view rotated 90deg about +z
    "black_holder_with_handle": np.array([-0.541, -1.063, 0.55]),  # default view rotated 300deg
    "container_pink": np.array([0.446, 1.106, 0.55]),   # 125deg from default (305 + 180 relative)
    "french_mustard": np.array([-0.348, -1.141, 0.55]),  # 310deg from default (130 + 180 relative)
    "coffee_tin": np.array([1.0, 0.65, 0.55]),          # default view rotated 90deg about +z
    "corkscrew": np.array([-1.167, 0.247, 0.55]),       # 225deg from default (180 + 45 relative)
    "metal_scoop_big": np.array([-1.167, 0.247, 0.55]),   # 225deg from default (45 + 180 relative)
    "metal_scoop_small": np.array([1.167, -0.247, 0.55]),  # 45deg from default (225 + 180 relative)
    "icecream_scoop": np.array([1.0, 0.65, 0.55]),       # default view rotated 90deg about +z
    "work_lamp": np.array([1.0, 0.65, 0.55]),            # 90deg from default (270 + 180 relative)
    "green_cactus_vase": np.array([0.167, -1.181, 0.55]),  # 335deg from default (45 + 290 relative)
    "box_pink": np.array([-1.0, -0.65, 0.55]),           # default view rotated 270deg about +z
    "pink_clock": np.array([-0.953, 0.717, 0.55]),       # 200deg from default (335 + 225 relative)
    "screwdriver": np.array([-0.269, 1.162, 0.55]),      # 160deg from default (45 + 115 relative)
    "potato_mesher": np.array([0.247, 1.167, 0.55]),     # default view rotated 135deg about +z
    "thermo_clock": np.array([-1.0, -0.65, 0.55]),       # 270deg from default (180 + 90 relative)
    "white_clock": np.array([-0.65, 1.0, 0.55]),         # default view rotated 180deg about +z
    "green_soap_dispenser": np.array([-0.467, 1.098, 0.55]),  # default view rotated 170deg about +z
    "knife_sharpner": np.array([1.063, -0.541, 0.55]),   # 30deg from default (70 - 40 relative)
    "white_soap_dish": np.array([1.0, 0.65, 0.55]),      # 90deg from default (270 + 180 relative)
    "soaptray": np.array([1.0, 0.65, 0.55]),             # default view rotated 90deg about +z
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

    def add(gname, g, mat):
        g.compute_vertex_normals()
        rnd.scene.add_geometry(gname, g, mat)
        pts.append(np.asarray(g.vertices))

    # Branch on vertex-colors. Open3D's OBJ reader (used by read_triangle_model)
    # DROPS per-vertex colors, which are the ONLY color the vertex-colored objects
    # (apple, banana, ...) have — so load those via trimesh. Everything else goes
    # through read_triangle_model, which keeps both the mtl Kd color and the albedo
    # texture (multi-material).
    tmesh = trimesh.load(obj_path, force="mesh")
    has_vc = getattr(tmesh.visual, "kind", None) == "vertex"
    if not has_vc:
        model = o3d.io.read_triangle_model(obj_path)
        for i, mi in enumerate(model.meshes):
            g = mi.mesh
            if P is not None:
                g.transform(P)
            mat = model.materials[mi.material_idx]
            # A dim mtl Kd (brass_pot 0.4) multiplies the albedo down to gray, so
            # show the texture full-bright. With NO texture, keep the Kd color
            # (e.g. green_lamp's yellow-green) rather than a flat default gray.
            if getattr(mat, "albedo_img", None) is not None:
                mat.base_color = [1.0, 1.0, 1.0, 1.0]
            add(f"m{i}", g, mat)
    else:
        g = o3d.geometry.TriangleMesh(
            o3d.utility.Vector3dVector(np.asarray(tmesh.vertices, float)),
            o3d.utility.Vector3iVector(np.asarray(tmesh.faces, np.int32)))
        g.vertex_colors = o3d.utility.Vector3dVector(
            np.asarray(tmesh.visual.vertex_colors)[:, :3] / 255.0)
        if P is not None:
            g.transform(P)
        mat = o3d.visualization.rendering.MaterialRecord()
        mat.shader = "defaultLit"
        mat.base_color = [1.0, 1.0, 1.0, 1.0]
        add("mesh", g, mat)

    # Sun + image-based fill light so the shadowed side isn't near-black.
    rnd.scene.set_lighting(rnd.scene.LightingProfile.SOFT_SHADOWS, [0.3, -0.5, -0.8])
    # The default SOFT_SHADOWS fill crushes dark-colored objects (black bowls, bins)
    # to near-black; lift the indirect (ambient) and sun so they read as a
    # product-photo dark-gray. Light objects don't blow out at these levels.
    rnd.scene.scene.set_indirect_light_intensity(75000)
    rnd.scene.scene.set_sun_light([0.3, -0.5, -0.8], [1.0, 1.0, 1.0], 100000)
    pts = np.vstack(pts)
    mn, mx = pts.min(0), pts.max(0)
    center = ((mn + mx) / 2).tolist()
    radius = float(np.linalg.norm(mx - mn) / 2)
    # Use a longer "lens" (narrow FOV) and pull the camera back to compensate.
    # A wide FOV (55deg) badly exaggerated perspective foreshortening — near parts
    # ballooned ("big-head"/fisheye look, esp. tall objects like jja_ramen). 30deg
    # is much closer to an orthographic, distortion-free projection.
    fov = 30.0
    dist = radius / np.tan(np.deg2rad(fov / 2)) * 1.15  # 15% margin around object
    eye = np.asarray(center) + np.asarray(view_dir) / np.linalg.norm(view_dir) * dist
    # Set the near plane explicitly well in front of the object. Open3D's auto
    # near-plane (via setup_camera) was clipping the object's front face, slicing
    # it open and showing the interior as a cross-section.
    cam = rnd.scene.camera
    cam.set_projection(fov, 1.0, dist * 0.2, dist + radius * 10.0,
                       o3d.visualization.rendering.Camera.FovType.Vertical)
    cam.look_at(center, eye.tolist(), [0.0, 0.0, 1.0])
    img = np.asarray(rnd.render_to_image()).copy()
    del rnd
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("object_root")
    ap.add_argument("output", help="dir; writes <output>/objects/<name>/thumb.png")
    ap.add_argument("--only", help="comma-separated object names")
    ap.add_argument("--info-root", default="docs", help="where objects/<name>/info.json live")
    ap.add_argument("--glb-root", default="wiki/output/objects",
                    help="prefer GLB meshes here (fixed normals; no see-through on hollow objects)")
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
            # Prefer the GLB (same asset the Babylon viewer shows): its normals are
            # fixed, so hollow objects (boxes, baskets, pots) render solid instead of
            # showing through to the gray interior, which the raw OBJ does in Open3D.
            obj = os.path.join(args.glb_root, name, "mesh.glb")
            if not os.path.exists(obj):
                obj = os.path.join(base, "raw_mesh", f"{name}.obj")
                if not os.path.exists(obj):
                    cands = [f for f in os.listdir(os.path.join(base, "raw_mesh"))
                             if f.lower().endswith(".obj")] if os.path.isdir(os.path.join(base, "raw_mesh")) else []
                    if not cands:
                        raise FileNotFoundError("no GLB and no .obj in raw_mesh/")
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
