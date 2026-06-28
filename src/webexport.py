"""CLI to export per-object web assets: stage GLBs + overlay info.json.

    python src/webexport.py <obj> [<obj> ...]
    python src/webexport.py --all

Stage GLBs go to ``--glb-out`` (gitignored; upload to HuggingFace); the small
info.json overlays go to ``--info-out`` (committed; served by GitHub Pages).
Export logic lives in object_processing.visualization.webexport.
"""

import argparse
import os
import sys
import traceback

from object_processing.utils.config import object_root
from object_processing.visualization.webexport import export_object


def main(argv=None):
    p = argparse.ArgumentParser(prog="webexport")
    p.add_argument("objects", nargs="*", help="object names (or use --all)")
    p.add_argument("--all", action="store_true")
    p.add_argument("--glb-out", default="wiki/output",
                   help="root for stage GLBs (gitignored; upload to HuggingFace)")
    p.add_argument("--info-out", default="docs",
                   help="root for info.json (committed; served by GitHub Pages)")
    a = p.parse_args(argv)

    if a.all:
        r = object_root()
        objs = sorted(d for d in os.listdir(r)
                      if os.path.isdir(os.path.join(r, d, "processed_data", "mesh")))
    elif a.objects:
        objs = a.objects
    else:
        raise SystemExit("specify object name(s) or --all")

    fails = []
    for o in objs:
        try:
            written, info = export_object(o, a.glb_out, a.info_out)
            sym = info.get("symmetry", {}).get("type", "?")
            print(f"  {o}: stages={written} sym={sym} "
                  f"poses={info.get('n_tabletop_poses', 0)}")
        except Exception:
            fails.append(o)
            print(f"  {o}: FAILED\n{traceback.format_exc()}", file=sys.stderr)
    print(f"\n{len(objs) - len(fails)}/{len(objs)} objects exported")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
