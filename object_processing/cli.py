"""Command-line runner for the object processing pipeline.

Usage::

    python -m object_processing process [obj ...] [--all] [--skip] [--workers N]
    python -m object_processing decimate [obj ...] [--all] [--target-faces N]

Stages run in dependency order. Each stage raises on failure; the batch runner
collects failures per object and prints a loud summary with full tracebacks,
exiting non-zero if anything failed — failures are never swallowed into a log.
"""

import argparse
import os
import sys
import traceback
from multiprocessing import Pool

from object_processing.utils.config import object_root, obj_dir
from object_processing import pipeline

# Objects that are bodies of revolution: de-duplicate stable poses by up-axis
# tilt only (rotation about the symmetry axis is irrelevant).
CYLINDRICAL_OBJECTS = {"pringles", "smallbowl", "servingbowl_small"}


def _exists(path):
    return os.path.exists(path)


def process_object(obj_name, skip=False, quiet=True):
    """Run the full mesh pipeline for one object. Raises on the first failure.

    Layout produced under ``{OBJECT_ROOT}/{obj_name}``:
        processed_data/mesh/{raw,coacd,manifold,simplified}.obj
        processed_data/urdf/{coacd.urdf,coacd.xml,meshes/}
        processed_data/info/{simplified.json,tabletop/*.npy}
    """
    root = obj_dir(obj_name)
    raw_in = os.path.join(root, "raw_mesh", f"{obj_name}.obj")
    if not os.path.isfile(raw_in):
        raise FileNotFoundError(f"{obj_name}: missing raw mesh {raw_in}")

    mesh_dir = os.path.join(root, "processed_data", "mesh")
    urdf_dir = os.path.join(root, "processed_data", "urdf")
    info_dir = os.path.join(root, "processed_data", "info")
    parts_dir = os.path.join(urdf_dir, "meshes")

    raw_obj = os.path.join(mesh_dir, "raw.obj")
    coacd_obj = os.path.join(mesh_dir, "coacd.obj")
    manifold_obj = os.path.join(mesh_dir, "manifold.obj")
    simplified_ply = os.path.join(mesh_dir, "simplified.ply")
    simplified_obj = os.path.join(mesh_dir, "simplified.obj")
    urdf_path = os.path.join(urdf_dir, "coacd.urdf")
    mjcf_path = os.path.join(urdf_dir, "coacd.xml")
    info_path = os.path.join(info_dir, "simplified.json")
    symmetry_path = os.path.join(info_dir, "symmetry.json")
    tabletop_dir = os.path.join(info_dir, "tabletop")

    # (output_path-to-test-for-skip, callable). A None test means "always run".
    steps = [
        (raw_obj, lambda: pipeline.change_format(raw_in, raw_obj, keep_material=True)),
        (coacd_obj, lambda: pipeline.convex_decompose(raw_obj, coacd_obj, parts_dir, quiet=quiet)),
        (urdf_path, lambda: pipeline.export_urdf(parts_dir, urdf_path)),
        (mjcf_path, lambda: pipeline.export_mjcf(parts_dir, mjcf_path)),
        (manifold_obj, lambda: pipeline.manifold(coacd_obj, manifold_obj, quiet=quiet)),
        (simplified_ply, lambda: pipeline.simplify(manifold_obj, simplified_ply, quiet=quiet)),
        (simplified_obj, lambda: pipeline.change_format(
            simplified_ply, simplified_obj, keep_material=False, delete_input=True)),
        (info_path, lambda: pipeline.basic_info(simplified_obj, info_path)),
        (symmetry_path, lambda: pipeline.compute_symmetry(simplified_obj, symmetry_path)),
        (tabletop_dir, lambda: pipeline.generate_tabletop_poses(
            mjcf_path, tabletop_dir,
            cylindrical=obj_name in CYLINDRICAL_OBJECTS)),
    ]

    for out_path, step in steps:
        if skip and out_path is not None and _exists(out_path):
            continue
        step()


def _run_one(args):
    """Worker wrapper: returns (obj_name, traceback_or_None) for aggregation."""
    obj_name, skip, quiet = args
    try:
        process_object(obj_name, skip=skip, quiet=quiet)
        return obj_name, None
    except Exception:
        return obj_name, traceback.format_exc()


def _discover_objects():
    root = object_root()
    return sorted(
        d for d in os.listdir(root)
        if os.path.isdir(os.path.join(root, d, "raw_mesh"))
    )


