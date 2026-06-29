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
import glob
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from object_processing.visualization import render as R
from object_processing.visualization.poses import teaser_pose

_WHITE = [1.0, 1.0, 1.0, 1.0]
# High-contrast axis colors: the default golden axis vanishes against yellow
# objects (e.g. the mustard bottle), so use saturated magenta / blue / orange.
_AXIS_COLORS = [(0.85, 0.10, 0.55), (0.10, 0.55, 0.90), (0.95, 0.50, 0.10)]


def _symmetry_label(t):
    """Human-readable description of a symmetry group code (Cn / Dn / Cinf / ...).
    Returns (description, code) so the image can show both."""
    if not t:
        return ("", "")
    t = t.strip()
    if t in ("C1", "1"):
        return ("No symmetry", t)
    if t == "Cinf":
        return ("Axially symmetric", t)
    if t == "Dinf":
        return ("Axially symmetric, with mirror", t)
    if t.startswith("C") and t[1:].isdigit():
        return (f"{t[1:]}-fold rotational symmetry", t)
    if t.startswith("D") and t[1:].isdigit():
        return (f"{t[1:]}-fold rotational + mirror", t)
    return (t, t)


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


def _textured_parts(o3d, base, name):
    """[(TriangleMesh, MaterialRecord)] for the object's textured display mesh in
    object frame. Per-vertex-color meshes load via trimesh; the rest via
    read_triangle_model so mtl Kd + albedo textures survive."""
    import trimesh
    raw_dir = os.path.join(base, "raw_mesh")
    obj_path = os.path.join(raw_dir, f"{name}.obj")
    if not os.path.exists(obj_path):
        cands = [f for f in os.listdir(raw_dir) if f.lower().endswith(".obj")]
        obj_path = os.path.join(raw_dir, cands[0])
    tmesh = trimesh.load(obj_path, force="mesh")
    parts = []
    if getattr(tmesh.visual, "kind", None) != "vertex":
        model = o3d.io.read_triangle_model(obj_path)
        for mi in model.meshes:
            mat = model.materials[mi.material_idx]
            if getattr(mat, "albedo_img", None) is not None:
                mat.base_color = [1.0, 1.0, 1.0, 1.0]
            parts.append((mi.mesh, mat))
    else:
        g = o3d.geometry.TriangleMesh(
            o3d.utility.Vector3dVector(np.asarray(tmesh.vertices, float)),
            o3d.utility.Vector3iVector(np.asarray(tmesh.faces, np.int32)))
        g.vertex_colors = o3d.utility.Vector3dVector(
            np.asarray(tmesh.visual.vertex_colors)[:, :3] / 255.0)
        mat = o3d.visualization.rendering.MaterialRecord()
        mat.shader = "defaultLit"; mat.base_color = [1.0, 1.0, 1.0, 1.0]
        parts.append((g, mat))
    return parts


def _ground(o3d, gw, gd, drop):
    g = o3d.geometry.TriangleMesh.create_box(gw, gd, drop)
    g.translate([-gw / 2, -gd / 2, -drop])
    g.compute_vertex_normals()
    mat = o3d.visualization.rendering.MaterialRecord()
    mat.shader = "defaultLit"; mat.base_color = [0.92, 0.92, 0.94, 1.0]
    return g, mat


