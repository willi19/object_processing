"""Tabletop-pose viewer.

Two modes, toggled by the **"Show settling motion"** checkbox:

- **off** (default): the object in each of its final *stable* tabletop poses,
  laid out on a grid with OBB and body axes.
- **on**: every candidate's drop is **animated** from
  ``processed_data/info/debug/{True,False}/*_traj.npy`` — green if it settled,
  red if it rolled/fell over — with OBB, axes, and the sampled contact
  face + normal. A view-locked MP4 recorder captures the motion.

The motion data is written automatically by the tabletop step
(``python src/tabletop.py <obj>`` or the full ``src/process.py``).

Needs the ``[viewers]`` extra and the external ``paradex`` package.
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import tempfile
import time

import numpy as np
import transforms3d
import trimesh

from paradex.visualization.visualizer.viser import ViserViewer

from object_processing.utils.config import object_root, find_raw_mesh

parser = argparse.ArgumentParser()
parser.add_argument("--obj_path", default=object_root(),
                    help="Root dir holding object subdirs (default: OBJECT_ROOT).")
cli_args = parser.parse_args()

# ── Color palette ──────────────────────────────────────────────────────────────
COLOR_SUCCESS = (0.00, 1.00, 0.00)   # Green — settled stably
COLOR_FAILURE = (1.00, 0.00, 0.00)   # Red   — rolled / fell over
COLOR_OBB     = (0.27, 0.51, 1.00)
COLOR_AXIS_X  = (1.00, 0.20, 0.20)
COLOR_AXIS_Y  = (0.20, 0.85, 0.20)
COLOR_AXIS_Z  = (0.20, 0.20, 1.00)

LINE_WIDTH_OBB    = 4.0
LINE_WIDTH_AXIS   = 3.0
LINE_WIDTH_NORMAL = 2.5
# ──────────────────────────────────────────────────────────────────────────────

obj_base_dir = cli_args.obj_path
available_objects = sorted([
    d for d in os.listdir(obj_base_dir)
    if os.path.isdir(os.path.join(obj_base_dir, d, "processed_data", "info", "tabletop"))
])

vis = ViserViewer()
vis.add_floor(0.0)
vis.add_view_save_gui()


def load_mesh(obj_name):
    """Prefer decimated raw mesh, then raw, then simplified."""
    decimated = os.path.join(obj_base_dir, obj_name, "raw_mesh_decimated", f"{obj_name}.obj")
    if os.path.exists(decimated):
        return trimesh.load(decimated, force="mesh")
    try:
        return trimesh.load(find_raw_mesh(obj_name, root=obj_base_dir), force="mesh")
    except FileNotFoundError:
        return trimesh.load(
            os.path.join(obj_base_dir, obj_name, "processed_data", "mesh", "simplified.obj"),
            force="mesh",
        )


def load_obb(obj_name):
    """Return (corners_in_object_frame, edges, axis_len) for the OBB overlay."""
    with open(os.path.join(obj_base_dir, obj_name, "processed_data", "info",
                           "simplified.json")) as f:
        data = json.load(f)
    obb_extents   = np.array(data['obb'])
    obb_transform = np.array(data['obb_transform'])

    half = obb_extents / 2
    corners_local = np.array([
        [-half[0], -half[1], -half[2]], [half[0], -half[1], -half[2]],
        [half[0],  half[1], -half[2]],  [-half[0], half[1], -half[2]],
        [-half[0], -half[1],  half[2]], [half[0], -half[1],  half[2]],
        [half[0],  half[1],  half[2]],  [-half[0], half[1],  half[2]],
    ])
    corners = (obb_transform[:3, :3] @ corners_local.T).T + obb_transform[:3, 3]
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
             (0, 4), (1, 5), (2, 6), (3, 7)]
    return obb_extents, corners, edges, float(np.max(obb_extents)) * 0.6


def _draw_obb_and_axes(fp, corners, edges, axis_len, obb_color=COLOR_OBB):
    for ei, (i, j) in enumerate(edges):
        vis.server.scene.add_spline_catmull_rom(
            name=f"{fp}/obb_edge_{ei}",
            positions=np.array([corners[i], corners[j]]),
            color=obb_color, line_width=LINE_WIDTH_OBB,
        )
    for axis_dir, axis_color, axis_label in [
        (np.array([1, 0, 0]), COLOR_AXIS_X, "axis_x"),
        (np.array([0, 1, 0]), COLOR_AXIS_Y, "axis_y"),
        (np.array([0, 0, 1]), COLOR_AXIS_Z, "axis_z"),
    ]:
        vis.server.scene.add_spline_catmull_rom(
            name=f"{fp}/{axis_label}",
            positions=np.array([np.zeros(3), axis_dir * axis_len]),
            color=axis_color, line_width=LINE_WIDTH_AXIS,
        )


def clear_scene():
    for name in list(vis.obj_dict.keys()):
        try:
            vis.obj_dict[name]['frame'].remove()
        except Exception:
            pass
    vis.obj_dict.clear()
    vis.frame_nodes.clear()
    vis.clear_traj()


def _grid(idx, cols, spacing):
    row = idx // cols - cols // 2
    col = idx % cols - cols // 2
    return np.array([col * spacing, row * spacing, 0])


def load_static(obj_name):
    """Final stable poses, one mesh each, on a grid."""
    mesh = load_mesh(obj_name)
    obb_extents, corners, edges, axis_len = load_obb(obj_name)
    poses = sorted(glob.glob(os.path.join(
        obj_base_dir, obj_name, "processed_data", "info", "tabletop", "*.npy")))

    spacing = float(np.linalg.norm(obb_extents)) + 0.05
    cols = int(np.ceil(np.sqrt(max(len(poses), 1))))
    for idx, path in enumerate(poses):
        pose = np.load(path).copy()
        pose[:3, 3] += _grid(idx, cols, spacing)
        name = os.path.basename(path).removesuffix(".npy")
        vis.add_object(name, mesh, obj_T=pose)
        _draw_obb_and_axes(f"/objects/{name}_frame", corners, edges, axis_len)
    print(f"Loaded: {obj_name}  ({len(poses)} stable poses)")


def load_motion(obj_name):
    """Animate every candidate drop (green=settled, red=failed)."""
    mesh = load_mesh(obj_name)
    obb_extents, corners, edges, axis_len = load_obb(obj_name)
    info_dir = os.path.join(obj_base_dir, obj_name, "processed_data", "info")
    trajs = sorted(glob.glob(os.path.join(info_dir, "debug", "*", "*_traj.npy")))
    succ = set(glob.glob(os.path.join(info_dir, "debug", "True", "*_traj.npy")))
    if not trajs:
        print(f"No settling motion for {obj_name} — run: python src/tabletop.py {obj_name}")
        return

    spacing = float(np.linalg.norm(obb_extents)) + 0.05
    cols = int(np.ceil(np.sqrt(max(len(trajs), 1))))
    traj_dict = {}
    for idx, path in enumerate(trajs):
        traj = np.load(path)
        offset = _grid(idx, cols, spacing)
        se3 = np.array([np.eye(4) for _ in range(traj.shape[0])])
        for i in range(traj.shape[0]):
            se3[i][:3, :3] = transforms3d.quaternions.quat2mat(traj[i, 3:7])
            se3[i][:3, 3]  = traj[i, :3] + offset

        name = os.path.basename(path).removesuffix("_traj.npy")
        traj_dict[name] = se3
        ok = path in succ
        status_color = COLOR_SUCCESS if ok else COLOR_FAILURE
        vis.add_object(name, mesh, obj_T=se3[0])
        vis.change_color(name=name, color=status_color)

        fp = f"/objects/{name}_frame"
        _draw_obb_and_axes(fp, corners, edges, axis_len, obb_color=status_color)

        info_path = path.replace("_traj.npy", "_info.json")
        if os.path.exists(info_path):
            with open(info_path) as f:
                fi = json.load(f)
            fc = np.array(fi['surface_point'])
            fn = np.array(fi['face_normal'])
            vis.server.scene.add_icosphere(name=f"{fp}/face_center", radius=0.005,
                                           color=(255, 0, 0), position=fc)
            vis.server.scene.add_spline_catmull_rom(
                name=f"{fp}/face_normal", positions=np.array([fc, fc + fn * 0.05]),
                color=(0.0, 1.0, 0.0), line_width=LINE_WIDTH_NORMAL)

    vis.add_traj("tabletop_motion", {}, traj_dict)
    n_succ = sum(1 for p in trajs if p in succ)
    print(f"Loaded: {obj_name}  ({len(trajs)} candidates: "
          f"{n_succ} settled / {len(trajs) - n_succ} failed)")


def load_object(obj_name, show_motion):
    clear_scene()
    if show_motion:
        load_motion(obj_name)
    else:
        load_static(obj_name)


# ── Video recording ──────────────────────────────────────────────────────────
rec = {
    'active': False, 'view': None, 'temp_dir': None, 'idx': 0, 'total': 0,
    'width': 1280, 'height': 720, 'output': 'recording.mp4', 'fps': 30,
}


def _encode_recording():
    n = rec['idx']
    if n == 0:
        print("No frames captured.")
        return
    out = rec['output']
    print(f"Encoding {n} frames → {out} …")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "warning", "-framerate", str(rec['fps']),
        "-i", os.path.join(rec['temp_dir'], "frame_%05d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out,
    ], check=True)
    shutil.rmtree(rec['temp_dir'])
    rec['temp_dir'] = None
    print(f"Saved: {out}")


# ── GUI ────────────────────────────────────────────────────────────────────────
with vis.server.gui.add_folder("Object Selection"):
    obj_dropdown = vis.server.gui.add_dropdown(
        "Object", options=tuple(available_objects),
        initial_value=available_objects[0] if available_objects else "",
    )
    motion_checkbox = vis.server.gui.add_checkbox("Show settling motion", initial_value=False)
    load_btn = vis.server.gui.add_button("Load Object")

@load_btn.on_click
def _(_) -> None:
    load_object(obj_dropdown.value, motion_checkbox.value)

@motion_checkbox.on_update
def _(_) -> None:
    load_object(obj_dropdown.value, motion_checkbox.value)


with vis.server.gui.add_folder("Record Video"):
    gui_view_json  = vis.server.gui.add_text("View JSON",  initial_value="view.json")
    gui_output_mp4 = vis.server.gui.add_text("Output MP4", initial_value="recording.mp4")
    gui_vid_width  = vis.server.gui.add_number("Width",  initial_value=1280, min=640, max=3840)
    gui_vid_height = vis.server.gui.add_number("Height", initial_value=720,  min=480, max=2160)
    gui_vid_fps    = vis.server.gui.add_slider("FPS", min=10, max=60, step=1, initial_value=30)
    start_rec_btn  = vis.server.gui.add_button("Start Recording")
    stop_rec_btn   = vis.server.gui.add_button("Stop Recording", disabled=True)

@start_rec_btn.on_click
def _(_) -> None:
    view_json = gui_view_json.value
    if not os.path.exists(view_json):
        print(f"View file not found: {view_json} — save a view first.")
        return
    if not vis.num_frames:
        print("Nothing to record — enable 'Show settling motion' first.")
        return
    with open(view_json) as f:
        rec['view'] = json.load(f)
    rec['temp_dir'] = tempfile.mkdtemp()
    rec['idx']    = 0
    rec['total']  = vis.num_frames
    rec['width']  = int(gui_vid_width.value)
    rec['height'] = int(gui_vid_height.value)
    rec['output'] = gui_output_mp4.value
    rec['fps']    = int(gui_vid_fps.value)
    rec['active'] = True
    start_rec_btn.disabled = True
    stop_rec_btn.disabled  = False
    print(f"Recording started: {rec['total']} frames → {rec['output']}")

@stop_rec_btn.on_click
def _(_) -> None:
    rec['active'] = False


if available_objects:
    load_object(available_objects[0], False)

# ── Main loop ─────────────────────────────────────────────────────────────────
while True:
    if rec['active']:
        i = rec['idx']
        if i < rec['total']:
            clients = list(vis.server.get_clients().values())
            if clients:
                client = clients[0]
                vis.update_scene(i)
                vis.server.flush()
                client.camera.position = tuple(rec['view']['position'])
                client.camera.wxyz     = tuple(rec['view']['wxyz'])
                vis.capture_scene_png(
                    os.path.join(rec['temp_dir'], f"frame_{i:05d}.png"),
                    height=rec['height'], width=rec['width'])
                rec['idx'] += 1
                if (i + 1) % 20 == 0:
                    print(f"  {i + 1}/{rec['total']}")
            else:
                time.sleep(0.1)
        else:
            rec['active'] = False
            start_rec_btn.disabled = False
            stop_rec_btn.disabled  = True
            _encode_recording()
    else:
        if rec['temp_dir'] is not None:
            start_rec_btn.disabled = False
            stop_rec_btn.disabled  = True
            _encode_recording()
        vis.update()
