#pragma once

#include <array>
#include <cmath>

namespace crisp_controllers {

constexpr double kUnitQuaternionSquaredNormTolerance = 1.0e-3;

/**
 * @brief Validate a Cartesian target before it can enter the controller's realtime buffer.
 *
 * The quaternion is ordered x, y, z, w. A valid target has finite translation and quaternion
 * components and a quaternion whose squared norm is close to one.
 */
[[nodiscard]] inline bool is_valid_target_pose(
  const std::array<double, 3> & translation,
  const std::array<double, 4> & quaternion_xyzw) noexcept {
  for (const double component : translation) {
    if (!std::isfinite(component)) {
      return false;
    }
  }

  double quaternion_squared_norm = 0.0;
  for (const double component : quaternion_xyzw) {
    if (!std::isfinite(component)) {
      return false;
    }
    quaternion_squared_norm += component * component;
  }

  return std::isfinite(quaternion_squared_norm) &&
    std::abs(quaternion_squared_norm - 1.0) <= kUnitQuaternionSquaredNormTolerance;
}

}  // namespace crisp_controllers
