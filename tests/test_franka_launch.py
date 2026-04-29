import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "launch" / "franka.launch.py"
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
    assert Path(parameter_files[1]).name == "controllers.bare_flange_overlay.yaml"
    assert Path(parameter_files[1]).is_file()
    assert "end_effector_frame: fr3_link8" in Path(parameter_files[1]).read_text(
        encoding="utf-8"
    )


def test_derives_robot_type_from_urdf_path_when_arm_id_is_empty():
    launch_module = load_launch_module()

    assert launch_module.resolve_robot_type("", "fr3/fr3.urdf.xacro") == "fr3"
