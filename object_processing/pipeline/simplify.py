"""Surface simplification via ACVD."""

import os

from object_processing.utils.tools import acvd_bin, run, require_output


def simplify(input_path, output_path, vert_num=2000, gradation=1.5, quiet=False):
    """Simplify a mesh to roughly ``vert_num`` vertices with ACVD.

    ``output_path`` must be a ``.ply`` (ACVD's output format); convert it to
    ``.obj`` afterward with :func:`object_processing.pipeline.change_format`.
    ``gradation`` controls adaptivity (1.5 is the value recommended upstream).
    """
    if not output_path.endswith(".ply"):
        raise ValueError(f"simplify output must be a .ply, got {output_path}")

    out_dir = os.path.dirname(os.path.abspath(output_path))
    out_name = os.path.basename(output_path)
    os.makedirs(out_dir, exist_ok=True)

    cmd = [
        acvd_bin(),
        input_path,
        str(vert_num),
        str(gradation),
        "-o", out_dir + os.sep,
        "-of", out_name,
        "-m", "1",
    ]
    run(cmd, quiet=quiet)
    require_output(output_path, "simplify")

    # ACVD also drops a "smooth_" sibling we don't keep.
    smooth = os.path.join(out_dir, "smooth_" + out_name)
    if os.path.exists(smooth):
        os.remove(smooth)
