#!/usr/bin/env python3
"""Bake vertex colors from a colored scan onto a clean UV-mapped mesh.

The clean mesh (target) keeps its geometry and UV layout; for every texel we
find the corresponding surface point, look up the nearest point on the aligned
scan (source) and write its interpolated color.

    python bake_texture_from_scan.py TARGET.obj SOURCE.ply OUT_DIR [options]

The two meshes do not need to share a coordinate frame: the source is aligned
onto the target by matching principal axes and extents (both are assumed to be
single connected objects), optionally refined with ICP.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree


# --------------------------------------------------------------------------
# alignment
# --------------------------------------------------------------------------
def principal_frame(points):
    """Return (center, R) where R's rows are the principal axes, longest first."""
    center = points.mean(axis=0)
    X = points - center
    if len(X) > 200_000:
        X = X[:: len(X) // 200_000 + 1]
    _, _, vt = np.linalg.svd(X, full_matrices=False)
    if np.linalg.det(vt) < 0:
        vt[2] *= -1
    return center, vt


def axis_metrics(points, center, axis):
    """Axial extent (with mid point) and robust radius around `axis`."""
    t = (points - center) @ axis
    radial = np.linalg.norm((points - center) - np.outer(t, axis), axis=1)
    return t.min(), t.max(), np.percentile(radial, 95)


def align_source(source, target, flip=False, yaw_deg=0.0, icp=True):
    """Return the 4x4 transform mapping source coordinates onto the target."""
    sp = np.asarray(source.vertices)
    tp = np.asarray(target.vertices)

    s_center, s_R = principal_frame(sp)
    t_center, t_R = principal_frame(tp)
    s_lo, s_hi, s_rad = axis_metrics(sp, s_center, s_R[0])
    t_lo, t_hi, t_rad = axis_metrics(tp, t_center, t_R[0])

    # source -> canonical: long axis to +Z, axial mid point to the origin
    to_canon = np.eye(4)
    to_canon[:3, :3] = s_R
    to_canon[:3, 3] = -s_R @ s_center
    to_canon[2, 3] -= (s_lo + s_hi) / 2.0

    # anisotropic scale: match axial extent and radius separately, so a scan
    # that is a few percent off in only one direction still lands correctly
    scale = np.diag([
        t_rad / s_rad, t_rad / s_rad, (t_hi - t_lo) / (s_hi - s_lo), 1.0
    ])

    adjust = np.eye(4)
    if flip:  # 180 deg about X: swap which end of the axis is which
        adjust[:3, :3] = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], float)
    if yaw_deg:
        a = np.radians(yaw_deg)
        rot = np.array([[np.cos(a), -np.sin(a), 0],
                        [np.sin(a), np.cos(a), 0],
                        [0, 0, 1]], float)
        adjust[:3, :3] = rot @ adjust[:3, :3]

    # canonical -> target frame
    from_canon = np.eye(4)
    from_canon[:3, :3] = t_R.T
    from_canon[:3, 3] = t_center + t_R.T @ np.array([0, 0, (t_lo + t_hi) / 2.0])

    T = from_canon @ adjust @ scale @ to_canon

    if icp:
        probe = trimesh.sample.sample_surface(source, 20000)[0]
        probe = trimesh.transform_points(probe, T)
        T_icp, _, cost = trimesh.registration.icp(
            probe, target, initial=np.eye(4), max_iterations=60, scale=False
        )
        print(f"  ICP residual: {cost * 1000:.3f} mm")
        T = T_icp @ T
    return T


# --------------------------------------------------------------------------
# baking
# --------------------------------------------------------------------------
def rasterize_uv(uv, faces, size, pad=1.0):
    """Rasterize UV triangles.

    Returns (pixel_index, face_index, barycentric) for every covered texel.
    `pad` dilates each triangle by that many pixels so texels straddling a
    UV edge still get a sample (avoids one-pixel seam gaps).
    """
    px = np.stack([uv[:, 0] * size, (1.0 - uv[:, 1]) * size], axis=1)
    tri = px[faces]  # (F, 3, 2)

    pix_idx, face_idx, bary = [], [], []
    lo = np.floor(tri.min(axis=1) - pad).astype(int)
    hi = np.ceil(tri.max(axis=1) + pad).astype(int)
    np.clip(lo, 0, size - 1, out=lo)
    np.clip(hi, 0, size - 1, out=hi)

    for f in range(len(faces)):
        x0, y0 = lo[f]
        x1, y1 = hi[f]
        if x1 < x0 or y1 < y0:
            continue
        xs = np.arange(x0, x1 + 1) + 0.5
        ys = np.arange(y0, y1 + 1) + 0.5
        gx, gy = np.meshgrid(xs, ys)
        pts = np.stack([gx.ravel(), gy.ravel()], axis=1)

        a, b, c = tri[f]
        v0, v1, v2 = b - a, c - a, pts - a
        den = v0[0] * v1[1] - v1[0] * v0[1]
        if abs(den) < 1e-12:
            continue
        w1 = (v2[:, 0] * v1[1] - v1[0] * v2[:, 1]) / den
        w2 = (v0[0] * v2[:, 1] - v2[:, 0] * v0[1]) / den
        w0 = 1.0 - w1 - w2
        w = np.stack([w0, w1, w2], axis=1)

        # slack in barycentric units ~= pad pixels
        slack = pad / max(np.abs(tri[f] - tri[f].mean(axis=0)).max(), 1e-9)
        inside = (w >= -slack).all(axis=1)
        if not inside.any():
            continue
        sel = pts[inside]
        col = sel[:, 0].astype(int)
        row = sel[:, 1].astype(int)
        pix_idx.append(row * size + col)
        face_idx.append(np.full(inside.sum(), f))
        bary.append(np.clip(w[inside], 0.0, 1.0))

    if not pix_idx:
        raise RuntimeError("UV rasterization produced no texels")
    pix = np.concatenate(pix_idx)
    fid = np.concatenate(face_idx)
    bar = np.concatenate(bary)
    bar /= bar.sum(axis=1, keepdims=True)
    # keep one sample per texel (interior samples beat padded ones)
    order = np.lexsort((np.abs(bar - 1.0 / 3).max(axis=1), pix))
    pix, fid, bar = pix[order], fid[order], bar[order]
    keep = np.ones(len(pix), bool)
    keep[1:] = pix[1:] != pix[:-1]
    return pix[keep], fid[keep], bar[keep]


