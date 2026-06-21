"""Export convex pieces as a fixed-joint URDF and a MuJoCo MJCF."""

import os

import lxml.etree as et
import mujoco

from object_processing.utils.tools import require_output


def export_urdf(parts_dir, output_path):
    """Write a URDF whose links are the convex pieces in ``parts_dir``, chained
    by fixed joints. Mesh filenames are stored relative to the URDF's directory.
    """
    piece_names = sorted(os.listdir(parts_dir))
    if not piece_names:
        raise RuntimeError(f"export_urdf: no convex pieces found in {parts_dir}")

    commonprefix = os.path.commonprefix([parts_dir, output_path])
    root = et.Element("robot", name="root")

    prev_link_name = None
    for piece_name in piece_names:
        piece_filename = os.path.join(parts_dir, piece_name).removeprefix(commonprefix)
        link_name = f"link_{piece_name}"

        link = et.SubElement(root, "link", name=link_name)
        inertial = et.SubElement(link, "inertial")
        et.SubElement(inertial, "origin", xyz="0 0 0", rpy="0 0 0")

        visual = et.SubElement(link, "visual")
        et.SubElement(visual, "origin", xyz="0 0 0", rpy="0 0 0")
        geometry = et.SubElement(visual, "geometry")
        et.SubElement(geometry, "mesh", filename=piece_filename, scale="1.0 1.0 1.0")

        collision = et.SubElement(link, "collision")
        et.SubElement(collision, "origin", xyz="0 0 0", rpy="0 0 0")
        geometry = et.SubElement(collision, "geometry")
        et.SubElement(geometry, "mesh", filename=piece_filename, scale="1.0 1.0 1.0")

        if prev_link_name is not None:
            joint = et.SubElement(
                root, "joint", name=f"{link_name}_joint", type="fixed"
            )
            et.SubElement(joint, "origin", xyz="0 0 0", rpy="0 0 0")
            et.SubElement(joint, "parent", link=prev_link_name)
            et.SubElement(joint, "child", link=link_name)
        prev_link_name = link_name

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    et.ElementTree(root).write(output_path, pretty_print=True)
    require_output(output_path, "export_urdf")


def export_mjcf(parts_dir, output_path):
    """Write a MuJoCo MJCF with one visual + one collision geom per convex piece.

    Visual geoms are non-colliding (``contype=conaffinity=0``); collision geoms
    use the piece meshes directly. Mesh paths are stored relative to the MJCF.
    """
    piece_names = sorted(os.listdir(parts_dir))
    if not piece_names:
        raise RuntimeError(f"export_mjcf: no convex pieces found in {parts_dir}")

    commonprefix = os.path.commonprefix([parts_dir, output_path])

    spec = mujoco.MjSpec()
    spec.meshdir = commonprefix
    for i, piece_name in enumerate(piece_names):
        piece_filename = os.path.join(parts_dir, piece_name).removeprefix(commonprefix)
        spec.add_mesh(name=piece_name, file=piece_filename)
        spec.worldbody.add_geom(
            name=f"object_visual_{i}",
            type=mujoco.mjtGeom.mjGEOM_MESH,
            meshname=piece_name,
            density=0,
            contype=0,
            conaffinity=0,
        )
        spec.worldbody.add_geom(
            name=f"object_collision_{i}",
            type=mujoco.mjtGeom.mjGEOM_MESH,
            meshname=piece_name,
        )

    spec.compile()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(spec.to_xml().replace(commonprefix, "."))
    require_output(output_path, "export_mjcf")
