from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from pathlib import Path


def _franka_include(namespace_arg: str, ip_arg: str, arm_prefix_arg: str):
    local_franka_launch = str(Path(__file__).resolve().parent / "franka.launch.py")
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(local_franka_launch),
        launch_arguments={
            "arm_id": "fr3",
            "arm_prefix": LaunchConfiguration(arm_prefix_arg),
            "namespace": LaunchConfiguration(namespace_arg),
            "robot_ip": LaunchConfiguration(ip_arg),
            "load_gripper": LaunchConfiguration("load_gripper"),
            "use_fake_hardware": LaunchConfiguration("use_fake_hardware"),
            "controllers_yaml": LaunchConfiguration("controllers_yaml"),
        }.items(),
    )


def generate_launch_description():
    launch_args = [
        DeclareLaunchArgument("leader_namespace", default_value="left"),
        DeclareLaunchArgument("follower_namespace", default_value="right"),
        # Keep arm_prefix empty by default.
        # We isolate robots by namespace, and controllers.yaml uses unprefixed FR3 joint names.
        DeclareLaunchArgument("leader_arm_prefix", default_value=""),
        DeclareLaunchArgument("follower_arm_prefix", default_value=""),
        DeclareLaunchArgument("leader_robot_ip", default_value="172.16.0.33"),
        DeclareLaunchArgument("follower_robot_ip", default_value="172.16.0.3"),
        DeclareLaunchArgument("load_gripper", default_value="true"),
        DeclareLaunchArgument("use_fake_hardware", default_value="false"),
        DeclareLaunchArgument(
            "controllers_yaml", default_value="config/controllers.yaml"
        ),
    ]

    leader = _franka_include("leader_namespace", "leader_robot_ip", "leader_arm_prefix")
    follower = _franka_include(
        "follower_namespace", "follower_robot_ip", "follower_arm_prefix"
    )

    return LaunchDescription(launch_args + [leader, follower])