def _resolve_obj_list(args):
    if args.all:
        return _discover_objects()
    if args.objects:
        return args.objects
    raise SystemExit("specify object name(s) or --all")


def _report(results):
    """Print a loud summary; return the number of failures."""
    failures = [(name, tb) for name, tb in results if tb is not None]
    n_ok = len(results) - len(failures)
    print(f"\n=== {n_ok}/{len(results)} objects succeeded ===")
    for name, tb in failures:
        print(f"\n----- FAILED: {name} -----\n{tb}", file=sys.stderr)
    if failures:
        print(
            f"{len(failures)} object(s) FAILED: "
            + ", ".join(name for name, _ in failures),
            file=sys.stderr,
        )
    return len(failures)


def cmd_process(args):
    objs = _resolve_obj_list(args)
    print(f"Processing {len(objs)} object(s) under {object_root()}")
    work = [(o, args.skip, not args.verbose) for o in objs]

    if args.workers > 1:
        with Pool(processes=args.workers) as pool:
            results = pool.map(_run_one, work)
    else:
        results = [_run_one(w) for w in work]

    sys.exit(1 if _report(results) else 0)


def cmd_decimate(args):
    from object_processing.pipeline.decimate import decimate  # needs pymeshlab

    objs = _resolve_obj_list(args)
    root = object_root()
    print(f"Decimating {len(objs)} object(s) to {args.target_faces} faces")

    results = []
    for obj in objs:
        in_dir = os.path.join(root, obj, "raw_mesh")
        out_dir = os.path.join(root, obj, "raw_mesh_decimated")
        if os.path.isdir(out_dir) and not args.overwrite:
            print(f"  skip (exists): {obj}")
            results.append((obj, None))
            continue
        try:
            decimate(obj, in_dir, out_dir, args.target_faces)
            results.append((obj, None))
        except Exception:
            results.append((obj, traceback.format_exc()))

    sys.exit(1 if _report(results) else 0)


def cmd_symmetry(args):
    objs = _resolve_obj_list(args)
    root = object_root()
    print(f"Detecting symmetry for {len(objs)} object(s)")

    results = []
    for obj in objs:
        info_dir = os.path.join(root, obj, "processed_data", "info")
        simplified_obj = os.path.join(root, obj, "processed_data", "mesh", "simplified.obj")
        out_path = os.path.join(info_dir, "symmetry.json")
        if os.path.exists(out_path) and not args.overwrite:
            print(f"  skip (exists): {obj}")
            results.append((obj, None))
            continue
        try:
            sym = pipeline.compute_symmetry(simplified_obj, out_path, rel_tol=args.rel_tol)
            axes = ", ".join(
                f"{a['fold']}-fold (res {a['residual']:.4f})" for a in sym["axes"]
            ) or "none"
            print(f"  {obj}: {sym['type']}  [{axes}]")
            results.append((obj, None))
        except Exception:
            results.append((obj, traceback.format_exc()))

    sys.exit(1 if _report(results) else 0)


def build_parser():
    parser = argparse.ArgumentParser(prog="object_processing")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("process", help="run the full mesh pipeline")
    p.add_argument("objects", nargs="*", help="object names (or use --all)")
    p.add_argument("--all", action="store_true", help="process every object")
    p.add_argument("--skip", action="store_true", help="skip stages whose output exists")
    p.add_argument("--workers", type=int, default=1, help="parallel object workers")
    p.add_argument("--verbose", action="store_true", help="show external tool output")
    p.set_defaults(func=cmd_process)

    d = sub.add_parser("decimate", help="decimate raw meshes for visualization")
    d.add_argument("objects", nargs="*", help="object names (or use --all)")
    d.add_argument("--all", action="store_true")
    d.add_argument("--target-faces", type=int, default=50_000)
    d.add_argument("--overwrite", action="store_true")
    d.set_defaults(func=cmd_decimate)

    s = sub.add_parser("symmetry", help="detect rotational symmetry per object")
    s.add_argument("objects", nargs="*", help="object names (or use --all)")
    s.add_argument("--all", action="store_true")
    s.add_argument("--rel-tol", type=float, default=0.01,
                   help="acceptance threshold as a fraction of object scale")
    s.add_argument("--overwrite", action="store_true")
    s.set_defaults(func=cmd_symmetry)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
