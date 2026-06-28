"""Decimate raw meshes for fast viewing (pymeshlab).

    python src/decimate.py <obj> [<obj> ...]
    python src/decimate.py --all --target-faces 50000
"""

import argparse
import sys
from functools import partial

from object_processing.runner import decimate_object, resolve_objects, run_batch, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("objects", nargs="*", help="object names (or use --all)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--target-faces", type=int, default=50_000)
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args(argv)

    objs = resolve_objects(a.objects, a.all)
    print(f"Decimating {len(objs)} object(s) to {a.target_faces} faces")
    fn = partial(decimate_object, target_faces=a.target_faces, overwrite=a.overwrite)
    sys.exit(1 if report(run_batch(objs, fn, workers=1)) else 0)


if __name__ == "__main__":
    main()
