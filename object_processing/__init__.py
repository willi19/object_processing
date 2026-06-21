"""Object & mesh processing pipeline.

Canonical home for the mesh/object data-preparation pipeline used across the
AutoDex project: format conversion, convex decomposition, manifold/simplify,
URDF/MJCF export, stable tabletop-pose generation, symmetry, and visualization.

The per-object data root is resolved by :mod:`object_processing.config`.
"""

from object_processing.config import object_root, obj_dir, OBJECT_ROOT

__all__ = ["object_root", "obj_dir", "OBJECT_ROOT"]
