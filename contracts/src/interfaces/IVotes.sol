// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title IVotes
/// @notice Snapshot voting-power interface the governor reads from token/escrow.
interface IVotes {
    /// @notice Returns the current voting power of `account`.
    /// @param account The address to query voting power for.
    /// @return The current amount of votes `account` holds.
    function getVotes(address account) external view returns (uint256);

    /// @notice Returns the historical voting power of `account` at a past `timepoint`.
    /// @param account The address to query voting power for.
    /// @param timepoint The past block number (or timestamp) to query.
    /// @return The amount of votes `account` held at `timepoint`.
    function getPastVotes(address account, uint256 timepoint) external view returns (uint256);

    /// @notice Returns the total voting supply at a past `timepoint`.
    /// @param timepoint The past block number (or timestamp) to query.
    /// @return The total amount of votes in existence at `timepoint`.
    function getPastTotalSupply(uint256 timepoint) external view returns (uint256);

    /// @notice Returns the address `account` has delegated its voting power to.
    /// @param account The address to query the delegate of.
    /// @return The current delegatee for `account`.
    function delegates(address account) external view returns (address);

    /// @notice Delegates the caller's voting power to `delegatee`.
    /// @param delegatee The address to delegate voting power to.
    function delegate(address delegatee) external;
}
