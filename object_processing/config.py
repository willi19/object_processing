"""Resolution of the per-object data root.

Every stage of the pipeline reads/writes under a single object root, laid out
per object as::

    {OBJECT_ROOT}/{obj_name}/
        raw_mesh/{obj_name}.obj            # input
        processed_data/mesh/{raw,coacd,manifold,simplified}.obj
        processed_data/urdf/{coacd.urdf,coacd.xml,meshes/}
        processed_data/info/{simplified.json, tabletop/*.npy}
        scene/{table,wall,shelf,box,float,packed}/*.json

The root is resolved in this order:

1. ``OBJECT_ROOT`` environment variable, if set.
2. ``DEFAULT_OBJECT_ROOT`` below.

This replaces the scattered ``autodex.utils.path.obj_path`` /
``rsslib.path.obj_path`` constants so this package has no dependency on AutoDex.
"""

import os

# Active object root used by the live AutoDex pipeline and the viewers.
# Override per-machine with the OBJECT_ROOT environment variable.
DEFAULT_OBJECT_ROOT = os.path.join(
    os.path.expanduser("~"), "shared_data", "AutoDex", "object", "paradex"
)


def object_root() -> str:
    """Return the absolute path to the per-object data root."""
    return os.path.abspath(os.environ.get("OBJECT_ROOT", DEFAULT_OBJECT_ROOT))


def obj_dir(obj_name: str) -> str:
    """Return the directory for a single object: ``{OBJECT_ROOT}/{obj_name}``."""
    return os.path.join(object_root(), obj_name)


# Convenience constant for callers that prefer a value over a function.
# Note: this is evaluated at import time; use object_root() if OBJECT_ROOT may
# change after import.
OBJECT_ROOT = object_root()
