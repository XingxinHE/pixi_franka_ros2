#!/usr/bin/env python3
"""Bridge CRISP gripper topics to Franka gripper actions.

Provides CRISP-compatible interfaces:
- subscribe: /gripper/gripper_position_controller/commands (Float64MultiArray)
- publish:   /gripper/joint_states (JointState, normalized [0,1])

Backed by Franka interfaces:
- subscribe: /franka_gripper/joint_states
- action:    /franka_gripper/grasp
"""

from __future__ import annotations

import argparse

import rclpy
from franka_msgs.action import Grasp

try:
    from franka_msgs.action import Move
except Exception:  # noqa: BLE001
    Move = None  # type: ignore[assignment]
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from rclpy.qos import qos_profile_system_default
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray


def _join_topic(namespace: str, relative: str) -> str:
    ns = namespace.strip("/")
    rel = relative.strip("/")
    return f"/{ns}/{rel}" if ns else f"/{rel}"


class CrispPyFrankaHandAdapter(Node):
    def __init__(self, namespace: str = ""):
        super().__init__("crisp_py_franka_hand_adapter")
        self._cb_group = ReentrantCallbackGroup()

        # CRISP shim topics expected by crisp_py gripper_franka config.
        self._command_topic = _join_topic(
            namespace, "gripper/gripper_position_controller/commands"
        )
        self._joint_state_topic = _join_topic(namespace, "gripper/joint_states")

        # Franka-native topics/actions.
        self._franka_joint_state_topic = _join_topic(
            namespace, "franka_gripper/joint_states"
        )
        self._franka_grasp_action = _join_topic(namespace, "franka_gripper/grasp")
        self._franka_move_action = _join_topic(namespace, "franka_gripper/move")

        self._open_width = 0.08
        self._close_width = 0.0
        self._toggle_threshold = 0.5
        self._speed = 0.1
        self._force = 50.0
        self._epsilon_inner = 0.01
        self._epsilon_outer = 0.01

        self._current_width: float | None = None
        self._last_discrete_command: str | None = None
        self._goal_in_flight = False

        self._grasp_client = ActionClient(
            self,
            Grasp,
            self._franka_grasp_action,
            callback_group=self._cb_group,
        )
        self._move_client = (
            ActionClient(
                self,
                Move,
                self._franka_move_action,
                callback_group=self._cb_group,
            )
            if Move is not None
            else None
        )

        self.create_subscription(
            Float64MultiArray,
            self._command_topic,
            self._command_callback,
            qos_profile=qos_profile_system_default,
            callback_group=self._cb_group,
        )
        self.create_subscription(
            JointState,
            self._franka_joint_state_topic,
            self._franka_joint_state_callback,
            qos_profile=qos_profile_system_default,
            callback_group=self._cb_group,
        )

        self._joint_state_publisher = self.create_publisher(
            JointState,
            self._joint_state_topic,
            qos_profile=qos_profile_system_default,
            callback_group=self._cb_group,
        )

        self.create_timer(
            1.0 / 50.0, self._publish_crisp_joint_state, callback_group=self._cb_group
        )

        self.get_logger().info(
            "CRISP Franka hand adapter started: cmd=%s, state=%s, franka_state=%s, franka_grasp=%s, franka_move=%s"
            % (
                self._command_topic,
                self._joint_state_topic,
                self._franka_joint_state_topic,
                self._franka_grasp_action,
                self._franka_move_action
                if self._move_client is not None
                else "<not available>",
            )
        )

    def _wait_server(self, client: ActionClient | None, action_name: str) -> bool:
        if client is None:
            return False
        if client.server_is_ready():
            return True
        if not client.wait_for_server(timeout_sec=1.0):
            self.get_logger().warn(
                f"{action_name} not ready. Ignoring gripper command.",
                throttle_duration_sec=2.0,
            )
            return False
        return True

    def _franka_joint_state_callback(self, msg: JointState) -> None:
        if len(msg.position) >= 2:
            self._current_width = float(msg.position[0] + msg.position[1])

    def _publish_crisp_joint_state(self) -> None:
        if self._current_width is None or self._open_width <= 0.0:
            return

        crisp_joint = JointState()
        crisp_joint.header.stamp = self.get_clock().now().to_msg()
        crisp_joint.name = ["gripper_joint"]
        crisp_joint.position = [self._current_width / self._open_width]
        crisp_joint.effort = [0.0]
        self._joint_state_publisher.publish(crisp_joint)

    def _command_callback(self, msg: Float64MultiArray) -> None:
        if not msg.data:
            return

        command = float(msg.data[0])

        # Commands can come either as normalized [0,1] (legacy crisp_py config)
        # or as width in meters [0, 0.08] (current FR3 env configs).
        if command <= self._open_width + 1e-6:
            normalized = command / self._open_width if self._open_width > 0.0 else 0.0
        else:
            normalized = command

        should_close = normalized <= self._toggle_threshold
        discrete_command = "close" if should_close else "open"

        if discrete_command == self._last_discrete_command:
            return

        if should_close:
            if not self._wait_server(self._grasp_client, self._franka_grasp_action):
                return
            self._send_grasp(self._close_width)
        else:
            # Prefer Move action for opening; fallback to Grasp if Move is unavailable.
            if self._move_client is not None and self._wait_server(
                self._move_client, self._franka_move_action
            ):
                self._send_move(self._open_width)
            else:
                if not self._wait_server(self._grasp_client, self._franka_grasp_action):
                    return
                self._send_grasp(self._open_width)
        self._last_discrete_command = discrete_command

    def _send_grasp(self, width: float) -> None:
        if self._goal_in_flight:
            self.get_logger().warn(
                "Previous gripper goal still in flight; dropping command.",
                throttle_duration_sec=1.0,
            )
            return

        goal = Grasp.Goal()
        goal.width = width
        goal.speed = self._speed
        goal.force = self._force
        goal.epsilon.inner = self._epsilon_inner
        goal.epsilon.outer = self._epsilon_outer

        self._goal_in_flight = True
        future = self._grasp_client.send_goal_async(goal)
        future.add_done_callback(self._goal_response_callback)

    def _send_move(self, width: float) -> None:
        if self._goal_in_flight:
            self.get_logger().warn(
                "Previous gripper goal still in flight; dropping command.",
                throttle_duration_sec=1.0,
            )
            return
        if self._move_client is None or Move is None:
            return

        goal = Move.Goal()
        goal.width = width
        goal.speed = self._speed

        self._goal_in_flight = True
        future = self._move_client.send_goal_async(goal)
        future.add_done_callback(self._goal_response_callback)

    def _goal_response_callback(self, future) -> None:  # noqa: ANN001
        try:
            goal_handle = future.result()
        except Exception as exc:  # noqa: BLE001
            self._goal_in_flight = False
            self._last_discrete_command = None
            self.get_logger().warn(f"Franka gripper goal send failed: {exc}")
            return

        if goal_handle is None or not goal_handle.accepted:
            self._goal_in_flight = False
            self._last_discrete_command = None
            self.get_logger().warn(
                "Franka gripper goal rejected; command state reset.",
                throttle_duration_sec=1.0,
            )
            return

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._goal_result_callback)

    def _goal_result_callback(self, future) -> None:  # noqa: ANN001
        self._goal_in_flight = False
        try:
            result_msg = future.result()
        except Exception as exc:  # noqa: BLE001
            self._last_discrete_command = None
            self.get_logger().warn(f"Franka gripper result retrieval failed: {exc}")
            return

        if result_msg is None or not getattr(result_msg.result, "success", False):
            self._last_discrete_command = None
            self.get_logger().warn(
                "Franka gripper action reported failure; command state reset.",
                throttle_duration_sec=1.0,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="CRISP Franka hand adapter")
    parser.add_argument(
        "--namespace", type=str, default="", help="Optional ROS namespace"
    )
    args = parser.parse_args()

    rclpy.init()
    node = CrispPyFrankaHandAdapter(namespace=args.namespace)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
