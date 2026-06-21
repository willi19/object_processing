"""Numpy quaternion helpers used by stable-pose generation.

Ported from the legacy ``MeshProcess/src/util/rotation.py``. Quaternions are
``[w, x, y, z]`` with the real part first.
"""

import numpy as np


def np_normalize(x_vec):
    return x_vec / np.maximum(np.linalg.norm(x_vec, axis=-1, keepdims=True), 1e-8)


def standardize_quaternion(quaternions):
    """Force the real part of a unit quaternion to be non-negative."""
    return np.where(quaternions[..., 0:1] < 0, -quaternions, quaternions)


def batched_quat_inv(quaternions):
    inverses = np.copy(quaternions)
    inverses[..., 1:] = -inverses[..., 1:]
    return inverses


def batched_quat_multiply(quaternion0, quaternion1):
    w0, x0, y0, z0 = np.split(quaternion0, 4, axis=-1)
    w1, x1, y1, z1 = np.split(quaternion1, 4, axis=-1)
    return standardize_quaternion(
        np.concatenate(
            (
                -x1 * x0 - y1 * y0 - z1 * z0 + w1 * w0,
                x1 * w0 + y1 * z0 - z1 * y0 + w1 * x0,
                -x1 * z0 + y1 * w0 + z1 * x0 + w1 * y0,
                x1 * y0 - y1 * x0 + z1 * w0 + w1 * z0,
            ),
            axis=-1,
        )
    )


def batched_quat_to_axisangle(quaternions):
    w = quaternions[..., 0]
    vec = quaternions[..., 1:]
    angles = 2 * np.arccos(np.clip(w, -1.0, 1.0))
    norm_vec = np.linalg.norm(vec, axis=-1, keepdims=True)
    axes = np.divide(vec, norm_vec, out=np.zeros_like(vec), where=(norm_vec != 0))
    return angles, axes


def batched_quat_delta(q0, q1):
    """Angle/axis of the relative rotation taking q0 to q1."""
    return batched_quat_to_axisangle(batched_quat_multiply(batched_quat_inv(q0), q1))
