"""Decimate raw textured meshes for fast visualization (pymeshlab).

Reads  ``{OBJECT_ROOT}/{obj}/raw_mesh/{obj}.obj`` and writes
``{OBJECT_ROOT}/{obj}/raw_mesh_decimated/{obj}.obj`` (+ mtl + textures), using
quadric edge-collapse decimation with texture preservation. Meshes already at or
below the target face count are copied through unchanged.
"""

import os
import re
import shutil

import pymeshlab


def referenced_textures(mtl_path):
    """Return the texture filenames referenced by a ``.mtl`` (map_* entries)."""
    refs = []
    with open(mtl_path) as f:
        for line in f:
            m = re.match(r"\s*(map_[A-Za-z_]+)\s+(.+?)\s*$", line)
            if m:
                refs.append(m.group(2))
    return refs


def decimate(obj_name, in_dir, out_dir, target_faces=50_000):
    """Decimate ``{in_dir}/{obj_name}.obj`` to ``target_faces`` into ``out_dir``.

    Returns the output ``.obj`` path. Raises ``FileNotFoundError`` if the input
    mesh is missing (callers should not silently skip).
    """
    in_obj = os.path.join(in_dir, f"{obj_name}.obj")
    if not os.path.isfile(in_obj):
        raise FileNotFoundError(f"decimate: no raw obj at {in_obj}")

    os.makedirs(out_dir, exist_ok=True)
    out_obj = os.path.join(out_dir, f"{obj_name}.obj")

    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(in_obj)
    in_faces = ms.current_mesh().face_number()
    if in_faces <= target_faces:
        shutil.copy2(in_obj, out_obj)
    else:
        ms.apply_filter(
            "meshing_decimation_quadric_edge_collapse_with_texture",
            targetfacenum=target_faces,
            preserveboundary=True,
            preservenormal=True,
            optimalplacement=True,
        )
        ms.save_current_mesh(
            out_obj,
            save_vertex_color=False,
            save_vertex_normal=False,
            save_wedge_texcoord=True,
        )

    # pymeshlab writes its own {stem}.obj.mtl; bring the texture files over.
    in_mtl = os.path.join(in_dir, f"{obj_name}.mtl")
    if os.path.isfile(in_mtl):
        for tex in referenced_textures(in_mtl):
            src = os.path.join(in_dir, tex)
            dst = os.path.join(out_dir, os.path.basename(tex))
            if os.path.isfile(src) and not os.path.isfile(dst):
                shutil.copy2(src, dst)

    return out_obj
