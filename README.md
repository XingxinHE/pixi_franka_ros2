A simple demo on zero gravity of Franka Research 3 robot.

## Versioning

This repository pins repositories to:

- `franka_ros2`: `v2.2.0`
- `libfranka`: `0.19.0`
- `franka_description`: `1.3.0`
- `crisp_controllers`: `v2.1.0`

It has been tested on `Franka System Image == 5.9.1` and `Franka Arm == Arm3R`.

## Get Started

```bash
# Terminal 1: setup + bring up
pixi install
pixi run -e humble setup
pixi run -e humble franka robot_ip:=172.16.0.3 load_gripper:=true controllers_yaml:=config/controllers.yaml
```

```bash
# Terminal 2: activate the zero gravity controller
pixi run -e humble ros2 control switch_controllers --activate gravity_compensation
```

```bash
# Terminal 3: inspect the joint states
pixi run -e humble ros2 topic echo /franka/joint_states --once
```
