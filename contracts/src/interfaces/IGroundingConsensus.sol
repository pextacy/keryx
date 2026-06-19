// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title IGroundingConsensus
/// @notice Read interface for finalized grounding consensus used by dispute resolution.
interface IGroundingConsensus {
    /// @notice Returns the finalized grounding consensus for a given data hash.
    /// @param dataHash The identifier of the grounded data being queried.
    /// @return gBps The consensus grounding score in basis points (0-10000).
    /// @return finalized True once consensus has been finalized for the data hash.
    function consensusOf(bytes32 dataHash) external view returns (uint16 gBps, bool finalized);
}
