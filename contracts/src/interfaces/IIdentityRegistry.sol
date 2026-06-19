// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice ERC-8004-inspired identity registry: every Keryx author/agent is one
///         on-chain identity (agentId) bound to a wallet. One contract holds them all.
interface IIdentityRegistry {
    function agentIdOf(address wallet) external view returns (uint256);
    function walletOf(uint256 agentId) external view returns (address);
    function isRegistered(address wallet) external view returns (bool);
    function totalAgents() external view returns (uint256);
}
