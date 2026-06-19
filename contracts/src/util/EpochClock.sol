// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessController} from "../access/AccessController.sol";

/// @title EpochClock
/// @notice Shared epoch boundary math (epoch index from timestamp) used by the
///         emissions, buyback, and gauge modules so they all agree on a single
///         genesis anchor and a governed epoch length.
contract EpochClock {
    /// @notice Role registry consulted for governor authorization.
    AccessController public immutable acl;

    /// @notice The timestamp at which epoch zero begins; all epochs are measured
    ///         relative to this anchor.
    uint256 public immutable genesis;

    /// @notice The duration of a single epoch in seconds.
    uint256 public epochLength;

    /// @notice Emitted when the governed epoch length is updated.
    event EpochLengthSet(uint256 epochLength);

    /// @notice Thrown when a non-governor attempts a mutating call.
    error NotGovernor();

    /// @notice Thrown when a queried timestamp falls before the genesis anchor.
    error BeforeGenesis();

    /// @notice Thrown when a zero epoch length is configured.
    error ZeroEpochLength();

    /// @notice Restricts a function to accounts holding the governor role.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @param acl_ The access controller used for governor authorization.
    /// @param genesis_ The timestamp anchoring epoch zero.
    /// @param epochLength_ The initial epoch duration in seconds (must be non-zero).
    constructor(AccessController acl_, uint256 genesis_, uint256 epochLength_) {
        if (epochLength_ == 0) revert ZeroEpochLength();
        acl = acl_;
        genesis = genesis_;
        epochLength = epochLength_;
        emit EpochLengthSet(epochLength_);
    }

    /// @notice Updates the governed epoch length.
    /// @dev Restricted to the governor role. Changing the length re-divides time
    ///      from genesis using the new length for all subsequent reads.
    /// @param epochLength_ The new epoch duration in seconds (must be non-zero).
    function setEpochLength(uint256 epochLength_) external onlyGovernor {
        if (epochLength_ == 0) revert ZeroEpochLength();
        epochLength = epochLength_;
        emit EpochLengthSet(epochLength_);
    }

    /// @notice Returns the epoch index containing the current block timestamp.
    /// @return The zero-based epoch index for `block.timestamp`.
    function currentEpoch() external view returns (uint256) {
        return _epochAt(block.timestamp);
    }

    /// @notice Returns the epoch index containing the given timestamp.
    /// @param timestamp The timestamp to locate (must be at or after genesis).
    /// @return The zero-based epoch index for `timestamp`.
    function epochAt(uint256 timestamp) external view returns (uint256) {
        return _epochAt(timestamp);
    }

    /// @notice Returns the timestamp at which the given epoch begins.
    /// @param epoch The zero-based epoch index.
    /// @return The starting timestamp of `epoch`.
    function epochStart(uint256 epoch) external view returns (uint256) {
        return genesis + (epoch * epochLength);
    }

    /// @dev Computes the zero-based epoch index for a timestamp relative to genesis.
    /// @param timestamp The timestamp to locate (must be at or after genesis).
    /// @return The epoch index containing `timestamp`.
    function _epochAt(uint256 timestamp) internal view returns (uint256) {
        if (timestamp < genesis) revert BeforeGenesis();
        return (timestamp - genesis) / epochLength;
    }
}
