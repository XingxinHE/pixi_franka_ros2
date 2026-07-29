#pragma once

#include <atomic>
#include <cstdint>

namespace crisp_controllers {

enum class TargetCommandWatchdogEvent {
  kNone,
  kTimedOut,
};

struct TargetCommandWatchdogUpdate {
  bool has_new_command;
  std::uint64_t accepted_command_value;
  bool armed;
  bool timed_out;
  TargetCommandWatchdogEvent event;
};

/**
 * @brief Whether non-pose target channels may affect the controller.
 *
 * Async inference intentionally has a pose-only command contract. Joint, wrench, and
 * topic-stiffness targets remain available to legacy deployments where the watchdog is disabled.
 */
[[nodiscard]] constexpr bool
auxiliary_target_commands_allowed(bool async_inference_watchdog_enabled) noexcept {
  return !async_inference_watchdog_enabled;
}

/**
 * @brief Realtime-loop-owned latest-value state for non-blocking heartbeat acknowledgements.
 */
class LatestTargetCommandAcknowledgement {
public:
  void request(std::uint64_t command_value) noexcept {
    value_ = command_value;
    pending_ = true;
  }

  void mark_published() noexcept { pending_ = false; }

  void reset() noexcept {
    value_ = 0;
    pending_ = false;
  }

  [[nodiscard]] bool pending() const noexcept { return pending_; }

  [[nodiscard]] std::uint64_t value() const noexcept { return value_; }

private:
  std::uint64_t value_{0};
  bool pending_{false};
};

/**
 * @brief Realtime-safe state machine for detecting stale target commands.
 *
 * The non-realtime command callback calls note_command() after accepting and buffering a command.
 * The realtime update loop calls update() and owns the remaining mutable state.
 */
class TargetCommandWatchdog {
public:
  /**
   * @brief Record a candidate command heartbeat and its monotonic local receipt timestamp.
   *
   * The command value must increase strictly. Duplicate and out-of-order values are observed but
   * do not refresh the lease.
   */
  void note_command(std::uint64_t command_value, std::uint64_t receipt_time_ns) noexcept {
    // This mailbox has one non-realtime writer: the subscription's mutually-exclusive callback.
    mailbox_version_.fetch_add(1, std::memory_order_acq_rel);
    latest_command_value_.store(command_value, std::memory_order_relaxed);
    latest_receipt_time_ns_.store(receipt_time_ns, std::memory_order_relaxed);
    mailbox_version_.fetch_add(1, std::memory_order_release);
  }

  /**
   * @brief Disarm and ignore every command received before this lifecycle boundary.
   */
  void reset_ignoring_existing_commands() noexcept {
    std::uint64_t version_before;
    std::uint64_t version_after;
    while (true) {
      version_before = mailbox_version_.load(std::memory_order_acquire);
      if ((version_before & 1U) != 0U) {
        continue;
      }
      last_accepted_command_value_ = latest_command_value_.load(std::memory_order_relaxed);
      last_accepted_receipt_time_ns_ = latest_receipt_time_ns_.load(std::memory_order_relaxed);
      version_after = mailbox_version_.load(std::memory_order_acquire);
      if (version_before == version_after) {
        break;
      }
    }

    observed_mailbox_version_ = version_after;
    // The existing mailbox sample is ignored by version. The first new sample starts a fresh
    // numeric epoch, allowing a restarted publisher to recover after an explicit lifecycle reset.
    has_accepted_command_value_ = false;
    armed_ = false;
    timed_out_ = false;
  }

  /**
   * @brief Observe new commands and advance the watchdog state.
   *
   * Commands are tracked while disabled so dynamically enabling the watchdog uses the latest local
   * receipt time. The watchdog remains disarmed until a command is received after the last reset.
   */
  [[nodiscard]] TargetCommandWatchdogUpdate
  update(std::uint64_t now_ns, bool enabled, std::uint64_t timeout_ns) noexcept {
    bool has_new_command = false;
    std::uint64_t accepted_command_value = 0;
    const std::uint64_t version_before = mailbox_version_.load(std::memory_order_acquire);
    if (version_before != observed_mailbox_version_ && (version_before & 1U) == 0U) {
      const std::uint64_t command_value = latest_command_value_.load(std::memory_order_relaxed);
      const std::uint64_t receipt_time_ns = latest_receipt_time_ns_.load(std::memory_order_relaxed);
      const std::uint64_t version_after = mailbox_version_.load(std::memory_order_acquire);
      if (version_before == version_after) {
        observed_mailbox_version_ = version_after;
        if (!has_accepted_command_value_ || command_value > last_accepted_command_value_) {
          last_accepted_command_value_ = command_value;
          last_accepted_receipt_time_ns_ = receipt_time_ns;
          has_accepted_command_value_ = true;
          has_new_command = true;
          accepted_command_value = command_value;
          armed_ = true;
        }
      }
    }

    if (!enabled) {
      return {
        has_new_command,
        accepted_command_value,
        armed_,
        timed_out_,
        TargetCommandWatchdogEvent::kNone};
    }

    if (!armed_) {
      return {
        has_new_command, accepted_command_value, false, false, TargetCommandWatchdogEvent::kNone};
    }

    // Expiry is a latched safety fault. Only a lifecycle reset may clear it.
    if (timed_out_) {
      return {
        has_new_command, accepted_command_value, true, true, TargetCommandWatchdogEvent::kNone};
    }

    const bool expired = now_ns >= last_accepted_receipt_time_ns_ &&
      now_ns - last_accepted_receipt_time_ns_ >= timeout_ns;

    if (expired) {
      timed_out_ = true;
      return {
        has_new_command, accepted_command_value, true, true, TargetCommandWatchdogEvent::kTimedOut};
    }

    return {
      has_new_command, accepted_command_value, true, false, TargetCommandWatchdogEvent::kNone};
  }

private:
  // Even versions are stable; odd versions mean the callback is writing the mailbox.
  std::atomic<std::uint64_t> mailbox_version_{0};
  std::atomic<std::uint64_t> latest_command_value_{0};
  std::atomic<std::uint64_t> latest_receipt_time_ns_{0};

  // The realtime update loop is the sole reader/writer of these fields.
  std::uint64_t observed_mailbox_version_{0};
  std::uint64_t last_accepted_command_value_{0};
  std::uint64_t last_accepted_receipt_time_ns_{0};
  bool has_accepted_command_value_{false};
  bool armed_{false};
  bool timed_out_{false};
};

}  // namespace crisp_controllers
