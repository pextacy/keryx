// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title IStakeView
/// @notice Read-only stake balance interface consumed by rewards, dispute, and slashing modules.
/// @dev Implemented by the StakingVault; lets downstream contracts query stake without coupling to its storage layout.
interface IStakeView {
    /// @notice Returns the active (bonded, non-pending-unstake) stake of an account.
    /// @param account The address whose staked balance is queried.
    /// @return The amount of stake currently backing the account.
    function stakeOf(address account) external view returns (uint256);

    /// @notice Returns the total active stake across all accounts.
    /// @return The aggregate staked amount.
    function totalStaked() external view returns (uint256);

    /// @notice Returns whether an account currently holds a non-zero active stake.
    /// @param account The address to check.
    /// @return True if the account is considered an active staker.
    function isActive(address account) external view returns (bool);
}