def render_tabletop_textured(o3d, base, name, out_path, size):
    """Textured version of the tabletop figure: the object's own materials,
    placed in each stable pose on a ground plane."""
    pose_files = sorted(glob.glob(os.path.join(base, "processed_data/info/tabletop/*.npy")))
    poses = [np.load(p) for p in pose_files]
    parts = _textured_parts(o3d, base, name)
    allv = np.vstack([np.asarray(g.vertices) for g, _ in parts])
    diag = float(np.linalg.norm(allv.max(0) - allv.min(0)))
    spacing = diag * 1.25
    n = len(poses); cols = int(np.ceil(np.sqrt(n))); rows = int(np.ceil(n / cols))

    rnd = o3d.visualization.rendering.OffscreenRenderer(size, size)
    rnd.scene.set_background(_WHITE)
    rnd.scene.set_lighting(rnd.scene.LightingProfile.SOFT_SHADOWS, [0.3, -0.5, -0.8])
    rnd.scene.scene.set_indirect_light_intensity(75000)
    rnd.scene.scene.set_sun_light([0.3, -0.5, -0.8], [1.0, 1.0, 1.0], 100000)
    for k, Pk in enumerate(poses):
        dx = ((k % cols) - (cols - 1) / 2) * spacing
        dy = (k // cols - (rows - 1) / 2) * spacing
        T = np.eye(4); T[:3, 3] = [dx, dy, 0]
        M = T @ np.asarray(Pk)
        for j, (g, mat) in enumerate(parts):
            gc = o3d.geometry.TriangleMesh(g)
            gc.transform(M); gc.compute_vertex_normals()
            rnd.scene.add_geometry(f"p{k}_{j}", gc, mat)
    gw, gd = cols * spacing + diag, rows * spacing + diag
    g, gmat = _ground(o3d, gw, gd, diag * 0.02)
    rnd.scene.add_geometry("ground", g, gmat)
    center = [0.0, 0.0, diag * 0.25]; span = max(gw, gd)
    vd = np.array([0.35, -1.0, 0.6]); vd /= np.linalg.norm(vd)
    eye = np.array(center) + vd * span * 0.85
    rnd.setup_camera(50.0, center, eye.tolist(), [0.0, 0.0, 1.0])
    img = np.asarray(rnd.render_to_image())
    del rnd
    Image.fromarray(img).save(out_path)
    print("  wrote", os.path.basename(out_path))


def render_simready(o3d, base, name, P, center, radius, size, out_path):
    """A drop-in sim scene: the textured object resting on a ground plane with an
    XYZ body frame at the origin — what a URDF / MJCF places into a simulator."""
    rnd = o3d.visualization.rendering.OffscreenRenderer(size, size)
    rnd.scene.set_background(_WHITE)
    rnd.scene.set_lighting(rnd.scene.LightingProfile.SOFT_SHADOWS, [0.3, -0.5, -0.8])
    rnd.scene.scene.set_indirect_light_intensity(75000)
    rnd.scene.scene.set_sun_light([0.3, -0.5, -0.8], [1.0, 1.0, 1.0], 100000)
    R._add_textured(o3d, rnd, base, name, P)
    g, gmat = _ground(o3d, radius * 3.2, radius * 3.2, radius * 0.03)
    gmat.base_color = [0.86, 0.86, 0.89, 1.0]
    rnd.scene.add_geometry("ground", g, gmat)
    # XYZ body frame at the origin. Sized so X/Y extend across the footprint and
    # Z rises past the object, since the origin itself sits under the mesh.
    frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=radius * 1.5, origin=[0, 0, 0])
    fmat = o3d.visualization.rendering.MaterialRecord(); fmat.shader = "defaultLit"
    rnd.scene.add_geometry("frame", frame, fmat)
    eye = np.asarray(center) + R._VIEW_DIR / np.linalg.norm(R._VIEW_DIR) * radius * 2.3
    rnd.setup_camera(55.0, list(center), eye.tolist(), [0.0, 0.0, 1.0])
    img = np.asarray(rnd.render_to_image()).copy()
    del rnd
    Image.fromarray(_key_white(img)).save(out_path)
    print("  wrote", os.path.basename(out_path))


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

    # Symmetry — textured mesh + rotational symmetry axes, with the group type
    # (e.g. C2 / Dinf) written on the image.
    sym_path = os.path.join(info_dir, "symmetry.json")
    sym_ov, sym_type = [], None
    if os.path.exists(sym_path):
        sym = json.load(open(sym_path))
        sym_type = sym.get("type")
        ctr = np.asarray(sym["center"]); L = sym["scale"] * 0.6
        for i, ax in enumerate(sym.get("axes", [])):
            d = np.asarray(ax["axis"])
            ls = o3d.geometry.LineSet()
            ls.points = o3d.utility.Vector3dVector([ctr - d * L, ctr + d * L])
            ls.lines = o3d.utility.Vector2iVector([[0, 1]])
            ls.paint_uniform_color(list(_AXIS_COLORS[i % len(_AXIS_COLORS)]))
            sym_ov.append((f"axis_{i}", ls))
    sym_img = Image.fromarray(_textured(o3d, base, name, P, center, radius, size, overlays=sym_ov))
    if sym_type:
        desc, code = _symmetry_label(sym_type)
        draw = ImageDraw.Draw(sym_img)
        big, small = R._font(max(16, int(size * 0.05))), R._font(max(11, int(size * 0.03)))
        x, y = int(size * 0.045), int(size * 0.035)
        draw.text((x, y), desc, font=big, fill=(156, 74, 47))   # terracotta accent
        draw.text((x, y + int(size * 0.065)), code, font=small, fill=(138, 129, 120))
    sym_img.save(os.path.join(a.out, "symmetry.png"))
    print("  wrote symmetry.png")

    # Tabletop — every stable resting pose on a ground plane, textured.
    render_tabletop_textured(o3d, base, name, os.path.join(a.out, "tabletop.png"), size)

    # Sim-ready URDF / MJCF — object on a ground plane with an XYZ body frame.
    render_simready(o3d, base, name, P, center, radius, size,
                    os.path.join(a.out, "urdf.png"))
    print("DONE ->", a.out)


if __name__ == "__main__":
    main()
