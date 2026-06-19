// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessController} from "../access/AccessController.sol";
import {GroundingMath} from "../libraries/GroundingMath.sol";
import {IGroundingConsensus} from "../interfaces/IGroundingConsensus.sol";

/// @title GroundingAttestor
/// @notice Aggregates multiple oracle-signed grounding scores into a consensus
///         grounding basis-point value (gBps) per dataHash. Each ORACLE_ROLE holder
///         submits one bounded score per dataHash; once the configured quorum of
///         distinct oracles has reported, a governor-gated finalize call freezes the
///         arithmetic-mean consensus that downstream settlement and dispute modules read.
/// @dev Implements {IGroundingConsensus} so dispute resolution can read finalized scores.
contract GroundingAttestor is IGroundingConsensus {
    /// @notice Role registry consulted for oracle and governor authorization.
    AccessController public immutable acl;

    /// @notice Minimum number of distinct oracle submissions required before a
    ///         dataHash may be finalized.
    uint256 public quorum;

    /// @notice Running aggregate of submitted scores for a single dataHash.
    struct Aggregate {
        uint256 sumBps;
        uint256 count;
        uint16 consensusBps;
        bool finalized;
    }

    /// @notice Per-dataHash aggregate state.
    mapping(bytes32 => Aggregate) internal _aggregates;

    /// @notice Tracks whether a given oracle has already submitted for a dataHash.
    mapping(bytes32 => mapping(address => bool)) public submitted;

    /// @notice Emitted when an oracle records a grounding score for a dataHash.
    event ScoreSubmitted(bytes32 indexed dataHash, address indexed oracle, uint16 gBps);
    /// @notice Emitted when a dataHash's consensus is frozen.
    event Finalized(bytes32 indexed dataHash, uint16 consensusBps, uint256 count);
    /// @notice Emitted when the quorum threshold is updated.
    event QuorumSet(uint256 quorum);

    error NotOracle();
    error NotGovernor();
    error AlreadySubmitted();
    error AlreadyFinalized();
    error QuorumNotMet();
    error InvalidScore();

    /// @notice Restricts a call to holders of the ORACLE_ROLE.
    modifier onlyOracle() {
        if (!acl.hasRole(acl.ORACLE_ROLE(), msg.sender)) revert NotOracle();
        _;
    }

    /// @notice Restricts a call to holders of the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the attestor to the role registry and sets the initial quorum.
    /// @param acl_ The access controller used for authorization decisions.
    /// @param quorum_ The initial minimum distinct-oracle count required to finalize.
    constructor(AccessController acl_, uint256 quorum_) {
        acl = acl_;
        quorum = quorum_;
        emit QuorumSet(quorum_);
    }

    /// @notice Updates the quorum threshold required for finalization.
    /// @dev Restricted to the governor. Applies to any not-yet-finalized dataHash.
    /// @param quorum_ The new minimum distinct-oracle count.
    function setQuorum(uint256 quorum_) external onlyGovernor {
        quorum = quorum_;
        emit QuorumSet(quorum_);
    }

    /// @notice Records an oracle's grounding score for a dataHash.
    /// @dev Each oracle may submit at most once per dataHash, and only while the
    ///      aggregate remains unfinalized. The score must be a valid basis-point value.
    /// @param dataHash The identifier of the grounded data being scored.
    /// @param gBps The grounding score in basis points (0..10000).
    function submitScore(bytes32 dataHash, uint16 gBps) external onlyOracle {
        if (gBps > GroundingMath.BPS) revert InvalidScore();

        Aggregate storage agg = _aggregates[dataHash];
        if (agg.finalized) revert AlreadyFinalized();
        if (submitted[dataHash][msg.sender]) revert AlreadySubmitted();

        // Effects: mark the submission and fold the score into the running sum.
        submitted[dataHash][msg.sender] = true;
        agg.sumBps += gBps;
        agg.count += 1;

        emit ScoreSubmitted(dataHash, msg.sender, gBps);
    }

    /// @notice Freezes the consensus grounding score for a dataHash.
    /// @dev Restricted to the governor. Requires the distinct-oracle count to have
    ///      reached the quorum and the aggregate to be unfinalized. The consensus is
    ///      the integer arithmetic mean of all submitted scores, itself a valid gBps.
    /// @param dataHash The identifier of the grounded data to finalize.
    /// @return consensusBps The frozen consensus grounding score in basis points.
    function finalize(bytes32 dataHash) external onlyGovernor returns (uint16 consensusBps) {
        Aggregate storage agg = _aggregates[dataHash];
        if (agg.finalized) revert AlreadyFinalized();
        if (agg.count < quorum || agg.count == 0) revert QuorumNotMet();

        // Integer arithmetic mean of submitted basis points; each input is <= BPS,
        // so the mean is also <= BPS and fits a uint16 without truncation loss of range.
        consensusBps = uint16(agg.sumBps / agg.count);

        // Effects: freeze the aggregate before emitting.
        agg.consensusBps = consensusBps;
        agg.finalized = true;

        emit Finalized(dataHash, consensusBps, agg.count);
    }

    /// @notice Reads the consensus state for a dataHash.
    /// @param dataHash The identifier of the grounded data.
    /// @return gBps The consensus grounding score in basis points (0 until finalized).
    /// @return finalized Whether the consensus has been frozen.
    function consensusOf(bytes32 dataHash) external view override returns (uint16 gBps, bool finalized) {
        Aggregate storage agg = _aggregates[dataHash];
        return (agg.consensusBps, agg.finalized);
    }
}
