"""Headless Open3D rendering utilities for the object pipeline.

Renders processed meshes to PNG images with no display, using Open3D's
OffscreenRenderer (the same GPU renderer AutoDex uses for its turntable / scene
figures). Two things it produces:

- ``render_pipeline_figure`` — a labeled side-by-side strip of one object's
  pipeline stages (raw -> coacd -> manifold -> simplified), for docs/README.
- ``turntable_frames`` / ``save_turntable_gif`` — a spinning view of a mesh.

Open3D is an optional, heavy dependency and is imported lazily inside the
functions, so importing this module (or the rest of ``object_processing``) never
requires it. Run standalone::

    python -m object_processing.render pipeline pringles --out /tmp/pringles.png
    python -m object_processing.render turntable book --out /tmp/book.gif
"""

import argparse
import os

import numpy as np

from object_processing.config import obj_dir

# A consistent 3/4 view direction (object frame, +z up) used for every render so
# pipeline stages line up.
_VIEW_DIR = np.array([0.65, -1.0, 0.55])
_BG = [1.0, 1.0, 1.0, 1.0]

# Distinct colors for convex-decomposition pieces (RGB, 0-1).
_PALETTE = [
    (0.90, 0.36, 0.36), (0.36, 0.62, 0.90), (0.46, 0.80, 0.40),
    (0.95, 0.72, 0.25), (0.70, 0.48, 0.86), (0.36, 0.80, 0.78),
    (0.93, 0.55, 0.30), (0.55, 0.65, 0.40), (0.85, 0.45, 0.70),
]


def _o3d():
    import open3d as o3d  # lazy: keeps Open3D optional for the rest of the package
    return o3d


def _load(o3d, path, post=True):
    mesh = o3d.io.read_triangle_mesh(path, enable_post_processing=post)
    if len(mesh.triangles) == 0:
        # Open3D's OBJ reader occasionally returns empty; fall back to trimesh.
        import trimesh
        tm = trimesh.load(path, force="mesh")
        mesh = o3d.geometry.TriangleMesh(
            o3d.utility.Vector3dVector(np.asarray(tm.vertices, float)),
            o3d.utility.Vector3iVector(np.asarray(tm.faces, np.int32)),
        )
    if len(mesh.triangles) == 0:
        raise ValueError(f"render: empty mesh {path}")
    mesh.compute_vertex_normals()
    return mesh


def _bounds(mesh):
    aabb = mesh.get_axis_aligned_bounding_box()
    center = aabb.get_center()
    radius = float(np.linalg.norm(aabb.get_extent())) / 2.0
    return center, max(radius, 1e-6)


def _paint_components(o3d, mesh):
    """Color each connected component a distinct palette color (for coacd)."""
    labels = np.asarray(
        mesh.cluster_connected_triangles()[0]
    )
    if labels.size == 0:
        return mesh
    tri = np.asarray(mesh.triangles)
    vcol = np.ones((len(mesh.vertices), 3))
    for lbl in np.unique(labels):
        color = _PALETTE[int(lbl) % len(_PALETTE)]
        verts = np.unique(tri[labels == lbl])
        vcol[verts] = color
    mesh.vertex_colors = o3d.utility.Vector3dVector(vcol)
    return mesh


