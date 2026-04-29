from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
from typing import Literal

import numpy as np
from ament_index_python.packages import get_package_share_directory
from robot_descriptions.loaders.yourdfpy import load_robot_description
from scipy.spatial.transform import Rotation
import viser
from viser.extras import ViserUrdf
import xacro

from crisp_py.config.path import find_config
from crisp_py.robot import make_robot
from crisp_py.utils.geometry import Pose


FRANKA_ROBOT_TYPES = {"fr3", "panda"}
PYLIBFRANKA_REFERENCE_MATRIX = np.array(
    [
        [7.06629515e-01, -7.07583249e-01, -8.01872869e-04, 3.07247102e-01],
        [-7.07583547e-01, -7.06629694e-01, -6.39656500e-05, -2.44413008e-04],
        [-5.21366135e-04, 6.12592034e-04, -9.99999702e-01, 5.90142131e-01],
        [0.0, 0.0, 0.0, 1.0],
    ]
)


def get_description_name(robot_type: str) -> str:
    if robot_type in ["fr3", "panda"]:
        return "panda_description"
    if robot_type in ["iiwa", "iiwa14"]:
        return "iiwa14_description"
    return f"{robot_type}_description"


def get_end_effector_mode(robot_type: str) -> Literal["hand", "flange"]:
    raw_mode = os.getenv("CRISP_VISER_EE")
    if raw_mode is None:
        return "hand" if robot_type in FRANKA_ROBOT_TYPES else "flange"

    end_effector_mode = raw_mode.lower()
    if end_effector_mode not in {"hand", "flange"}:
        raise ValueError("CRISP_VISER_EE must be either 'hand' or 'flange'.")
    if robot_type not in FRANKA_ROBOT_TYPES and end_effector_mode == "hand":
        raise ValueError(
            f"CRISP_VISER_EE=hand is only supported for {sorted(FRANKA_ROBOT_TYPES)}."
        )
    return end_effector_mode  # type: ignore[return-value]


def get_target_frame(
    robot_type: str, end_effector_mode: Literal["hand", "flange"]
) -> str | None:
    if robot_type == "fr3":
        return "fr3_hand_tcp" if end_effector_mode == "hand" else "fr3_link8"
    if robot_type == "panda":
        return "panda_hand_tcp" if end_effector_mode == "hand" else "panda_link8"
    return None


def should_add_gripper_to_config(
    robot_type: str, end_effector_mode: Literal["hand", "flange"]
) -> bool:
    return robot_type in FRANKA_ROBOT_TYPES and end_effector_mode == "hand"


def load_urdf(robot_type: str, end_effector_mode: Literal["hand", "flange"]):
    if robot_type not in FRANKA_ROBOT_TYPES:
        return load_robot_description(get_description_name(robot_type))

    franka_description_share = Path(get_package_share_directory("franka_description"))
    xacro_path = (
        franka_description_share / "robots" / robot_type / f"{robot_type}.urdf.xacro"
    )
    robot_description = xacro.process_file(
        str(xacro_path),
        mappings={"hand": "true" if end_effector_mode == "hand" else "false"},
    ).toprettyxml(indent="  ")
    robot_description = robot_description.replace(
        "package://franka_description/", f"{franka_description_share.as_posix()}/"
    )

    urdf_file = (
        Path(tempfile.gettempdir())
        / f"crisp_viser_{robot_type}_{end_effector_mode}.urdf"
    )
    urdf_file.write_text(robot_description, encoding="utf-8")
    return urdf_file


robot_type: Literal["fr3", "panda", "iiwa14"] = os.getenv("CRISP_VISER_ROBOT", "fr3")  # type: ignore[assignment]
home_time = float(os.getenv("CRISP_VISER_HOME_TIME", "2.0"))
viser_port = int(os.getenv("CRISP_VISER_PORT", "8080"))
controller_config = "control/default_cartesian_impedance.yaml"
end_effector_mode = get_end_effector_mode(robot_type)
target_frame = get_target_frame(robot_type, end_effector_mode)

