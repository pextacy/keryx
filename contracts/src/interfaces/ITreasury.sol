// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title ITreasury
/// @notice Treasury deposit/withdraw interface that fee and buyback modules call into.
interface ITreasury {
    /// @notice Pulls `amount` of `token` from the caller into the treasury.
    /// @param token The ERC20 token being deposited.
    /// @param amount The amount of `token` to deposit.
    function deposit(address token, uint256 amount) external;

    /// @notice Sends `amount` of `token` from the treasury to `to`.
    /// @param token The ERC20 token being withdrawn.
    /// @param to The recipient of the withdrawn tokens.
    /// @param amount The amount of `token` to withdraw.
    function withdraw(address token, address to, uint256 amount) external;

    /// @notice Returns the treasury-accounted balance of `token`.
    /// @param token The ERC20 token to query.
    /// @return The amount of `token` held by the treasury.
    function balanceOf(address token) external view returns (uint256);
}
