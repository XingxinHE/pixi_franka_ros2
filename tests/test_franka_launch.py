import importlib.util
from pathlib import Path

import pytest
import yaml


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "launch" / "franka.launch.py"
)
ASYNC_CONTROLLER_PROFILE = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "controllers.async_inference_overlay.yaml"
)


def load_launch_module():
    spec = importlib.util.spec_from_file_location("pixi_franka_launch", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_selects_with_hand_overlay_when_gripper_loaded():
    launch_module = load_launch_module()

    parameter_files = launch_module.resolve_controller_parameter_files(
        "config/controllers.yaml", load_gripper=True
    )

    assert parameter_files[0] == "config/controllers.yaml"
    assert len(parameter_files) == 2
    assert Path(parameter_files[1]).name == "controllers.with_hand_overlay.yaml"
    assert Path(parameter_files[1]).is_file()
    assert "end_effector_frame: fr3_hand_tcp" in Path(parameter_files[1]).read_text(
        encoding="utf-8"
    )


def test_selects_bare_flange_overlay_when_gripper_removed():
    launch_module = load_launch_module()

    parameter_files = launch_module.resolve_controller_parameter_files(
        "config/controllers.yaml", load_gripper=False
    )

    assert parameter_files[0] == "config/controllers.yaml"
    assert len(parameter_files) == 2
    assert Path(parameter_files[1]).name == "controllers.bare_flange_overlay.yaml"
    assert Path(parameter_files[1]).is_file()
    assert "end_effector_frame: fr3_link8" in Path(parameter_files[1]).read_text(
        encoding="utf-8"
    )


def test_inserts_async_profile_before_end_effector_overlay():
    launch_module = load_launch_module()

    parameter_files = launch_module.resolve_controller_parameter_files(
        "config/controllers.yaml",
        load_gripper=True,
        controller_profile_yaml=str(ASYNC_CONTROLLER_PROFILE),
    )

    assert parameter_files == [
        "config/controllers.yaml",
        str(ASYNC_CONTROLLER_PROFILE),
        launch_module.get_controller_overlay_path(load_gripper=True),
    ]
    profile = yaml.safe_load(ASYNC_CONTROLLER_PROFILE.read_text(encoding="utf-8"))[
        "/**"
    ]["cartesian_impedance_controller"]["ros__parameters"]
    assert set(profile) == {
        "use_operational_space",
        "operational_space_regularization",
        "task",
        "nullspace",
        "filter",
        "limit_error",
        "limit_torques",
        "max_delta_tau",
        "stop_commands",
        "log",
        "enable_introspection",
        "noise",
        "use_friction",
        "use_coriolis_compensation",
        "use_gravity_compensation",
        "use_local_jacobian",
        "joint_limit_repulsion",
        "variable_max_stiffness",
        "variable_stiffness",
        "async_inference_watchdog",
    }
    assert profile["task"] == {
        "k_pos_x": 250.0,
        "k_pos_y": 250.0,
        "k_pos_z": 250.0,
        "k_rot_x": 20.0,
        "k_rot_y": 20.0,
        "k_rot_z": 20.0,
        "d_pos_x": 35.0,
        "d_pos_y": 35.0,
        "d_pos_z": 35.0,
        "d_rot_x": 9.0,
        "d_rot_y": 9.0,
        "d_rot_z": 9.0,
        "error_clip": {
            "x": 0.1,
            "y": 0.1,
            "z": 0.1,
            "rx": 0.5,
            "ry": 0.5,
            "rz": 0.5,
        },
    }
    assert profile["filter"] == {
        "target_pose": 0.1,
        "q": 0.5,
        "dq": 0.5,
        "q_ref": 0.5,
        "output_torque": 0.5,
    }
    assert profile["nullspace"] == {
        "stiffness": 8.0,
        "damping": 5.0,
        "projector_type": "kinematic",
        "regularization": 1.0e-6,
        "max_tau": 5.0,
        "weights": {f"fr3_joint{joint}.value": 1.0 for joint in range(1, 8)},
    }
    assert profile["limit_error"] is True
    assert profile["limit_torques"] is True
    assert profile["max_delta_tau"] == 0.5
    assert profile["stop_commands"] is False
    assert profile["use_operational_space"] is False
    assert profile["operational_space_regularization"] == 0.01
    assert profile["use_friction"] is False
    assert profile["use_coriolis_compensation"] is True
    assert profile["use_gravity_compensation"] is False
    assert profile["use_local_jacobian"] is True
    assert profile["log"] == {
        "enabled": False,
        "robot_state": False,
        "control_values": False,
        "limits": False,
        "controller_parameters": False,
        "computed_torques": False,
        "dynamic_params": False,
        "timing": False,
    }
    assert profile["enable_introspection"] is False
    assert profile["noise"] == {
        "add_random_noise": False,
        "amplitude": 0.0,
    }
    assert profile["joint_limit_repulsion"] == {
        "enabled": True,
        "safe_range": 0.1,
        "max_torque": 5.0,
    }
    assert profile["variable_max_stiffness"] == {
        "translational": 900.0,
        "rotational": 60.0,
    }
    assert profile["variable_stiffness"] == {
        "enabled": False,
        "topic": "target_stiffness",
    }
    assert profile["async_inference_watchdog"] == {
        "enabled": True,
        "timeout_seconds": 0.25,
        "heartbeat_topic": "async_inference_heartbeat",
        "ack_topic": "async_inference_watchdog_ack",
        "status_topic": "async_inference_watchdog_status",
    }


def test_rejects_missing_controller_profile(tmp_path):
    launch_module = load_launch_module()
    missing_profile = tmp_path / "missing-controller-profile.yaml"

    with pytest.raises(FileNotFoundError, match="Controller profile file not found"):
        launch_module.resolve_controller_parameter_files(
            "config/controllers.yaml",
            load_gripper=True,
            controller_profile_yaml=str(missing_profile),
        )


def test_derives_robot_type_from_urdf_path_when_arm_id_is_empty():
    launch_module = load_launch_module()

    assert launch_module.resolve_robot_type("", "fr3/fr3.urdf.xacro") == "fr3"