def fill_background(image, mask, background):
    """Nearest-neighbour dilation of baked texels into the unused UV space."""
    _, idx = distance_transform_edt(~mask, return_indices=True)
    filled = image[idx[0], idx[1]]
    far = distance_transform_edt(~mask) > max(image.shape) * 0.05
    filled[far] = background
    return filled


def bake(target, source, size, samples, background):
    uv = np.asarray(target.visual.uv)
    faces = np.asarray(target.faces)
    verts = np.asarray(target.vertices)

    print(f"  rasterizing {len(faces)} faces into {size}x{size}...")
    pix, fid, bar = rasterize_uv(uv, faces, size)
    print(f"  {len(pix)} texels covered ({100 * len(pix) / size ** 2:.1f}% of the map)")

    points = np.einsum("ijk,ij->ik", verts[faces[fid]], bar)

    print(f"  sampling {samples} colored points on the source...")
    sp, _, sc = trimesh.sample.sample_surface(source, samples, sample_color=True)
    sc = np.asarray(sc)[:, :3].astype(np.uint8)

    print("  nearest-point color lookup...")
    tree = cKDTree(np.asarray(sp))
    dist, nn = tree.query(points, workers=-1)
    print(f"  transfer distance: mean {dist.mean() * 1000:.2f} mm, "
          f"p95 {np.percentile(dist, 95) * 1000:.2f} mm, max {dist.max() * 1000:.2f} mm")

    image = np.full((size, size, 3), background, np.uint8)
    mask = np.zeros(size * size, bool)
    flat = image.reshape(-1, 3)
    flat[pix] = sc[nn]
    mask[pix] = True
    return fill_background(flat.reshape(size, size, 3), mask.reshape(size, size),
                           background)


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="clean mesh with UVs (.obj)")
    ap.add_argument("source", help="colored scan (.ply with vertex colors)")
    ap.add_argument("out_dir", help="directory for texture.png / textured.obj / .glb")
    ap.add_argument("--size", type=int, default=2048, help="texture resolution")
    ap.add_argument("--samples", type=int, default=4_000_000,
                    help="surface samples drawn from the source")
    ap.add_argument("--yaw", type=float, default=0.0,
                    help="extra rotation (deg) of the source about the object axis")
    ap.add_argument("--flip", action="store_true",
                    help="flip the source end-for-end along its long axis")
    ap.add_argument("--no-icp", action="store_true", help="skip ICP refinement")
    ap.add_argument("--background", default="128,128,128",
                    help="fill color for unused UV space, 'r,g,b'")
    ap.add_argument("--name", default="texture", help="base name of the outputs")
    args = ap.parse_args()

    background = np.array([int(v) for v in args.background.split(",")], np.uint8)

    target = trimesh.load(args.target, process=False)
    source = trimesh.load(args.source, process=False)
    if not isinstance(target, trimesh.Trimesh) or not isinstance(source, trimesh.Trimesh):
        sys.exit("both inputs must be single triangle meshes")
    if getattr(target.visual, "uv", None) is None:
        sys.exit(f"{args.target} has no UV coordinates - unwrap it first")
    if source.visual.kind not in ("vertex", "face", "texture"):
        sys.exit(f"{args.source} carries no color ({source.visual.kind})")

    print(f"target: {len(target.vertices)} verts, extents {np.round(target.extents, 4)}")
    print(f"source: {len(source.vertices)} verts, extents {np.round(source.extents, 4)}")

    print("aligning source onto target...")
    T = align_source(source, target, flip=args.flip, yaw_deg=args.yaw,
                     icp=not args.no_icp)
    source.apply_transform(T)
    print(f"  aligned source extents {np.round(source.extents, 4)}")

    image = bake(target, source, args.size, args.samples, background)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tex_path = out / f"{args.name}.png"
    Image.fromarray(image).save(tex_path)
    print(f"wrote {tex_path}")

    textured = target.copy()
    textured.visual = trimesh.visual.TextureVisuals(
        uv=np.asarray(target.visual.uv),
        material=trimesh.visual.material.SimpleMaterial(image=Image.fromarray(image)),
    )
    textured.export(out / f"{args.name}.glb")
    np.savetxt(out / f"{args.name}_transform.txt", T, fmt="%.9f")
    print(f"wrote {out / (args.name + '.glb')} and the source->target transform")


if __name__ == "__main__":
    main()
