#include <array>
#include <limits>

#include <gtest/gtest.h>

#include "crisp_controllers/utils/target_pose_validation.hpp"

namespace {

using crisp_controllers::is_valid_target_pose;

constexpr std::array<double, 3> kValidTranslation = {0.4, -0.2, 0.7};
constexpr std::array<double, 4> kIdentityQuaternion = {0.0, 0.0, 0.0, 1.0};

TEST(TargetPoseValidationTest, AcceptsFiniteTranslationAndUnitQuaternion) {
  EXPECT_TRUE(is_valid_target_pose(kValidTranslation, kIdentityQuaternion));
  EXPECT_TRUE(
    is_valid_target_pose(kValidTranslation, {0.0, 0.0, 0.7071067811865476, 0.7071067811865476}));
}

TEST(TargetPoseValidationTest, RejectsNonFiniteTranslation) {
  const double nan = std::numeric_limits<double>::quiet_NaN();
  const double infinity = std::numeric_limits<double>::infinity();

  EXPECT_FALSE(is_valid_target_pose({nan, 0.0, 0.0}, kIdentityQuaternion));
  EXPECT_FALSE(is_valid_target_pose({0.0, infinity, 0.0}, kIdentityQuaternion));
  EXPECT_FALSE(is_valid_target_pose({0.0, 0.0, -infinity}, kIdentityQuaternion));
}

TEST(TargetPoseValidationTest, RejectsNonFiniteQuaternion) {
  const double nan = std::numeric_limits<double>::quiet_NaN();
  const double infinity = std::numeric_limits<double>::infinity();

  EXPECT_FALSE(is_valid_target_pose(kValidTranslation, {nan, 0.0, 0.0, 1.0}));
  EXPECT_FALSE(is_valid_target_pose(kValidTranslation, {0.0, infinity, 0.0, 1.0}));
  EXPECT_FALSE(is_valid_target_pose(kValidTranslation, {0.0, 0.0, -infinity, 1.0}));
  EXPECT_FALSE(is_valid_target_pose(kValidTranslation, {0.0, 0.0, 0.0, nan}));
}

TEST(TargetPoseValidationTest, RejectsZeroAndNonUnitQuaternions) {
  EXPECT_FALSE(is_valid_target_pose(kValidTranslation, {0.0, 0.0, 0.0, 0.0}));
  EXPECT_FALSE(is_valid_target_pose(kValidTranslation, {0.0, 0.0, 0.0, 2.0}));
  EXPECT_FALSE(is_valid_target_pose(kValidTranslation, {0.0, 0.0, 0.0, 0.9}));
}

}  // namespace

int main(int argc, char ** argv) {
  testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
