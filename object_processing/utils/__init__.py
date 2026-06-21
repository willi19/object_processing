"""Shared infrastructure for the pipeline.

- :mod:`config`   — per-object data root resolution (``OBJECT_ROOT``)
- :mod:`tools`    — external tool (CoACD / ACVD) resolution + subprocess helpers
- :mod:`rotation` — numpy quaternion helpers used by stable-pose generation
"""

from object_processing.utils.config import object_root, obj_dir, OBJECT_ROOT

__all__ = ["object_root", "obj_dir", "OBJECT_ROOT"]
