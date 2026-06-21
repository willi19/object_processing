"""Mesh/object processing pipeline stages, as plain callable functions.

Each stage takes explicit input/output paths and keyword arguments, performs one
processing step, validates its output, and raises on failure. Compose them via
:mod:`object_processing.cli` or call them directly from other code.

Stage order for a full object:

    change_format (raw.obj)
      -> convex_decompose (coacd.obj + urdf/meshes/)
      -> export_urdf / export_mjcf
      -> manifold (manifold.obj)
      -> simplify (simplified.ply) -> change_format (simplified.obj)
      -> basic_info (info/simplified.json)
      -> generate_tabletop_poses (info/tabletop/*.npy)
"""

from object_processing.pipeline.convert import change_format, normalize
from object_processing.pipeline.decompose import convex_decompose, manifold
from object_processing.pipeline.simplify import simplify
from object_processing.pipeline.export import export_urdf, export_mjcf
from object_processing.pipeline.info import basic_info, complete_pc
from object_processing.pipeline.tabletop import generate_tabletop_poses
from object_processing.pipeline.symmetry import (
    detect_symmetry,
    compute_symmetry,
    load_symmetry,
)

__all__ = [
    "change_format",
    "normalize",
    "convex_decompose",
    "manifold",
    "simplify",
    "export_urdf",
    "export_mjcf",
    "basic_info",
    "complete_pc",
    "generate_tabletop_poses",
    "detect_symmetry",
    "compute_symmetry",
    "load_symmetry",
]
