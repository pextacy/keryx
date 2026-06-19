// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {StakingVault} from "./StakingVault.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title ValidatorBondManager
/// @notice Tracks per-validator minimum bond and active status, gating who may
///         answer validations. A validator is eligible only while registered and
///         holding at least `minValidatorBond` staked in the StakingVault.
contract ValidatorBondManager {
    /// @notice Stake source consulted for each validator's bonded balance.
    StakingVault public immutable vault;

    /// @notice Role registry used to authorize governance actions.
    AccessController public immutable acl;

    /// @notice Minimum staked bond required for a registered validator to remain eligible.
    uint256 public minValidatorBond;

    /// @dev Registration flag per validator address.
    mapping(address => bool) internal _registered;

    /// @notice Emitted when a validator registers.
    event ValidatorRegistered(address indexed validator);

    /// @notice Emitted when a validator deregisters.
    event ValidatorDeregistered(address indexed validator);

    /// @notice Emitted when the minimum bond is updated.
    event MinBondSet(uint256 minBond);

    /// @notice Caller lacks the GOVERNOR_ROLE.
    error NotGovernor();

    /// @notice Caller's staked bond is below the required minimum.
    error InsufficientBond();

    /// @notice Caller is already registered.
    error AlreadyRegistered();

    /// @notice Caller is not registered.
    error NotRegistered();

    /// @dev Restricts a function to holders of the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the bond manager to its stake source and role registry.
    /// @param vault_ StakingVault holding validator bonds.
    /// @param acl_ AccessController consulted for governance authorization.
    /// @param minValidatorBond_ Initial minimum bond required for eligibility.
    constructor(StakingVault vault_, AccessController acl_, uint256 minValidatorBond_) {
        vault = vault_;
        acl = acl_;
        minValidatorBond = minValidatorBond_;
        emit MinBondSet(minValidatorBond_);
    }

    /// @notice Updates the minimum bond required for validator eligibility.
    /// @param minBond New minimum staked bond.
    function setMinBond(uint256 minBond) external onlyGovernor {
        minValidatorBond = minBond;
        emit MinBondSet(minBond);
    }

    /// @notice Registers the caller as a validator once their bond meets the minimum.
    /// @dev Reverts if already registered or if the staked bond is insufficient.
    function register() external {
        if (_registered[msg.sender]) revert AlreadyRegistered();
        if (vault.stakeOf(msg.sender) < minValidatorBond) revert InsufficientBond();
        _registered[msg.sender] = true;
        emit ValidatorRegistered(msg.sender);
    }

    /// @notice Deregisters the caller, removing their validator status.
    /// @dev Reverts if the caller is not currently registered.
    function deregister() external {
        if (!_registered[msg.sender]) revert NotRegistered();
        _registered[msg.sender] = false;
        emit ValidatorDeregistered(msg.sender);
    }

    /// @notice Reports whether an address may currently answer validations.
    /// @param validator Address to check.
    /// @return True if registered and holding at least the minimum bond.
    function isEligibleValidator(address validator) external view returns (bool) {
        return _registered[validator] && vault.stakeOf(validator) >= minValidatorBond;
    }
}
