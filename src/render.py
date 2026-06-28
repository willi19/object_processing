"""CLI for headless Open3D figures (pipeline strip, tabletop grid, overlays, turntable).

    python src/render.py pipeline  <obj> --out fig.png
    python src/render.py tabletop  <obj> --out poses.png
    python src/render.py overlays  <obj> --out obb_sym.png
    python src/render.py turntable <obj> --out spin.gif [--stage simplified]

Rendering logic lives in object_processing.visualization.render (importable);
this is just the runnable entry point.
"""

import argparse
import os

from object_processing.utils.config import obj_dir
from object_processing.visualization.render import (
    render_pipeline_figure,
    render_tabletop_figure,
    render_overlays_figure,
    save_turntable_gif,
)

_TURNTABLE_STAGES = {
    "raw": "raw_mesh/{obj}.obj",
    "coacd": "processed_data/mesh/coacd.obj",
    "manifold": "processed_data/mesh/manifold.obj",
    "simplified": "processed_data/mesh/simplified.obj",
}


def main(argv=None):
    p = argparse.ArgumentParser(prog="render")
    sub = p.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("pipeline", help="render pipeline-stage strip for an object")
    pf.add_argument("object")
    pf.add_argument("--out", required=True)
    pf.add_argument("--tile", type=int, default=560)

    tb = sub.add_parser("tabletop", help="render the mesh in each stable tabletop pose")
    tb.add_argument("object")
    tb.add_argument("--out", required=True)

    ov = sub.add_parser("overlays", help="render mesh + OBB + symmetry axes")
    ov.add_argument("object")
    ov.add_argument("--out", required=True)

    tt = sub.add_parser("turntable", help="render a spinning GIF of a stage mesh")
    tt.add_argument("object")
    tt.add_argument("--out", required=True)
    tt.add_argument("--stage", default="simplified", choices=list(_TURNTABLE_STAGES),
                    help="mesh stage to spin (default: simplified)")
    tt.add_argument("--frames", type=int, default=36)

    a = p.parse_args(argv)
    if a.cmd == "pipeline":
        labels = render_pipeline_figure(a.object, a.out, tile=a.tile)
        print(f"wrote {a.out}  ({' -> '.join(labels)})")
    elif a.cmd == "tabletop":
        n = render_tabletop_figure(a.object, a.out)
        print(f"wrote {a.out}  ({n} poses)")
    elif a.cmd == "overlays":
        render_overlays_figure(a.object, a.out)
        print(f"wrote {a.out}")
    elif a.cmd == "turntable":
        path = os.path.join(obj_dir(a.object), _TURNTABLE_STAGES[a.stage].format(obj=a.object))
        save_turntable_gif(path, a.out, n_frames=a.frames)
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
