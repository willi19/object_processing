"""Resolution of the per-object data root.

Every stage of the pipeline reads/writes under a single object root, laid out
per object as::

    {OBJECT_ROOT}/{obj_name}/
        raw_mesh/{obj_name}.obj            # input (any supported format; see find_raw_mesh)
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


# Raw-input mesh formats trimesh can load directly, in preference order.
SUPPORTED_MESH_EXTS = (".obj", ".glb", ".gltf", ".ply", ".stl", ".dae", ".off")


def find_raw_mesh(obj_name: str, root: str = None) -> str:
    """Locate an object's raw input mesh under ``raw_mesh/``, format-agnostically.

    The input is not required to be named ``{obj_name}.obj`` — IKEA and other
    sources may ship ``.glb``/``.dae``/etc. Resolution order:

    1. ``{obj_name}.<ext>`` for ext in :data:`SUPPORTED_MESH_EXTS` (preferred);
    2. otherwise the single supported mesh in the directory.

    ``*_remeshed.*`` variants are ignored. Raises ``FileNotFoundError`` if the
    directory is missing, holds no supported mesh, or is ambiguous (several
    candidates, none named ``{obj_name}``) — never silently guesses.
    """
    base = obj_dir(obj_name) if root is None else os.path.join(root, obj_name)
    raw_dir = os.path.join(base, "raw_mesh")
    if not os.path.isdir(raw_dir):
        raise FileNotFoundError(f"{obj_name}: no raw_mesh/ directory at {raw_dir}")

    candidates = [
        f for f in os.listdir(raw_dir)
        if os.path.splitext(f)[1].lower() in SUPPORTED_MESH_EXTS
        and not os.path.splitext(f)[0].endswith("_remeshed")
    ]

    # 1. Preferred: exact name match, by extension priority.
    for ext in SUPPORTED_MESH_EXTS:
        if f"{obj_name}{ext}" in candidates:
            return os.path.join(raw_dir, f"{obj_name}{ext}")

    # 2. Fall back to the only supported mesh present.
    if len(candidates) == 1:
        return os.path.join(raw_dir, candidates[0])

    if not candidates:
        raise FileNotFoundError(
            f"{obj_name}: no supported raw mesh in {raw_dir} "
            f"(supported: {', '.join(SUPPORTED_MESH_EXTS)})"
        )
    raise FileNotFoundError(
        f"{obj_name}: ambiguous raw mesh in {raw_dir}: {sorted(candidates)}. "
        f"Rename the primary one to {obj_name}.obj"
    )


# Convenience constant for callers that prefer a value over a function.
# Note: this is evaluated at import time; use object_root() if OBJECT_ROOT may
# change after import.
OBJECT_ROOT = object_root()