robot_kwargs = {"target_frame": target_frame} if target_frame is not None else {}
robot = make_robot(robot_type, **robot_kwargs)
robot.wait_until_ready()

robot.config.time_to_home = home_time
robot.home()
start_pose = robot.end_effector_pose

robot.controller_switcher_client.switch_controller("cartesian_impedance_controller")
param_file = find_config(controller_config)
if param_file is None:
    raise FileNotFoundError(
        f"Could not find {controller_config} in CRISP config paths."
    )
robot.cartesian_controller_parameters_client.load_param_config(file_path=param_file)

server = viser.ViserServer(port=viser_port)

urdf = load_urdf(robot_type, end_effector_mode)
viser_urdf = ViserUrdf(
    server,
    urdf_or_path=urdf,
    load_meshes=True,
    load_collision_meshes=False,
    collision_mesh_color_override=(1.0, 0.0, 0.0, 0.5),
)

with server.gui.add_folder("Visibility"):
    show_meshes_cb = server.gui.add_checkbox("Show meshes", viser_urdf.show_visual)
    show_collision_meshes_cb = server.gui.add_checkbox(
        "Show collision meshes", viser_urdf.show_collision
    )
    show_pylibfranka_frame_cb = server.gui.add_checkbox("Show pylibfranka frame", True)


@show_meshes_cb.on_update
def _(_):
    viser_urdf.show_visual = show_meshes_cb.value


@show_collision_meshes_cb.on_update
def _(_):
    viser_urdf.show_collision = show_collision_meshes_cb.value


show_meshes_cb.visible = True
show_collision_meshes_cb.visible = False

actuation = (
    np.array([*robot.joint_values, 0.0])
    if should_add_gripper_to_config(robot_type, end_effector_mode)
    else np.array(robot.joint_values)
)
viser_urdf.update_cfg(actuation)

trimesh_scene = viser_urdf._urdf.scene or viser_urdf._urdf.collision_scene
grid_z = 0.0
if trimesh_scene is not None and trimesh_scene.bounds is not None:
    grid_z = float(trimesh_scene.bounds[0, 2])

server.scene.add_grid(
    "/grid",
    width=2,
    height=2,
    position=(0.0, 0.0, grid_z),
)

pylibfranka_rotation = Rotation.from_matrix(PYLIBFRANKA_REFERENCE_MATRIX[:3, :3])
pylibfranka_frame = server.scene.add_frame(
    "/pylibfranka_reference",
    position=tuple(PYLIBFRANKA_REFERENCE_MATRIX[:3, 3]),
    wxyz=tuple(pylibfranka_rotation.as_quat(scalar_first=True)),
    axes_length=0.12,
    axes_radius=0.004,
    origin_radius=0.01,
)


@show_pylibfranka_frame_cb.on_update
def _(_):
    pylibfranka_frame.visible = show_pylibfranka_frame_cb.value


transform_handle = server.scene.add_transform_controls(
    "/end_effector_target",
    position=start_pose.position,
    wxyz=start_pose.orientation.as_quat(scalar_first=True),
    scale=0.3,
    line_width=3.0,
)


@transform_handle.on_update
def update_robot_target(handle: viser.TransformControlsEvent) -> None:
    rot = Rotation.from_quat(handle.target.wxyz, scalar_first=True)
    pose = Pose(position=handle.target.position, orientation=rot)
    robot.set_target(pose=pose)


print(
    "Viser teleop is running at "
    f"http://localhost:{viser_port} "
    f"(robot={robot_type}, ee={end_effector_mode}, target_frame={robot.config.target_frame})"
)

while True:
    actuation = (
        np.array([*robot.joint_values, 0.0])
        if should_add_gripper_to_config(robot_type, end_effector_mode)
        else np.array(robot.joint_values)
    )
    viser_urdf.update_cfg(actuation)
    time.sleep(0.01)
