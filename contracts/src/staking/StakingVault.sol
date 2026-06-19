// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "../interfaces/IERC20.sol";
import "../interfaces/IStakeView.sol";
import "../util/SafeTransferLib.sol";
import "../util/ReentrancyGuard.sol";
import "../access/AccessController.sol";

/// @title StakingVault
/// @notice Authors and validators stake KRX with an unbonding delay to back their attestations.
contract StakingVault is IStakeView, ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice KRX token staked into this vault.
    IERC20 public immutable krx;

    /// @notice Access controller queried for governor and slasher authorization.
    AccessController public immutable acl;

    /// @notice Delay (in seconds) between requesting an unstake and being able to withdraw.
    uint256 public unbondingPeriod;

    /// @notice Total KRX currently staked (active stake; excludes pending unstake amounts).
    uint256 public totalStaked;

    struct Account {
        uint256 staked;
        uint256 pendingUnstake;
        uint64 unlockAt;
    }

    mapping(address => Account) internal _accounts;

    event Staked(address indexed user, uint256 amount);
    event UnstakeRequested(address indexed user, uint256 amount, uint64 unlockAt);
    event Unstaked(address indexed user, uint256 amount);
    event Slashed(address indexed user, uint256 amount, address indexed beneficiary);
    event UnbondingPeriodSet(uint256 period);

    error ZeroAmount();
    error InsufficientStake();
    error StillBonding();
    error NothingPending();
    error NotSlasher();
    error NotGovernor();

    /// @notice Wires the vault to the KRX token, the access controller, and an initial unbonding period.
    constructor(IERC20 krx_, AccessController acl_, uint256 unbondingPeriod_) {
        krx = krx_;
        acl = acl_;
        unbondingPeriod = unbondingPeriod_;
        emit UnbondingPeriodSet(unbondingPeriod_);
    }

    /// @notice Sets the unbonding delay. Restricted to the governor role.
    function setUnbondingPeriod(uint256 period) external {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        unbondingPeriod = period;
        emit UnbondingPeriodSet(period);
    }

    /// @notice Stakes `amount` KRX, pulling it from the caller and increasing active stake.
    function stake(uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();

        // Effects.
        _accounts[msg.sender].staked += amount;
        totalStaked += amount;

        emit Staked(msg.sender, amount);

        // Interaction.
        krx.safeTransferFrom(msg.sender, address(this), amount);
    }

    /// @notice Requests to unstake `amount` from active stake, starting the unbonding timer.
    /// @dev Re-requesting refreshes the unlock time for the full pending balance.
    function requestUnstake(uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();

        Account storage acct = _accounts[msg.sender];
        if (acct.staked < amount) revert InsufficientStake();

        // Effects: move stake from active into pending unbonding.
        acct.staked -= amount;
        totalStaked -= amount;
        acct.pendingUnstake += amount;

        uint64 unlockAt = uint64(block.timestamp + unbondingPeriod);
        acct.unlockAt = unlockAt;

        emit UnstakeRequested(msg.sender, amount, unlockAt);
    }

    /// @notice Withdraws fully-unbonded pending stake to the caller.
    function withdraw() external nonReentrant {
        Account storage acct = _accounts[msg.sender];

        uint256 amount = acct.pendingUnstake;
        if (amount == 0) revert NothingPending();
        if (block.timestamp < acct.unlockAt) revert StillBonding();

        // Effects.
        acct.pendingUnstake = 0;
        acct.unlockAt = 0;

        emit Unstaked(msg.sender, amount);

        // Interaction.
        krx.safeTransfer(msg.sender, amount);
    }

    /// @notice Slashes up to `amount` of a user's stake to `beneficiary`. Restricted to the slasher role.
    /// @dev Drains active stake first, then pending unstake. Returns the actual amount slashed.
    function slash(address user, uint256 amount, address beneficiary) external nonReentrant returns (uint256 slashed) {
        if (!acl.hasRole(acl.SLASHER_ROLE(), msg.sender)) revert NotSlasher();
        if (amount == 0) revert ZeroAmount();

        Account storage acct = _accounts[user];

        uint256 remaining = amount;

        uint256 fromActive = acct.staked;
        if (fromActive > remaining) fromActive = remaining;
        if (fromActive != 0) {
            acct.staked -= fromActive;
            totalStaked -= fromActive;
            remaining -= fromActive;
        }

        if (remaining != 0) {
            uint256 fromPending = acct.pendingUnstake;
            if (fromPending > remaining) fromPending = remaining;
            if (fromPending != 0) {
                acct.pendingUnstake -= fromPending;
                remaining -= fromPending;
                if (acct.pendingUnstake == 0) acct.unlockAt = 0;
            }
        }

        slashed = amount - remaining;

        emit Slashed(user, slashed, beneficiary);

        // Interaction.
        if (slashed != 0) krx.safeTransfer(beneficiary, slashed);
    }

    /// @notice Active stake backing `account`'s attestations.
    function stakeOf(address account) external view returns (uint256) {
        return _accounts[account].staked;
    }

    /// @notice Whether `account` currently has any active stake.
    function isActive(address account) external view returns (bool) {
        return _accounts[account].staked != 0;
    }
}
