"""Mesh format conversion and normalization (trimesh)."""

import os

import numpy as np
import trimesh

from object_processing.utils.tools import require_output


def change_format(input_path, output_path, keep_material=True, delete_input=False):
    """Load ``input_path`` and re-export it to ``output_path``.

    The output format is inferred from the extension (e.g. ``.ply`` -> ``.obj``).
    When ``keep_material`` is False the visual/material data is stripped (useful
    when downstream tools only need geometry).
    """
    mesh = trimesh.load(input_path, force="mesh")
    if not keep_material:
        mesh.visual = trimesh.visual.ColorVisuals()

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    mesh.export(output_path)
    require_output(output_path, "change_format")

    if delete_input and os.path.abspath(input_path) != os.path.abspath(output_path):
        os.remove(input_path)


def normalize(input_path, output_path, length=0.1):
    """Center the mesh at its bounding-box center and scale by ``1/length``.

    Matches the legacy behavior (half-diagonal scale, overridden to a fixed
    ``length`` of 0.1).
    """
    mesh = trimesh.load(input_path, force="mesh")
    verts = np.asarray(mesh.vertices)
    center = (verts.max(axis=0) + verts.min(axis=0)) / 2
    mesh.vertices = (verts - center[None]) / length

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    mesh.export(output_path)
    require_output(output_path, "normalize")
