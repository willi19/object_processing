"""External tool resolution and subprocess helpers.

The mesh pipeline shells out to two native tools:

- **CoACD** (``third_party/CoACD/build/main``) for convex decomposition and the
  manifold/remesh step.
- **ACVD** (``third_party/ACVD/bin/ACVD``) for surface simplification.

Binary locations are resolved from environment variables (``COACD_BIN`` /
``ACVD_BIN``) and otherwise fall back to ``third_party/`` at the repo root.

All process invocation goes through :func:`run`, which raises on a non-zero exit
instead of swallowing it — the pipeline never silently continues past a failed
external tool.
"""

import os
import subprocess

# Repo root = two levels up from this file (object_processing/utils/tools.py).
_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def _resolve(env_var: str, *rel_parts: str) -> str:
    """Resolve a tool binary: ``$env_var`` if set, else the first existing
    candidate under ``third_party/`` (or the legacy ``MeshProcess/third_party/``).
    Falls back to the primary location so the error message points somewhere real.
    """
    path = os.environ.get(env_var)
    if path:
        return os.path.abspath(path)

    candidates = [
        os.path.join(_REPO_ROOT, "third_party", *rel_parts),
        os.path.join(_REPO_ROOT, "MeshProcess", "third_party", *rel_parts),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]


def coacd_bin() -> str:
    return _resolve("COACD_BIN", "CoACD", "build", "main")


def acvd_bin() -> str:
    return _resolve("ACVD_BIN", "ACVD", "bin", "ACVD")


def run(cmd, quiet: bool = False) -> None:
    """Run ``cmd`` (a list of args), raising ``CalledProcessError`` on failure.

    When ``quiet`` is set, stdout/stderr are suppressed unless the command
    fails, in which case the captured output is attached to the raised error so
    the failure is never silent.
    """
    if quiet:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr
            )
    else:
        subprocess.run(cmd, check=True)


def require_output(output_path: str, stage: str) -> None:
    """Raise if a stage did not produce its expected output file."""
    if not os.path.exists(output_path):
        raise RuntimeError(
            f"{stage}: expected output not produced at {output_path}"
        )
