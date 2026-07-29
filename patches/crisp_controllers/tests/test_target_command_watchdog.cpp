#include <cstdint>

#include <gtest/gtest.h>

#include "crisp_controllers/utils/target_command_watchdog.hpp"

namespace {

using crisp_controllers::auxiliary_target_commands_allowed;
using crisp_controllers::LatestTargetCommandAcknowledgement;
using crisp_controllers::TargetCommandWatchdog;
using crisp_controllers::TargetCommandWatchdogEvent;

constexpr std::uint64_t kTimeoutNs = 250;

TEST(AsyncInferenceCommandPolicyTest, AllowsOnlyPoseTargetsInAsyncMode) {
  EXPECT_TRUE(auxiliary_target_commands_allowed(false));
  EXPECT_FALSE(auxiliary_target_commands_allowed(true));
}

TEST(LatestTargetCommandAcknowledgementTest, NewValueSupersedesAContendedPublish) {
  LatestTargetCommandAcknowledgement acknowledgement;
  acknowledgement.request(100);
  ASSERT_TRUE(acknowledgement.pending());
  ASSERT_EQ(acknowledgement.value(), 100U);

  acknowledgement.request(101);
  EXPECT_TRUE(acknowledgement.pending());
  EXPECT_EQ(acknowledgement.value(), 101U);

  acknowledgement.mark_published();
  EXPECT_FALSE(acknowledgement.pending());
}

TEST(TargetCommandWatchdogTest, DisabledWatchdogNeverTrips) {
  TargetCommandWatchdog watchdog;
  watchdog.note_command(1, 100);

  const auto first = watchdog.update(1000, false, kTimeoutNs);
  EXPECT_TRUE(first.has_new_command);
  EXPECT_FALSE(first.timed_out);
  EXPECT_EQ(first.event, TargetCommandWatchdogEvent::kNone);

  const auto second = watchdog.update(2000, false, kTimeoutNs);
  EXPECT_FALSE(second.has_new_command);
  EXPECT_FALSE(second.timed_out);
  EXPECT_EQ(second.event, TargetCommandWatchdogEvent::kNone);
}

TEST(TargetCommandWatchdogTest, RemainsDisarmedUntilFirstPostResetCommand) {
  TargetCommandWatchdog watchdog;
  watchdog.note_command(1, 100);
  watchdog.reset_ignoring_existing_commands();

  const auto ignored = watchdog.update(1000, true, kTimeoutNs);
  EXPECT_FALSE(ignored.has_new_command);
  EXPECT_FALSE(ignored.timed_out);

  watchdog.note_command(2, 1100);
  const auto armed = watchdog.update(1100, true, kTimeoutNs);
  EXPECT_TRUE(armed.has_new_command);
  EXPECT_EQ(armed.accepted_command_value, 2U);
  EXPECT_TRUE(armed.armed);
  EXPECT_FALSE(armed.timed_out);
}

TEST(TargetCommandWatchdogTest, TripsAtExactTimeoutAndOnlyReportsTransitionOnce) {
  TargetCommandWatchdog watchdog;
  watchdog.note_command(1, 100);

  EXPECT_FALSE(watchdog.update(100, true, kTimeoutNs).timed_out);
  EXPECT_FALSE(watchdog.update(349, true, kTimeoutNs).timed_out);

  const auto timed_out = watchdog.update(350, true, kTimeoutNs);
  EXPECT_TRUE(timed_out.timed_out);
  EXPECT_EQ(timed_out.event, TargetCommandWatchdogEvent::kTimedOut);

  const auto remains_timed_out = watchdog.update(600, true, kTimeoutNs);
  EXPECT_TRUE(remains_timed_out.timed_out);
  EXPECT_EQ(remains_timed_out.event, TargetCommandWatchdogEvent::kNone);
}

TEST(TargetCommandWatchdogTest, FreshCommandCannotRecoverLatchedTimeout) {
  TargetCommandWatchdog watchdog;
  watchdog.note_command(1, 100);
  ASSERT_EQ(watchdog.update(350, true, kTimeoutNs).event, TargetCommandWatchdogEvent::kTimedOut);

  watchdog.note_command(2, 400);
  const auto still_timed_out = watchdog.update(401, true, kTimeoutNs);
  EXPECT_TRUE(still_timed_out.has_new_command);
  EXPECT_TRUE(still_timed_out.timed_out);
  EXPECT_EQ(still_timed_out.event, TargetCommandWatchdogEvent::kNone);
}

TEST(TargetCommandWatchdogTest, StalledControlLoopWithoutHeartbeatTimesOut) {
  TargetCommandWatchdog watchdog;
  watchdog.note_command(1, 100);
  ASSERT_FALSE(watchdog.update(200, true, kTimeoutNs).timed_out);

  const auto timed_out = watchdog.update(350, true, kTimeoutNs);
  EXPECT_FALSE(timed_out.has_new_command);
  EXPECT_TRUE(timed_out.timed_out);
  EXPECT_EQ(timed_out.event, TargetCommandWatchdogEvent::kTimedOut);
}

TEST(TargetCommandWatchdogTest, DuplicateAndOutOfOrderHeartbeatsDoNotRefreshLease) {
  TargetCommandWatchdog watchdog;
  watchdog.note_command(10, 100);
  ASSERT_FALSE(watchdog.update(100, true, kTimeoutNs).timed_out);

  watchdog.note_command(10, 300);
  const auto duplicate = watchdog.update(300, true, kTimeoutNs);
  EXPECT_FALSE(duplicate.has_new_command);
  EXPECT_EQ(duplicate.accepted_command_value, 0U);
  EXPECT_FALSE(duplicate.timed_out);

  watchdog.note_command(9, 340);
  const auto out_of_order = watchdog.update(340, true, kTimeoutNs);
  EXPECT_FALSE(out_of_order.has_new_command);
  EXPECT_FALSE(out_of_order.timed_out);

  const auto timed_out = watchdog.update(350, true, kTimeoutNs);
  EXPECT_TRUE(timed_out.timed_out);
  EXPECT_EQ(timed_out.event, TargetCommandWatchdogEvent::kTimedOut);
}

TEST(TargetCommandWatchdogTest, PublisherRestartRequiresLifecycleReset) {
  TargetCommandWatchdog watchdog;
  watchdog.note_command(1'000'000, 100);
  ASSERT_TRUE(watchdog.update(350, true, kTimeoutNs).timed_out);

  watchdog.note_command(2'000'000, 400);
  ASSERT_TRUE(watchdog.update(401, true, kTimeoutNs).timed_out);

  watchdog.reset_ignoring_existing_commands();
  const auto reset = watchdog.update(1000, true, kTimeoutNs);
  EXPECT_FALSE(reset.has_new_command);
  EXPECT_FALSE(reset.timed_out);

  // The lifecycle boundary starts a new numeric epoch, so a restarted publisher may begin lower.
  watchdog.note_command(1, 1100);
  const auto rearmed = watchdog.update(1101, true, kTimeoutNs);
  EXPECT_TRUE(rearmed.has_new_command);
  EXPECT_EQ(rearmed.accepted_command_value, 1U);
  EXPECT_FALSE(rearmed.timed_out);
}

TEST(TargetCommandWatchdogTest, DisablingCannotClearLatchedTimeout) {
  TargetCommandWatchdog watchdog;
  watchdog.note_command(1, 100);
  ASSERT_TRUE(watchdog.update(350, true, kTimeoutNs).timed_out);

  const auto disabled = watchdog.update(351, false, kTimeoutNs);
  EXPECT_TRUE(disabled.timed_out);
  EXPECT_EQ(disabled.event, TargetCommandWatchdogEvent::kNone);

  const auto reenabled_with_stale_command = watchdog.update(352, true, kTimeoutNs);
  EXPECT_TRUE(reenabled_with_stale_command.timed_out);
  EXPECT_EQ(reenabled_with_stale_command.event, TargetCommandWatchdogEvent::kNone);
}

TEST(TargetCommandWatchdogTest, FutureReceiptDoesNotUnderflowElapsedTime) {
  TargetCommandWatchdog watchdog;
  watchdog.note_command(1, 500);

  const auto update = watchdog.update(400, true, kTimeoutNs);
  EXPECT_TRUE(update.has_new_command);
  EXPECT_FALSE(update.timed_out);
  EXPECT_EQ(update.event, TargetCommandWatchdogEvent::kNone);
}

TEST(TargetCommandWatchdogTest, AlreadyStaleFirstCommandTripsImmediately) {
  TargetCommandWatchdog watchdog;
  watchdog.note_command(1, 100);

  const auto update = watchdog.update(350, true, kTimeoutNs);
  EXPECT_TRUE(update.has_new_command);
  EXPECT_TRUE(update.timed_out);
  EXPECT_EQ(update.event, TargetCommandWatchdogEvent::kTimedOut);
}

}  // namespace

int main(int argc, char ** argv) {
  testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
