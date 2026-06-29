"""Headless Open3D rendering utilities for the object pipeline.

Renders processed meshes to PNG images with no display, using Open3D's
OffscreenRenderer (the same GPU renderer AutoDex uses for its turntable / scene
figures). Two things it produces:

- ``render_pipeline_figure`` — a labeled side-by-side strip of one object's
  pipeline stages (raw -> coacd -> manifold -> simplified), for docs/README.
- ``turntable_frames`` / ``save_turntable_gif`` — a spinning view of a mesh.

Open3D is an optional, heavy dependency and is imported lazily inside the
functions, so importing this module (or the rest of ``object_processing``) never
requires it. The runnable CLI lives in ``src/render.py``.
"""

import glob
import json
import os

import numpy as np

from object_processing.utils.config import obj_dir

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


def _coacd_colored(o3d, pieces_dir):
    """Build the convex decomposition colored per piece, from the individual
    ``convex_piece_*.obj`` files (the ground-truth pieces). Returns ``None`` if
    the pieces directory is missing so the caller can fall back."""
    import glob
    files = sorted(glob.glob(os.path.join(pieces_dir, "*.obj")))
    if not files:
        return None
    combined = o3d.geometry.TriangleMesh()
    for i, f in enumerate(files):
        piece = _load(o3d, f)
        piece.paint_uniform_color(list(_PALETTE[i % len(_PALETTE)]))
        combined += piece
    combined.compute_vertex_normals()
    return combined


def _paint_components(o3d, mesh):
    """Fallback: color each connected component of a merged mesh."""
    labels = np.asarray(mesh.cluster_connected_triangles()[0])
    if labels.size == 0:
        return mesh
    tri = np.asarray(mesh.triangles)
    vcol = np.ones((len(mesh.vertices), 3))
    for lbl in np.unique(labels):
        verts = np.unique(tri[labels == lbl])
        vcol[verts] = _PALETTE[int(lbl) % len(_PALETTE)]
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
            pieces = os.path.join(base, "processed_data", "urdf", "meshes")
            colored = _coacd_colored(o3d, pieces)
            mesh = colored if colored is not None else _paint_components(o3d, mesh)
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


# ── Tabletop poses ───────────────────────────────────────────────────────────

def _lit(o3d, color):
    m = o3d.visualization.rendering.MaterialRecord()
    m.shader = "defaultLit"
    m.base_color = [*color, 1.0]
    return m


def _line_material(o3d, width=3.0):
    m = o3d.visualization.rendering.MaterialRecord()
    m.shader = "unlitLine"
    m.line_width = width
    return m


def _obb_lineset(o3d, extents, transform, color):
    """LineSet of the 12 oriented-bounding-box edges."""
    hx, hy, hz = np.asarray(extents) / 2
    corners = np.array([
        [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
        [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz],
    ])
    T = np.asarray(transform)
    corners = corners @ T[:3, :3].T + T[:3, 3]
    edges = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]]
    ls = o3d.geometry.LineSet()
    ls.points = o3d.utility.Vector3dVector(corners)
    ls.lines = o3d.utility.Vector2iVector(np.array(edges))
    ls.paint_uniform_color(list(color))
    return ls