def render_mesh(mesh, width=720, height=720, center=None, radius=None,
                bg=_BG, base_color=(0.78, 0.80, 0.83), fov=55.0,
                albedo_path=None, wireframe=False):
    """Render an Open3D ``mesh`` to an HxWx3 uint8 array.

    ``center``/``radius`` override auto-framing so several meshes can share a
    camera. ``albedo_path`` textures the surface; ``wireframe`` overlays mesh
    edges (so polygon density is visible). Vertex colors, if present, win over
    ``base_color``. The (uniform) background is keyed to pure white.
    """
    o3d = _o3d()
    if center is None or radius is None:
        center, radius = _bounds(mesh)

    rnd = o3d.visualization.rendering.OffscreenRenderer(width, height)
    rnd.scene.set_background(bg)
    mat = o3d.visualization.rendering.MaterialRecord()
    mat.shader = "defaultLit"
    mat.base_color = [*base_color, 1.0]
    if albedo_path is not None and os.path.exists(albedo_path):
        mat.base_color = [1.0, 1.0, 1.0, 1.0]
        mat.albedo_img = o3d.io.read_image(albedo_path)
    rnd.scene.add_geometry("mesh", mesh, mat)

    if wireframe:
        ls = o3d.geometry.LineSet.create_from_triangle_mesh(mesh)
        ls.paint_uniform_color([0.15, 0.15, 0.17])
        wmat = o3d.visualization.rendering.MaterialRecord()
        wmat.shader = "unlitLine"
        wmat.line_width = 1.0
        rnd.scene.add_geometry("wire", ls, wmat)

    rnd.scene.scene.set_sun_light([0.3, -0.5, -0.8], [1.0, 1.0, 1.0], 75000)
    rnd.scene.scene.enable_sun_light(True)

    eye = np.asarray(center) + _VIEW_DIR / np.linalg.norm(_VIEW_DIR) * radius * 2.3
    rnd.setup_camera(fov, center, eye.tolist(), [0.0, 0.0, 1.0])
    img = np.asarray(rnd.render_to_image()).copy()
    del rnd

    # Key the uniform corner background to pure white for clean compositing.
    corner = img[1, 1].astype(int)
    near = np.abs(img.astype(int) - corner).max(2) <= 10
    img[near] = 255
    return img


# ── Pipeline-stages figure ───────────────────────────────────────────────────

# (label, relative path under the object dir, render style)
_STAGES = [
    ("raw",        "raw_mesh/{obj}.obj",                  "texture"),
    ("coacd",      "processed_data/mesh/coacd.obj",       "components"),
    ("manifold",   "processed_data/mesh/manifold.obj",    "wire"),
    ("simplified", "processed_data/mesh/simplified.obj",  "wire"),
]


def _find_texture(base, obj_name):
    """Locate a raw-mesh albedo PNG, trying the common naming conventions."""
    raw_dir = os.path.join(base, "raw_mesh")
    for cand in (f"{obj_name}_0.png", "material_0.png"):
        p = os.path.join(raw_dir, cand)
        if os.path.exists(p):
            return p
    pngs = [f for f in os.listdir(raw_dir) if f.lower().endswith(".png")] \
        if os.path.isdir(raw_dir) else []
    return os.path.join(raw_dir, pngs[0]) if pngs else None


def _font(size):
    from PIL import ImageFont
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_pipeline_figure(obj_name, out_path, root=None, tile=560, pad=18):
    """Render an object's available pipeline stages into one labeled PNG strip.

    Missing stages (e.g. an intermediate that was cleaned up) are skipped. All
    stages share one camera framed on the raw mesh so they are directly
    comparable. Returns the list of stage labels drawn.
    """
    o3d = _o3d()
    from PIL import Image, ImageDraw

    base = obj_dir(obj_name) if root is None else os.path.join(root, obj_name)

    texture = _find_texture(base, obj_name)

    # Shared framing from the first stage mesh that exists.
    center = radius = None
    tiles, labels = [], []
    for label, rel, style in _STAGES:
        path = os.path.join(base, rel.format(obj=obj_name))
        if not os.path.exists(path):
            continue
        mesh = _load(o3d, path)
        if center is None:
            center, radius = _bounds(mesh)
        kw = dict(base_color=(0.78, 0.80, 0.83))
        if style == "components":
            mesh = _paint_components(o3d, mesh)
            kw = dict(base_color=(1.0, 1.0, 1.0))
        elif style == "wire":
            kw["wireframe"] = True
        elif style == "texture" and texture is not None:
            kw["albedo_path"] = texture
        nfaces = len(mesh.triangles)
        img = render_mesh(mesh, tile, tile, center=center, radius=radius, **kw)
        tiles.append(img)
        labels.append(f"{label}  ({nfaces//1000}k tris)" if nfaces >= 1000
                      else f"{label}  ({nfaces} tris)")

    if not tiles:
        raise FileNotFoundError(f"render: no stage meshes found for {obj_name}")

    n = len(tiles)
    label_h = 40
    big, small = _font(26), _font(22)
    strip = Image.new("RGB", (n * tile + (n + 1) * pad, tile + 2 * pad + label_h),
                      (255, 255, 255))
    draw = ImageDraw.Draw(strip)
    for i, (img, label) in enumerate(zip(tiles, labels)):
        x = pad + i * (tile + pad)
        strip.paste(Image.fromarray(img), (x, pad))
        draw.text((x + 10, tile + pad + 6), f"{i+1}. {label}", font=small,
                  fill=(20, 20, 20))
        if i + 1 < n:
            cx, cy = x + tile + pad // 2, tile // 2 + pad
            draw.line([(cx - 16, cy), (cx + 8, cy)], fill=(150, 150, 150), width=5)
            draw.polygon([(cx + 6, cy - 11), (cx + 6, cy + 11), (cx + 24, cy)],
                         fill=(150, 150, 150))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    strip.save(out_path)
    return labels


