
## Reproducibility

This repository pins upstream source repositories to:

- `franka_ros2`: `v2.2.0`
- `libfranka`: `0.19.0`
- `franka_description`: `1.3.0`
- `crisp_controllers`: `v2.1.0`

## Get Started

```bash
# Terminal 1
pixi install
pixi run -e humble setup
pixi run -e humble franka robot_ip:=172.16.0.3 load_gripper:=true controllers_yaml:=config/controllers.yaml
pixi run -e humble franka robot_ip:=172.16.0.55 load_gripper:=true controllers_yaml:=config/controllers.yaml
pixi run -e humble franka robot_ip:=172.16.0.3 load_gripper:=false controllers_yaml:=config/controllers.yaml
```

Dual FR3 bringup (leader/follower on same RT PC):

```bash
# Terminal 1
pixi run -e humble franka-dual \
  leader_robot_ip:=172.16.0.33 \
  follower_robot_ip:=172.16.0.3 \
  leader_namespace:=left \
  follower_namespace:=right \
  load_gripper:=true \
  controllers_yaml:=config/controllers.yaml
```

When `load_gripper:=true`, this launch now also starts a CRISP compatibility adapter that exposes:

- `/gripper/joint_states`
- `/gripper/gripper_position_controller/commands`

bridged to Franka's native gripper interfaces.

- `load_gripper:=true` keeps the controller end-effector at `fr3_hand_tcp`
- `load_gripper:=false` switches the controller end-effector to the bare flange `fr3_link8`

If the Franka Hand is physically removed, use the same bringup command with `load_gripper:=false`:

```bash
pixi run -e humble franka robot_ip:=172.16.0.3 load_gripper:=false controllers_yaml:=config/controllers.yaml
```
```bash
# Terminal 2
pixi run -e humble python examples/crisp_figure_eight.py
```



```bash
# Switch controller mode
# WARNING!! Stop the SpaceMouse publisher first before switching the controller
pixi run -e humble ros2 control switch_controllers --activate cartesian_impedance_controller

# Switch to joint impedance controller
pixi run -e humble ros2 control switch_controllers --activate joint_impedance_controller

# Switch to gravity compensation mode, i.e. make the robot kinaesthetic teaching
pixi run -e humble ros2 control switch_controllers --activate gravity_compensation
```



CRISP_VISER_EE=flange pixi run -e humble python examples/crisp_viser.py
