# `viewers/` — interactive desktop viewers (Viser)

Interactive 3D viewers for inspecting per-object data, built on the
[Viser](https://viser.studio) server. Each runs as a script and needs a
browser/display — these are **local inspection tools**, not the web gallery (that
is the static Babylon.js viewer in [`docs/`](../../docs/)). They depend on the
external `paradex` package and are installed with `pip install -e .[viewers]`.

| Module | Shows |
|--------|-------|
| [`object_viewer.py`](object_viewer.py) | raw / simplified / coacd mesh variants side by side, each with its OBB and axes; the raw mesh also shows the **detected symmetry axes + type label** (toggle "Show Symmetry") |
| [`table_top.py`](table_top.py) | grid of all stable tabletop poses for an object; tick **Show settling motion** to instead **animate** every candidate drop (green=settled, red=failed) with the contact face/normal + an MP4 recorder |
| [`cylinder_axis.py`](cylinder_axis.py) | rotate the mesh about a candidate axis and measure the symmetry residual |

Scene viewers are intentionally **not** here — this repo does mesh/object
processing, not scene generation, so a scene viewer would have nothing to show.
They live with AutoDex's `scene_generation`.

```bash
python src/viewers/table_top.py      # opens a Viser server
```

The **Show settling motion** toggle reads `processed_data/info/debug/`, which the
tabletop step writes automatically (`python src/tabletop.py <obj>`, or the full
`src/process.py`).

Object roots are resolved via
[`object_processing/utils/config.py`](../../object_processing/utils/config.py)
(`$OBJECT_ROOT`).