def render_tabletop_figure(obj_name, out_path, root=None, width=1200, height=820):
    """Render the simplified mesh placed in each of its stable tabletop poses,
    laid out on a grid above a ground plane. Returns the number of poses drawn."""
    o3d = _o3d()
    base = obj_dir(obj_name) if root is None else os.path.join(root, obj_name)
    mesh = _load(o3d, os.path.join(base, "processed_data", "mesh", "simplified.obj"))
    pose_files = sorted(glob.glob(
        os.path.join(base, "processed_data", "info", "tabletop", "*.npy")))
    if not pose_files:
        raise FileNotFoundError(f"render: no tabletop poses for {obj_name}")
    poses = [np.load(p) for p in pose_files]

    diag = float(np.linalg.norm(mesh.get_axis_aligned_bounding_box().get_extent()))
    spacing = diag * 1.25
    n = len(poses)
    cols = int(np.ceil(np.sqrt(n)))
    rows = int(np.ceil(n / cols))

    rnd = o3d.visualization.rendering.OffscreenRenderer(width, height)
    rnd.scene.set_background([1.0, 1.0, 1.0, 1.0])
    rnd.scene.scene.set_sun_light([0.3, -0.5, -0.8], [1.0, 1.0, 1.0], 75000)
    rnd.scene.scene.enable_sun_light(True)
    obj_mat = _lit(o3d, (0.86, 0.74, 0.55))  # warm tan, stands out from the floor

    for k, P in enumerate(poses):
        dx = ((k % cols) - (cols - 1) / 2) * spacing
        dy = (k // cols - (rows - 1) / 2) * spacing
        T = np.eye(4)
        T[:3, 3] = [dx, dy, 0]
        m = o3d.geometry.TriangleMesh(mesh)
        m.transform(T @ np.asarray(P))
        m.compute_vertex_normals()
        rnd.scene.add_geometry(f"pose_{k}", m, obj_mat)

    # Ground plane spanning the grid.
    gw, gd = cols * spacing + diag, rows * spacing + diag
    ground = o3d.geometry.TriangleMesh.create_box(gw, gd, diag * 0.02)
    ground.translate([-gw / 2, -gd / 2, -diag * 0.02])
    ground.compute_vertex_normals()
    rnd.scene.add_geometry("ground", ground, _lit(o3d, (0.92, 0.92, 0.94)))

    center = [0.0, 0.0, diag * 0.25]
    span = max(gw, gd)
    eye = np.array(center) + np.array([0.35, -1.0, 0.6]) / np.linalg.norm(
        [0.35, -1.0, 0.6]) * span * 0.85
    rnd.setup_camera(50.0, center, eye.tolist(), [0.0, 0.0, 1.0])
    img = np.asarray(rnd.render_to_image())
    del rnd

    from PIL import Image
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    Image.fromarray(img).save(out_path)
    return n


def _add_textured(o3d, rnd, base, obj_name, P):
    """Add the object's own textured display mesh (raw_mesh/<name>.obj) to the
    scene, posed by 4x4 ``P``. Returns the stacked posed vertices (Nx3) so the
    caller can frame the camera. Mirrors the thumbnail renderer: per-vertex-color
    meshes (apple/banana) load via trimesh; everything else via
    read_triangle_model so mtl Kd + albedo textures survive."""
    import trimesh
    raw_dir = os.path.join(base, "raw_mesh")
    obj_path = os.path.join(raw_dir, f"{obj_name}.obj")
    if not os.path.exists(obj_path):
        cands = [f for f in os.listdir(raw_dir) if f.lower().endswith(".obj")] \
            if os.path.isdir(raw_dir) else []
        if not cands:
            raise FileNotFoundError(f"render: no .obj in {raw_dir}")
        obj_path = os.path.join(raw_dir, cands[0])

    pts = []
    tmesh = trimesh.load(obj_path, force="mesh")
    has_vc = getattr(tmesh.visual, "kind", None) == "vertex"
    if not has_vc:
        model = o3d.io.read_triangle_model(obj_path)
        for i, mi in enumerate(model.meshes):
            g = mi.mesh
            g.transform(P)
            g.compute_vertex_normals()
            mat = model.materials[mi.material_idx]
            # A dim mtl Kd would multiply the albedo down to gray; show textured
            # surfaces full-bright, but keep the Kd color when there's no texture.
            if getattr(mat, "albedo_img", None) is not None:
                mat.base_color = [1.0, 1.0, 1.0, 1.0]
            rnd.scene.add_geometry(f"mesh_{i}", g, mat)
            pts.append(np.asarray(g.vertices))
    else:
        g = o3d.geometry.TriangleMesh(
            o3d.utility.Vector3dVector(np.asarray(tmesh.vertices, float)),
            o3d.utility.Vector3iVector(np.asarray(tmesh.faces, np.int32)))
        g.vertex_colors = o3d.utility.Vector3dVector(
            np.asarray(tmesh.visual.vertex_colors)[:, :3] / 255.0)
        g.transform(P)
        g.compute_vertex_normals()
        mat = o3d.visualization.rendering.MaterialRecord()
        mat.shader = "defaultLit"
        mat.base_color = [1.0, 1.0, 1.0, 1.0]
        rnd.scene.add_geometry("mesh", g, mat)
        pts.append(np.asarray(g.vertices))
    return np.vstack(pts)


def render_overlays_figure(obj_name, out_path, root=None, width=820, height=820):
    """Render the textured display mesh in its curated 'teaser' tabletop pose,
    with its oriented bounding box (blue) and rotational symmetry axes
    (yellow/green/blue) overlaid. Overlays are transformed into the posed frame
    so they stay aligned with the standing mesh."""
    from .poses import teaser_pose
    o3d = _o3d()
    base = obj_dir(obj_name) if root is None else os.path.join(root, obj_name)
    info_dir = os.path.join(base, "processed_data", "info")

    # Teaser resting pose (object -> table); identity if the object has none.
    Pt = teaser_pose(obj_name, base)
    P = np.asarray(Pt) if Pt is not None else np.eye(4)

    rnd = o3d.visualization.rendering.OffscreenRenderer(width, height)
    rnd.scene.set_background([1.0, 1.0, 1.0, 1.0])
    # Image-based + sun fill, matching the thumbnails, so PBR textures aren't flat
    # and dark-colored objects read as product-photo gray rather than near-black.
    rnd.scene.set_lighting(rnd.scene.LightingProfile.SOFT_SHADOWS, [0.3, -0.5, -0.8])
    rnd.scene.scene.set_indirect_light_intensity(75000)
    rnd.scene.scene.set_sun_light([0.3, -0.5, -0.8], [1.0, 1.0, 1.0], 100000)

    verts = _add_textured(o3d, rnd, base, obj_name, P)
    mn, mx = verts.min(0), verts.max(0)
    center = (mn + mx) / 2
    radius = max(float(np.linalg.norm(mx - mn) / 2), 1e-6)

    simp = os.path.join(info_dir, "simplified.json")
    if os.path.exists(simp):
        s = json.load(open(simp))
        obb = _obb_lineset(o3d, s["obb"], s["obb_transform"], (0.20, 0.45, 1.0))
        obb.transform(P)
        rnd.scene.add_geometry("obb", obb, _line_material(o3d, 3.0))

    sym_path = os.path.join(info_dir, "symmetry.json")
    axis_colors = [(1.0, 0.82, 0.1), (0.2, 0.85, 0.4), (0.36, 0.62, 0.95)]
    if os.path.exists(sym_path):
        sym = json.load(open(sym_path))
        ctr = np.asarray(sym["center"])
        L = sym["scale"] * 0.6
        for i, a in enumerate(sym.get("axes", [])):
            d = np.asarray(a["axis"])
            ls = o3d.geometry.LineSet()
            ls.points = o3d.utility.Vector3dVector([ctr - d * L, ctr + d * L])
            ls.lines = o3d.utility.Vector2iVector([[0, 1]])
            ls.paint_uniform_color(list(axis_colors[i % len(axis_colors)]))
            ls.transform(P)
            rnd.scene.add_geometry(f"axis_{i}", ls, _line_material(o3d, 5.0))

    eye = np.asarray(center) + _VIEW_DIR / np.linalg.norm(_VIEW_DIR) * radius * 2.3
    rnd.setup_camera(55.0, center.tolist(), eye.tolist(), [0.0, 0.0, 1.0])
    img = np.asarray(rnd.render_to_image())
    del rnd

    from PIL import Image
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    Image.fromarray(img).save(out_path)
    return out_path


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