# ── Turntable ────────────────────────────────────────────────────────────────

def turntable_frames(mesh_or_path, n_frames=36, width=540, height=540,
                     base_color=(0.78, 0.80, 0.83)):
    """Yield ``n_frames`` renders of the mesh spun a full turn about +z."""
    o3d = _o3d()
    mesh = mesh_or_path
    if isinstance(mesh_or_path, str):
        mesh = _load(o3d, mesh_or_path)
    center, radius = _bounds(mesh)
    frames = []
    for k in range(n_frames):
        ang = 2 * np.pi * k / n_frames
        c, s = np.cos(ang), np.sin(ang)
        Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
        spun = o3d.geometry.TriangleMesh(mesh)
        spun.rotate(Rz, center=center)
        frames.append(render_mesh(spun, width, height, center=center,
                                  radius=radius, base_color=base_color))
    return frames


def save_turntable_gif(mesh_or_path, out_path, n_frames=36, duration=60, **kw):
    """Render a turntable and save it as an animated GIF."""
    from PIL import Image
    frames = turntable_frames(mesh_or_path, n_frames=n_frames, **kw)
    imgs = [Image.fromarray(f) for f in frames]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    imgs[0].save(out_path, save_all=True, append_images=imgs[1:], loop=0,
                 duration=duration)
    return out_path


def main(argv=None):
    p = argparse.ArgumentParser(prog="object_processing.render")
    sub = p.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("pipeline", help="render pipeline-stage strip for an object")
    pf.add_argument("object")
    pf.add_argument("--out", required=True)
    pf.add_argument("--tile", type=int, default=560)

    tt = sub.add_parser("turntable", help="render a spinning GIF of a stage mesh")
    tt.add_argument("object")
    tt.add_argument("--out", required=True)
    tt.add_argument("--stage", default="simplified",
                    help="mesh stage to spin (default: simplified)")
    tt.add_argument("--frames", type=int, default=36)

    a = p.parse_args(argv)
    if a.cmd == "pipeline":
        labels = render_pipeline_figure(a.object, a.out, tile=a.tile)
        print(f"wrote {a.out}  ({' -> '.join(labels)})")
    elif a.cmd == "turntable":
        rel = {
            "raw": "raw_mesh/{obj}.obj",
            "coacd": "processed_data/mesh/coacd.obj",
            "manifold": "processed_data/mesh/manifold.obj",
            "simplified": "processed_data/mesh/simplified.obj",
        }[a.stage]
        path = os.path.join(obj_dir(a.object), rel.format(obj=a.object))
        save_turntable_gif(path, a.out, n_frames=a.frames)
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
