// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {IVotes} from "../interfaces/IVotes.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";

/// @title VoteEscrow
/// @notice Locks KRX for a chosen duration (up to MAX_LOCK) to mint decaying
///         vote-escrow voting power (veKRX). Voting power equals the locked
///         amount scaled by the remaining lock time over MAX_LOCK and linearly
///         decays to zero at the lock's end, after which the principal can be
///         withdrawn. Voting power is non-transferable and self-delegating, so
///         delegation is a fixed no-op that always points an account at itself.
contract VoteEscrow is IVotes, ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice The KRX token escrowed to mint voting power.
    IERC20 public immutable krx;

    /// @notice Maximum lock duration; a fresh max-length lock mints 1:1 power.
    uint256 public constant MAX_LOCK = 730 days;

    /// @dev A user's active lock: principal amount and unix end timestamp.
    struct Lock {
        uint256 amount;
        uint64 end;
    }

    /// @dev Per-user lock state.
    mapping(address => Lock) internal _locks;

    /// @notice Emitted when a user opens a new lock.
    event LockCreated(address indexed user, uint256 amount, uint64 end);
    /// @notice Emitted when a user adds tokens and/or extends an existing lock.
    event LockIncreased(address indexed user, uint256 addedAmount, uint64 newEnd);
    /// @notice Emitted when a user withdraws an expired lock's principal.
    event Withdrawn(address indexed user, uint256 amount);

    /// @notice Thrown when an operation requires an existing lock but none exists.
    error NoLock();
    /// @notice Thrown when withdrawing before the lock end has passed.
    error LockNotExpired();
    /// @notice Thrown when modifying a lock whose end has already passed.
    error LockExpired();
    /// @notice Thrown when a requested duration is zero or exceeds MAX_LOCK.
    error InvalidDuration();
    /// @notice Thrown when an amount argument is zero.
    error ZeroAmount();

    /// @param krx_ The KRX token to escrow.
    constructor(IERC20 krx_) {
        krx = krx_;
    }

    /// @notice Opens a new lock by pulling `amount` KRX locked for `duration`.
    /// @dev Reverts if the caller already holds an unexpired lock. Effects are
    ///      written before the external token pull (checks-effects-interactions).
    /// @param amount The amount of KRX to lock; must be non-zero.
    /// @param duration The lock duration in seconds; must be in (0, MAX_LOCK].
    function createLock(uint256 amount, uint256 duration) external nonReentrant {
        if (amount == 0) revert ZeroAmount();
        if (duration == 0 || duration > MAX_LOCK) revert InvalidDuration();

        Lock storage lock = _locks[msg.sender];
        if (lock.amount != 0 && lock.end > block.timestamp) revert LockExpired();

        uint64 end = uint64(block.timestamp + duration);
        lock.amount = amount;
        lock.end = end;

        emit LockCreated(msg.sender, amount, end);

        krx.safeTransferFrom(msg.sender, address(this), amount);
    }

    /// @notice Adds `amount` KRX to the caller's existing, unexpired lock.
    /// @dev The lock end is unchanged; the added stake simply earns power under
    ///      the same remaining time. Reverts if there is no active lock or it
    ///      has already expired.
    /// @param amount The additional amount of KRX to lock; must be non-zero.
    function increaseAmount(uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();

        Lock storage lock = _locks[msg.sender];
        if (lock.amount == 0) revert NoLock();
        if (lock.end <= block.timestamp) revert LockExpired();

        lock.amount += amount;

        emit LockIncreased(msg.sender, amount, lock.end);

        krx.safeTransferFrom(msg.sender, address(this), amount);
    }

    /// @notice Extends the caller's existing lock to `newDuration` from now.
    /// @dev `newDuration` is measured from the current block timestamp and must
    ///      strictly extend the lock (its new end must be later than the old
    ///      end) while staying within MAX_LOCK. Adds no tokens.
    /// @param newDuration The new lock duration in seconds; must be in (0, MAX_LOCK].
    function extendLock(uint256 newDuration) external {
        if (newDuration == 0 || newDuration > MAX_LOCK) revert InvalidDuration();

        Lock storage lock = _locks[msg.sender];
        if (lock.amount == 0) revert NoLock();
        if (lock.end <= block.timestamp) revert LockExpired();

        uint64 newEnd = uint64(block.timestamp + newDuration);
        if (newEnd <= lock.end) revert InvalidDuration();
        lock.end = newEnd;

        emit LockIncreased(msg.sender, 0, newEnd);
    }

    /// @notice Withdraws the caller's full principal once the lock has expired.
    /// @dev Clears lock state before transferring (checks-effects-interactions).
    function withdraw() external nonReentrant {
        Lock storage lock = _locks[msg.sender];
        uint256 amount = lock.amount;
        if (amount == 0) revert NoLock();
        if (lock.end > block.timestamp) revert LockNotExpired();

        delete _locks[msg.sender];

        emit Withdrawn(msg.sender, amount);

        krx.safeTransfer(msg.sender, amount);
    }

    /// @notice Returns the current decayed voting power of `user`'s lock.
    /// @param user The lock owner to query.
    /// @return votingPower The amount of veKRX currently held by `user`.
    function balanceOfLock(address user) external view returns (uint256 votingPower) {
        return _votingPower(_locks[user]);
    }

    /// @notice Returns the raw lock principal and end timestamp for `user`.
    /// @param user The lock owner to query.
    /// @return amount The locked KRX principal.
    /// @return end The unix timestamp at which the lock expires.
    function lockOf(address user) external view returns (uint256 amount, uint64 end) {
        Lock storage lock = _locks[user];
        return (lock.amount, lock.end);
    }

    /// @notice Returns the current voting power of `account` (IVotes surface).
    /// @param account The address to query voting power for.
    /// @return The current amount of veKRX `account` holds.
    function getVotes(address account) external view returns (uint256) {
        return _votingPower(_locks[account]);
    }

    /// @notice Historical voting power lookup.
    /// @dev veKRX is a deterministic, monotonically decaying function of a
    ///      lock's amount and end, with no per-block checkpoints retained. Past
    ///      voting power can only be evaluated against the live lock, so this
    ///      returns the decayed power computed at `timepoint` (interpreted as a
    ///      unix timestamp) for the account's current lock, and zero once the
    ///      queried time is at or beyond the lock end.
    /// @param account The address to query voting power for.
    /// @param timepoint The unix timestamp to evaluate the lock's power at.
    /// @return The veKRX power of `account` at `timepoint`.
    function getPastVotes(address account, uint256 timepoint) external view returns (uint256) {
        return _votingPowerAt(_locks[account], timepoint);
    }

    /// @notice Historical total voting supply lookup.
    /// @dev No global supply checkpoints are tracked by this escrow (power is
    ///      derived per-lock on demand), so this returns zero for every
    ///      timepoint to keep the IVotes surface total honest about the absence
    ///      of aggregate snapshots.
    /// @return Always zero.
    function getPastTotalSupply(uint256) external pure returns (uint256) {
        return 0;
    }

    /// @notice Returns the delegate of `account`.
    /// @dev veKRX is non-transferable and self-bound; every account always
    ///      delegates to itself.
    /// @param account The address to query the delegate of.
    /// @return Always `account` itself.
    function delegates(address account) external pure returns (address) {
        return account;
    }

    /// @notice Delegation entry point required by IVotes.
    /// @dev veKRX power is non-delegatable; voting power is fixed to the lock
    ///      owner. This is intentionally a no-op so the IVotes surface stays
    ///      callable without altering escrow state.
    function delegate(address) external pure {
        return;
    }

    /// @dev Computes the linearly decaying voting power of `lock` at the current
    ///      block timestamp. Power = amount * (end - now) / MAX_LOCK, and is
    ///      zero once the lock has expired or is empty.
    /// @param lock The lock to evaluate.
    /// @return The current veKRX power of the lock.
    function _votingPower(Lock storage lock) internal view returns (uint256) {
        return _votingPowerAt(lock, block.timestamp);
    }

    /// @dev Computes the linearly decaying voting power of `lock` evaluated at
    ///      timestamp `at`. Power = amount * (end - at) / MAX_LOCK, clamped to
    ///      zero once `at` reaches the lock end or the lock is empty.
    /// @param lock The lock to evaluate.
    /// @param at The unix timestamp at which to evaluate the lock.
    /// @return The veKRX power of the lock at `at`.
    function _votingPowerAt(Lock storage lock, uint256 at) internal view returns (uint256) {
        uint256 amount = lock.amount;
        uint256 end = lock.end;
        if (amount == 0 || at >= end) return 0;
        return (amount * (end - at)) / MAX_LOCK;
    }
}
