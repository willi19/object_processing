"""Per-object geometric info: oriented bounding box, mass, point cloud."""

import json
import os

import numpy as np
import trimesh

from object_processing.tools import require_output


def basic_info(input_path, output_path):
    """Compute and write OBB + mass properties for a mesh as JSON.

    Output fields: ``gravity_center`` (center of mass), ``obb`` (oriented
    bounding-box extents), ``obb_transform`` (4x4 OBB frame), ``scale``,
    ``density``, ``mass``. Consumed by scene generation and the viewers.
    """
    mesh = trimesh.load(input_path, force="mesh")
    obb = mesh.bounding_box_oriented.primitive

    info = {
        "gravity_center": mesh.center_mass.tolist(),
        "obb": obb.extents.tolist(),
        "obb_transform": obb.transform.tolist(),
        "scale": 1.0,
        "density": mesh.density,
        "mass": mesh.mass,
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(info, f, indent=1)
    require_output(output_path, "basic_info")


def complete_pc(input_path, output_path, point_num=4096):
    """Sample ``point_num`` surface points and save them as a float16 ``.npy``."""
    mesh = trimesh.load(input_path, force="mesh")
    pc, _ = trimesh.sample.sample_surface(mesh, point_num)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    np.save(output_path, pc.astype(np.float16))
    require_output(output_path, "complete_pc")
