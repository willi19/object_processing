#!/usr/bin/env python3
"""
Generate thumbnail images for each object mesh.

Usage:
    python generate_thumbnails.py <input_dir> <output_dir>

Example:
    python generate_thumbnails.py /path/to/paradex output

Generates output/objects/{name}/thumb.png for each object.
Requires: trimesh, pyrender, Pillow
Set PYOPENGL_PLATFORM=egl for headless rendering.
"""

import argparse
import os
import sys

os.environ["PYOPENGL_PLATFORM"] = "egl"

import numpy as np
import trimesh
import pyrender
from PIL import Image


def find_obj_file(obj_dir):
    """Find the .obj file inside raw_mesh/ subdirectory."""
    raw_mesh_dir = os.path.join(obj_dir, "raw_mesh")
    if not os.path.isdir(raw_mesh_dir):
        return None
    for f in os.listdir(raw_mesh_dir):
        if f.lower().endswith(".obj") and "remeshed" not in f.lower():
            return os.path.join(raw_mesh_dir, f)
    for f in os.listdir(raw_mesh_dir):
        if f.lower().endswith(".obj"):
            return os.path.join(raw_mesh_dir, f)
    return None


# Rec. 709 luma weights, used to decide whether an object is "light".
_LUMA = np.array([0.2126, 0.7152, 0.0722])


def render_thumbnail(obj_file, out_path, renderer, size=256, light_threshold=185):
    """Render a mesh to a thumbnail PNG using a shared renderer.

    Renders on a transparent background, measures the object's mean brightness,
    then composites onto white — or black for objects that are themselves light
    (so a white object doesn't vanish into a white page). Returns the background
    name chosen ("white" / "black").
    """
    scene = pyrender.Scene(bg_color=[0, 0, 0, 0])  # transparent → real alpha mask

    mesh = trimesh.load(obj_file, force="mesh")

    # Center and normalize
    mesh.vertices -= mesh.centroid
    scale = mesh.extents.max()
    if scale > 0:
        mesh.vertices /= scale

    pr_mesh = pyrender.Mesh.from_trimesh(mesh)
    scene.add(pr_mesh)

    # Camera looking at the object
    camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0)
    cam_pose = np.eye(4)
    cam_pose[2, 3] = 2.0  # distance
    cam_pose[1, 3] = 0.3  # slightly above
    scene.add(camera, pose=cam_pose)

    # Lights
    light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.0)
    scene.add(light, pose=cam_pose)

    ambient = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=1.0)
    amb_pose = np.eye(4)
    amb_pose[:3, :3] = trimesh.transformations.rotation_matrix(
        np.pi / 2, [1, 0, 0]
    )[:3, :3]
    scene.add(ambient, pose=amb_pose)

    color, _ = renderer.render(scene, flags=pyrender.RenderFlags.RGBA)
    rgba = np.asarray(color)

    # Mean luminance over the object's (mostly-opaque) pixels.
    mask = rgba[..., 3] > 8
    obj_lum = float((rgba[mask][:, :3] @ _LUMA).mean()) if mask.any() else 0.0
    bg = (0, 0, 0, 255) if obj_lum >= light_threshold else (255, 255, 255, 255)

    obj_img = Image.fromarray(rgba, "RGBA")
    bg_img = Image.new("RGBA", obj_img.size, bg)
    Image.alpha_composite(bg_img, obj_img).convert("RGB").save(out_path)
    return "black" if bg[0] == 0 else "white"


def main():
    parser = argparse.ArgumentParser(description="Generate thumbnails for object meshes")
    parser.add_argument("input_dir", help="Directory containing object folders")
    parser.add_argument("output_dir", help="Output directory (same as convert_objects output)")
    parser.add_argument("--size", type=int, default=256, help="Thumbnail size in pixels")
    parser.add_argument("--light-threshold", type=int, default=185,
                        help="Object mean-luminance (0-255) at/above which a black "
                             "background is used instead of white")
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir
    size = args.size

    if not os.path.isdir(input_dir):
        print(f"Error: {input_dir} not found")
        sys.exit(1)

    # Create a single shared renderer
    renderer = pyrender.OffscreenRenderer(size, size)

    items = sorted(os.listdir(input_dir))
    total = 0
    errors = 0

    for name in items:
        obj_dir = os.path.join(input_dir, name)
        if not os.path.isdir(obj_dir):
            continue

        obj_file = find_obj_file(obj_dir)
        if obj_file is None:
            continue

        out_dir = os.path.join(output_dir, "objects", name)
        os.makedirs(out_dir, exist_ok=True)
        thumb_path = os.path.join(out_dir, "thumb.png")

        try:
            bg = render_thumbnail(obj_file, thumb_path, renderer, size,
                                  args.light_threshold)
            print(f"  OK   {name}  (bg: {bg})")
            total += 1
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            errors += 1

    renderer.delete()
    print(f"\nDone: {total} thumbnails generated, {errors} errors")


if __name__ == "__main__":
    main()
