# `viewers/` — interactive desktop viewers (Viser)

Interactive 3D viewers for inspecting per-object data, built on the
[Viser](https://viser.studio) server. Each runs as a script and needs a
browser/display — these are **local inspection tools**, not the web gallery (that
is the static Babylon.js viewer in [`docs/`](../../docs/)). They depend on the
external `paradex` package and are installed with `pip install -e .[viewers]`.

| Module | Shows |
|--------|-------|
| [`object_viewer.py`](object_viewer.py) | raw / simplified / coacd mesh variants side by side, each with its OBB and axes |
| [`table_top.py`](table_top.py) | grid of all stable tabletop poses for an object |
| [`tabletop_compare.py`](tabletop_compare.py) | compare pose pairs after factoring out gravity-axis (yaw) rotation; reports residual angle |
| [`cylinder_axis.py`](cylinder_axis.py) | rotate the mesh about a candidate axis and measure the symmetry residual |
| [`scene_viewer.py`](scene_viewer.py) | a scene JSON (target + obstacles) with the target's OBB and axes |

```bash
python -m object_processing.viewers.table_top      # opens a Viser server
```

Object roots are resolved via [`utils/config.py`](../utils/config.py)
(`$OBJECT_ROOT`).
