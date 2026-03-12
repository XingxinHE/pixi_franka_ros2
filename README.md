
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
```
