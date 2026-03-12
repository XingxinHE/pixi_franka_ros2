# Allow callers to override these before activation.
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-100}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_zenoh_cpp}"

# Keep launch logs in a writable location by default.
if [ -z "${ROS_LOG_DIR:-}" ]; then
  export ROS_LOG_DIR="${TMPDIR:-/tmp}/ros-log"
fi

mkdir -p "${ROS_LOG_DIR}"
