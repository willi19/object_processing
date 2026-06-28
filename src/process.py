"""Run the full mesh pipeline per object.

    python src/process.py <obj> [<obj> ...]
    python src/process.py --all --skip --workers 8

Stages raise on failure; failures are reported per object with a non-zero exit.
"""

import argparse
import sys
from functools import partial

from object_processing.utils.config import object_root
from object_processing.runner import process_object, resolve_objects, run_batch, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("objects", nargs="*", help="object names (or use --all)")
    ap.add_argument("--all", action="store_true", help="process every object")
    ap.add_argument("--skip", action="store_true", help="skip stages whose output exists")
    ap.add_argument("--workers", type=int, default=1, help="parallel object workers")
    ap.add_argument("--verbose", action="store_true", help="show external tool output")
    a = ap.parse_args(argv)

    objs = resolve_objects(a.objects, a.all)
    print(f"Processing {len(objs)} object(s) under {object_root()}")
    fn = partial(process_object, skip=a.skip, quiet=not a.verbose)
    sys.exit(1 if report(run_batch(objs, fn, a.workers)) else 0)


if __name__ == "__main__":
    main()
