
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