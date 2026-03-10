import numpy as np
import os
import transforms3d
import trimesh
import json
import glob

from paradex.utils.path import shared_dir
from paradex.visualization.visualizer.viser import ViserViewer

from autodex.utils.path import robot_configs_path, get_object_mesh

# ── Color palette ──────────────────────────────────────────────────────────────
COLOR_OBB     = (0.27, 0.51, 1.00)   # Cyan
COLOR_AXIS_X  = (1.00, 0.20, 0.20)   # Red
COLOR_AXIS_Y  = (0.20, 0.85, 0.20)   # Green
COLOR_AXIS_Z  = (0.20, 0.20, 1.00)   # Blue

LINE_WIDTH_OBB    = 4.0
LINE_WIDTH_AXIS   = 3.0
LINE_WIDTH_NORMAL = 2.5
# ──────────────────────────────────────────────────────────────────────────────

# Find available objects
obj_base_dir = os.path.join(shared_dir, "RSS2026_Mingi", "object", "paradex")
available_objects = sorted([
    d for d in os.listdir(obj_base_dir)
    if os.path.isdir(os.path.join(obj_base_dir, d))
])

vis = ViserViewer()
vis.add_floor(0.0)


def clear_scene():
    """Remove all dynamically added scene objects."""
    for name in list(vis.obj_dict.keys()):
        try:
            vis.obj_dict[name]['frame'].remove()
        except Exception:
            pass
    vis.obj_dict.clear()
    vis.frame_nodes.clear()


def load_object(obj_name):
    clear_scene()

    mesh = get_object_mesh(obj_name)

    # Load OBB from simplified.json
    simplified_json_path = os.path.join(
        shared_dir, "RSS2026_Mingi", "object", "paradex", obj_name,
        "processed_data", "info", "simplified.json"
    )
    with open(simplified_json_path, 'r') as f:
        simplified_data = json.load(f)
        obb_extents   = np.array(simplified_data['obb'])            # [x, y, z]
        obb_transform = np.array(simplified_data['obb_transform'])  # 4x4

    # Only successful poses
    succ_pose_list = glob.glob(os.path.join(
        shared_dir, "RSS2026_Mingi", "object", "paradex", obj_name,
        "processed_data", "info", "debug", "True", "*_traj.npy"
    ))

    margin      = 0.05
    grid_spacing = float(np.linalg.norm(obb_extents)) + margin
    grid_cols   = int(np.ceil(np.sqrt(max(len(succ_pose_list), 1))))

    # OBB corners in object local frame
    half_extents = obb_extents / 2
    obb_corners_local = np.array([
        [-half_extents[0], -half_extents[1], -half_extents[2]],
        [ half_extents[0], -half_extents[1], -half_extents[2]],
        [ half_extents[0],  half_extents[1], -half_extents[2]],
        [-half_extents[0],  half_extents[1], -half_extents[2]],
        [-half_extents[0], -half_extents[1],  half_extents[2]],
        [ half_extents[0], -half_extents[1],  half_extents[2]],
        [ half_extents[0],  half_extents[1],  half_extents[2]],
        [-half_extents[0],  half_extents[1],  half_extents[2]],
    ])
    obb_corners_obj = (obb_transform[:3, :3] @ obb_corners_local.T).T + obb_transform[:3, 3]

    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),   # bottom face
        (4, 5), (5, 6), (6, 7), (7, 4),   # top face
        (0, 4), (1, 5), (2, 6), (3, 7),   # vertical edges
    ]

    axis_len = float(np.max(obb_extents)) * 0.6

    for idx, table_path in enumerate(succ_pose_list):
        obj_traj  = np.load(table_path)
        traj_name = os.path.basename(table_path).removesuffix("_traj.npy")

        info_path = table_path.replace("_traj.npy", "_info.json")
        face_info = None
        if os.path.exists(info_path):
            with open(info_path, 'r') as f:
                face_info = json.load(f)

        row    = idx // grid_cols - grid_cols // 2
        col    = idx  % grid_cols - grid_cols // 2
        offset = np.array([col * grid_spacing, row * grid_spacing, 0])

        # Final (table-top) pose only
        final_pose = np.eye(4)
        final_pose[:3, :3] = transforms3d.quaternions.quat2mat(obj_traj[-1, 3:7])
        final_pose[:3, 3]  = obj_traj[-1, :3] + offset

        vis.add_object(traj_name, mesh, obj_T=final_pose)

        fp = f"/objects/{traj_name}_frame"

        # ── OBB edges (child of object frame) ──
        for edge_idx, (i, j) in enumerate(edges):
            vis.server.scene.add_spline_catmull_rom(
                name=f"{fp}/obb_edge_{edge_idx}",
                positions=np.array([obb_corners_obj[i], obb_corners_obj[j]]),
                color=COLOR_OBB,
                line_width=LINE_WIDTH_OBB,
            )

        # ── X / Y / Z axes (child of object frame) ──
        origin = np.zeros(3)
        for axis_dir, axis_color, axis_label in [
            (np.array([1, 0, 0]), COLOR_AXIS_X, "axis_x"),
            (np.array([0, 1, 0]), COLOR_AXIS_Y, "axis_y"),
            (np.array([0, 0, 1]), COLOR_AXIS_Z, "axis_z"),
        ]:
            vis.server.scene.add_spline_catmull_rom(
                name=f"{fp}/{axis_label}",
                positions=np.array([origin, axis_dir * axis_len]),
                color=axis_color,
                line_width=LINE_WIDTH_AXIS,
            )

        # ── Face center & normal (child of object frame) ──
        if face_info is not None:
            face_center = np.array(face_info['surface_point'])
            face_normal = np.array(face_info['face_normal'])

            vis.server.scene.add_icosphere(
                name=f"{fp}/face_center",
                radius=0.005,
                color=(255, 0, 0),
                position=face_center,
            )
            vis.server.scene.add_spline_catmull_rom(
                name=f"{fp}/face_normal",
                positions=np.array([face_center, face_center + face_normal * 0.05]),
                color=(0.0, 1.0, 0.0),
                line_width=LINE_WIDTH_NORMAL,
            )

    print(f"Loaded: {obj_name}  ({len(succ_pose_list)} successful poses)")


# ── GUI ────────────────────────────────────────────────────────────────────────
with vis.server.gui.add_folder("Object Selection"):
    obj_dropdown = vis.server.gui.add_dropdown(
        "Object",
        options=tuple(available_objects),
        initial_value=available_objects[0] if available_objects else "",
    )
    load_btn = vis.server.gui.add_button("Load Object")

@load_btn.on_click
def _(_) -> None:
    load_object(obj_dropdown.value)

# Load initial object
if available_objects:
    load_object(available_objects[0])

vis.start_viewer()
