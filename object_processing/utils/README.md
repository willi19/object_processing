# `utils/` — shared infrastructure

Small, dependency-light helpers used across the package.

| Module | Role |
|--------|------|
| [`config.py`](config.py) | Resolve the per-object data root. `object_root()` reads `$OBJECT_ROOT` (default `~/shared_data/AutoDex/object/paradex`); `obj_dir(name)` is the directory for one object. |
| [`tools.py`](tools.py) | Resolve the native **CoACD** / **ACVD** binaries (`$COACD_BIN` / `$ACVD_BIN`, else `third_party/`), run subprocesses (raising on non-zero exit), and assert a stage produced its output. |
| [`rotation.py`](rotation.py) | Numpy quaternion helpers (`[w, x, y, z]`) used by stable-pose generation. |

```python
from object_processing.utils.config import object_root, obj_dir
from object_processing.utils.tools import coacd_bin, acvd_bin, run
```

Point the whole pipeline at a different dataset (e.g. a private copy, so a shared
dataset used by other tools is never written to) by setting the environment
variable:

```bash
export OBJECT_ROOT=~/object_data/paradex
```
