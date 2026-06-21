"""Headless visualization and web export of processed objects.

- :mod:`render`    — pipeline-stage figures, tabletop / symmetry figures, and
  turntable GIFs, rendered with Open3D's offscreen GPU renderer
- :mod:`webexport` — per-object stage GLBs + ``info.json`` for the web viewer

Open3D is an optional, heavy dependency and is imported lazily inside the
functions that need it, so importing this package never requires it.
"""
