// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IVotes} from "../interfaces/IVotes.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title SourceGauge
/// @notice veKRX-weighted gauge where holders allocate their voting power across
///         sources to set per-source reward weights for emission allocation. Each
///         user may spread their (decaying) veKRX voting power over many sources,
///         and the aggregate weights determine the relative share of emissions a
///         source receives. Votes are bounded by the user's current voting power.
contract SourceGauge {
    /// @notice The veKRX voting-power source consulted for each vote's budget.
    IVotes public immutable veToken;
    /// @notice The role registry queried for authorization decisions (reserved wiring).
    AccessController public immutable acl;

    /// @notice Aggregate weight allocated to each source across all voters.
    mapping(bytes32 => uint256) public sourceWeight;
    /// @notice Sum of all source weights; the denominator for relative weight.
    uint256 public totalWeight;

    /// @notice Per-user weight currently allocated to each source.
    mapping(address => mapping(bytes32 => uint256)) internal _userVote;
    /// @notice Total voting power a user has currently committed across all sources.
    mapping(address => uint256) internal _userUsed;

    /// @notice Emitted when a user (re)allocates weight to a source.
    event Voted(address indexed user, bytes32 indexed sourceId, uint256 weight);
    /// @notice Emitted when a user clears their allocation to a source.
    event VoteReset(address indexed user, bytes32 indexed sourceId);

    /// @notice Thrown when a vote would exceed the caller's available voting power.
    error InsufficientVotingPower();
    /// @notice Thrown when a vote is attempted with zero weight.
    error ZeroWeight();

    /// @notice Wires the gauge to its voting-power source and access controller.
    /// @param veToken_ The IVotes contract (veKRX escrow) supplying voting power.
    /// @param acl_ The access controller for the suite.
    constructor(IVotes veToken_, AccessController acl_) {
        veToken = veToken_;
        acl = acl_;
    }

    /// @notice Allocate `weight` of the caller's voting power to `sourceId`.
    /// @dev Replaces any prior allocation by the caller to this source. The caller's
    ///      total committed weight (after replacement) must not exceed their current
    ///      veKRX voting power. Follows checks-effects-interactions: only storage is
    ///      touched, no external calls beyond the voting-power read.
    /// @param sourceId The source identifier receiving the allocation.
    /// @param weight The amount of voting power to commit to the source.
    function vote(bytes32 sourceId, uint256 weight) external {
        if (weight == 0) revert ZeroWeight();

        uint256 prior = _userVote[msg.sender][sourceId];
        // Net committed weight if this allocation replaces the prior one.
        uint256 newUsed = _userUsed[msg.sender] - prior + weight;

        if (newUsed > veToken.getVotes(msg.sender)) revert InsufficientVotingPower();

        // Effects: update user and aggregate accounting.
        _userVote[msg.sender][sourceId] = weight;
        _userUsed[msg.sender] = newUsed;
        totalWeight = totalWeight - prior + weight;
        sourceWeight[sourceId] = sourceWeight[sourceId] - prior + weight;

        emit Voted(msg.sender, sourceId, weight);
    }

    /// @notice Clear the caller's allocation to `sourceId`, freeing that voting power.
    /// @param sourceId The source identifier to reset.
    function resetVote(bytes32 sourceId) external {
        uint256 prior = _userVote[msg.sender][sourceId];
        if (prior == 0) revert ZeroWeight();

        // Effects: remove the allocation from user and aggregate accounting.
        _userVote[msg.sender][sourceId] = 0;
        _userUsed[msg.sender] -= prior;
        totalWeight -= prior;
        sourceWeight[sourceId] -= prior;

        emit VoteReset(msg.sender, sourceId);
    }

    /// @notice Relative share of a source's weight in basis points (out of 10000).
    /// @dev Returns 0 when no weight has been allocated anywhere.
    /// @param sourceId The source identifier to query.
    /// @return bps The source's share of total weight in basis points.
    function relativeWeight(bytes32 sourceId) external view returns (uint256 bps) {
        uint256 total = totalWeight;
        if (total == 0) return 0;
        return (sourceWeight[sourceId] * 10000) / total;
    }
}
