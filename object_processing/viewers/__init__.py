"""Viser desktop viewers for inspecting per-object mesh/processing data.

These are interactive 3D viewers built on the viser server. They are run
directly as scripts (each module executes a viewer at import time) and require
a display/browser to be useful. They depend on the external ``paradex`` package
for ``paradex.visualization.visualizer.viser.ViserViewer``; this is an accepted
external dependency and is not vendored here.

Object data roots are resolved via ``object_processing.config.object_root()``.

Viewers
-------
object_viewer
    Raw / simplified / coacd mesh variants shown side-by-side, each with its
    oriented bounding box (OBB) and axes.
table_top
    Grid of all stable tabletop poses for an object, each rendered with its
    OBB and axes.
tabletop_compare
    Compare pairs of tabletop poses with gravity-axis (yaw) alignment; reports
    the residual angular difference and visualizes a selected pair.
cylinder_axis
    Symmetry-axis residual validation: rotate the mesh about a candidate axis
    and measure nearest-surface residuals to check cylindrical symmetry.
scene_viewer
    View a scene JSON (target + obstacles) with the target's OBB and axes.

Not ported
----------
scene_grid_viewer
    Not ported — depends on out-of-scope scene generation
    (``from generate_scene import ...``).
"""
