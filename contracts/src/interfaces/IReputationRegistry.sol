// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice ERC-8004-inspired reputation: settled citations accrue weighted feedback
///         to an author's on-chain reputation. Only authorized writers may accrue.
interface IReputationRegistry {
    function accrue(uint256 agentId, uint16 gBps) external;
    function reputationOf(uint256 agentId) external view returns (uint256 score, uint256 citations, uint256 avgBps);
}
