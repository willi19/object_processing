"""Curated 'teaser' tabletop pose per object — the single source of truth.

The pipeline emits several stable tabletop poses per object. The tallest one is a
sensible default 'hero' shot, but for some objects that pose is a near-duplicate,
a physically implausible resting pose, or simply an uninteresting side. For those
objects ``POSE_OVERRIDE`` pins a hand-picked tabletop pose (the ``.npy`` filename
stem under ``processed_data/info/tabletop/``).

This module is shared by everything that needs the same pose:
- the thumbnail renderer (``wiki/render_thumbnails.py``),
- the overlay figure (``render.render_overlays_figure``),
- the web viewer, via ``display_pose`` written into ``info.json`` by
  ``webexport.export_web_info``.

Only numpy / stdlib are imported here so it stays import-cheap (no Open3D).
"""

import glob
import json
import os

import numpy as np

# Per-object pose override: use this specific tabletop pose (.npy stem in
# processed_data/info/tabletop/) instead of the auto-selected tallest pose.
POSE_OVERRIDE = {
    "blue_alarm": "000",   # stands the clock up on its legs (vs 011 lying flat)
    "apple": "004",
    "baby_beaker": "033",
    "beige_brush": "000",
    "colander_green": "000",
    "blue_vase": "003",
    "box_pink": "002",
    "brass_pot": "017",
    "brown_ramen": "003",
    "container_pink": "005",
    "french_mustard": "002",   # 025 was an impossible resting pose
    "frog_bowl": "000",
    "frog_cup": "002",         # 019 was an impossible resting pose
    "fruit_cutter_base": "004",
    "fruit_cutter_green": "001",   # 009/010/019 were impossible poses
    "fruit_cutter_light_green": "000",   # 010/028/001 were impossible poses
    "green_attached_container": "008",
    "green_lamp": "001",
    "green_soap_dispenser": "002",
    "icecream_scoop": "000",   # 002 was a duplicate pose
    "large_peg": "002",        # 017 was an impossible pose
    "lemon_squeezer": "003",
    "light_green_basket": "001",
    "open_box": "002",
    "organizer_beige": "001",
    "pastel_blue_cup": "000",
    "mug_holder": "009",
    "jja_ramen": "000",
    "pink_clock": "012",
    "paper_bowl": "001",
    "paper_cup": "025",
    "pepper_tuna": "019",
    "pepper_tuna_light": "010",
    "yellow_plastic_cup": "001",
    "wood_tray_big": "001",
    "wood_tray_small": "002",
    "soaptray": "001",
    "standing_frame": "030",   # 034/017 were impossible resting poses
    "yellow_funnel": "001",
    "plant_pot": "001",
    "toothbrush_holder": "024",   # 001 was an impossible resting pose
    "white_plastic_box": "001",
    "white_soap_dish": "002",
    "white_table_lamp": "012",    # 035 was an impossible resting pose
    "white_watering_can": "000",  # 004 was impossible; no truly upright pose exists, 000 is the best of {000,009,018}
    "magazine_file": "007",
    "shoe_organizer": "006",
    "smallbowl": "000",
    "spam_can": "006",
    "wateringcan": "003",
    "white_pen_cup": "005",
}


def _tallest_pose(poses, obb):
    """4x4 object->table for the most-upright stable pose (largest z-extent of
    the OBB after resting), or None. ``poses`` is a list of 4x4 array-likes;
    ``obb`` is ``{"extents": [...], "transform": [[...]]}``."""
    if not poses or not obb:
        return None
    e = obb["extents"]
    T = np.asarray(obb["transform"])
    hx, hy, hz = e[0] / 2, e[1] / 2, e[2] / 2
    local = np.array([[sx * hx, sy * hy, sz * hz, 1.0]
                      for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]).T
    cobj = T @ local
    best, best_h = None, -1e9
    for pose in poses:
        P = np.asarray(pose)
        w = P @ cobj
        h = w[2].max() - w[2].min()
        if h > best_h:
            best_h, best = h, P
    return best


def teaser_pose(obj_name, base):
    """Return the 4x4 object->table 'teaser' pose for ``obj_name`` as an
    ``np.ndarray``, or ``None`` if the object has no tabletop poses.

    Uses the curated ``POSE_OVERRIDE`` pose if listed, otherwise the tallest
    stable pose. ``base`` is the object's source dir
    (``…/object_processing/<name>``); poses and OBB are read from
    ``<base>/processed_data/info/``.
    """
    info_dir = os.path.join(base, "processed_data", "info")
    stem = POSE_OVERRIDE.get(obj_name)
    if stem is not None:
        return np.load(os.path.join(info_dir, "tabletop", f"{stem}.npy"))

    pose_files = sorted(glob.glob(os.path.join(info_dir, "tabletop", "*.npy")))
    simp = os.path.join(info_dir, "simplified.json")
    if not pose_files or not os.path.exists(simp):
        return None
    with open(simp) as f:
        s = json.load(f)
    obb = {"extents": s["obb"], "transform": s["obb_transform"]}
    return _tallest_pose([np.load(p) for p in pose_files], obb)
