"""Convex decomposition and manifold/remesh via CoACD."""

import os

from object_processing.tools import coacd_bin, run, require_output

# Default CoACD args for decomposition: small minimum-volume threshold and
# decimation of the resulting hulls (legacy default).
DEFAULT_DECOMP_ARGS = ["-mv", "1e-10", "--decimate"]


def convex_decompose(
    input_path,
    output_path,
    parts_dir,
    part_prefix="convex_piece",
    extra_args=DEFAULT_DECOMP_ARGS,
    quiet=True,
):
    """Decompose a mesh into convex pieces with CoACD.

    Writes the merged decomposition to ``output_path`` (e.g. ``coacd.obj``) and
    the individual convex pieces to ``parts_dir`` as ``{part_prefix}*.obj`` —
    those pieces feed :func:`export_urdf` / :func:`export_mjcf`.
    """
    os.makedirs(parts_dir, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [
        coacd_bin(),
        "-i", input_path,
        "-o", output_path,
        "-pf", parts_dir,
        "-pn", part_prefix,
        *list(extra_args),
    ]
    run(cmd, quiet=quiet)
    require_output(output_path, "convex_decompose")


def manifold(input_path, output_path, level_set=0.1, quiet=True):
    """Produce a watertight/manifold mesh from ``input_path`` using CoACD's
    dual-marching-cubes remesher."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [
        coacd_bin(),
        "-i", input_path,
        "-ro", output_path,
        "-pm", "on",
        "--dualmc-threshold", str(level_set),
    ]
    run(cmd, quiet=quiet)
    require_output(output_path, "manifold")
