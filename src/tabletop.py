"""(Re)generate stable tabletop poses per object.

    python src/tabletop.py <obj> [<obj> ...]
    python src/tabletop.py --all --max-try 200

Always also writes the per-candidate settling/stability trajectories to
info/debug/ for the table_top viewer's "show motion" toggle.
"""

import argparse
import sys
from functools import partial

from object_processing.runner import tabletop_object, resolve_objects, run_batch, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("objects", nargs="*", help="object names (or use --all)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--max-try", type=int, default=200,
                    help="number of candidate orientations to sample")
    a = ap.parse_args(argv)

    objs = resolve_objects(a.objects, a.all)
    print(f"Generating tabletop poses for {len(objs)} object(s)")
    fn = partial(tabletop_object, max_try=a.max_try)
    sys.exit(1 if report(run_batch(objs, fn, workers=1)) else 0)


if __name__ == "__main__":
    main()
