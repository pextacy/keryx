// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {DisputeManager} from "./DisputeManager.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title ArbitrationPanel
/// @notice Arbitrator-role members cast votes on a dispute until a verdict tally
///         reaches the configured threshold, at which point the dispute is
///         resolved in the linked DisputeManager. Each arbitrator may vote once
///         per dispute and voting halts once a verdict has been decided.
contract ArbitrationPanel {
    /// @notice Role registry consulted for arbitrator and governor authorization.
    AccessController public immutable acl;

    /// @notice The dispute lifecycle contract this panel resolves verdicts into.
    DisputeManager public immutable disputes;

    /// @notice Number of votes on the winning side required to decide a verdict.
    uint256 public voteThreshold;

    /// @notice Role required to cast arbitration votes.
    bytes32 public constant ARBITRATOR_ROLE = keccak256("ARBITRATOR_ROLE");

    /// @notice Running vote counts and decision flag for a dispute.
    struct Tally {
        uint256 forVotes;
        uint256 againstVotes;
        bool decided;
    }

    /// @notice disputeId => running tally.
    mapping(uint256 => Tally) internal _tallies;

    /// @notice disputeId => arbitrator => whether they have already voted.
    mapping(uint256 => mapping(address => bool)) public voted;

    /// @notice Emitted when an arbitrator casts a vote on a dispute.
    event VoteCast(uint256 indexed disputeId, address indexed arbitrator, bool support);
    /// @notice Emitted when a dispute reaches a verdict and is resolved.
    event Decided(uint256 indexed disputeId, bool upheld);
    /// @notice Emitted when the governor updates the vote threshold.
    event VoteThresholdSet(uint256 threshold);

    /// @notice Thrown when a non-arbitrator attempts to vote.
    error NotArbitrator();
    /// @notice Thrown when a non-governor attempts a governance action.
    error NotGovernor();
    /// @notice Thrown when an arbitrator votes twice on the same dispute.
    error AlreadyVoted();
    /// @notice Thrown when voting on an already-decided dispute.
    error AlreadyDecided();

    /// @notice Wires the panel to the access controller and dispute manager.
    /// @param acl_ The role registry used for authorization.
    /// @param disputes_ The dispute manager that records final verdicts.
    /// @param voteThreshold_ Initial winning-side vote count required to decide.
    constructor(AccessController acl_, DisputeManager disputes_, uint256 voteThreshold_) {
        acl = acl_;
        disputes = disputes_;
        voteThreshold = voteThreshold_;
        emit VoteThresholdSet(voteThreshold_);
    }

    /// @notice Updates the winning-side vote count required to decide a verdict.
    /// @dev Restricted to GOVERNOR_ROLE holders.
    /// @param threshold The new vote threshold.
    function setVoteThreshold(uint256 threshold) external {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        voteThreshold = threshold;
        emit VoteThresholdSet(threshold);
    }

    /// @notice Casts an arbitrator vote for or against upholding a dispute.
    /// @dev Restricted to ARBITRATOR_ROLE holders. Once either side's count reaches
    ///      the threshold, the dispute is decided and resolved exactly once.
    ///      Follows checks-effects-interactions: all local state is updated before
    ///      the external resolve call into the dispute manager.
    /// @param disputeId The dispute being voted on.
    /// @param support True to uphold the dispute, false to reject it.
    function vote(uint256 disputeId, bool support) external {
        if (!acl.hasRole(ARBITRATOR_ROLE, msg.sender)) revert NotArbitrator();

        Tally storage tally = _tallies[disputeId];
        if (tally.decided) revert AlreadyDecided();
        if (voted[disputeId][msg.sender]) revert AlreadyVoted();

        // Effects: record the vote before any external interaction.
        voted[disputeId][msg.sender] = true;
        if (support) {
            tally.forVotes += 1;
        } else {
            tally.againstVotes += 1;
        }
        emit VoteCast(disputeId, msg.sender, support);

        uint256 threshold = voteThreshold;
        bool reached = threshold != 0 &&
            (tally.forVotes >= threshold || tally.againstVotes >= threshold);
        if (reached) {
            bool upheld = tally.forVotes >= threshold;
            tally.decided = true;
            emit Decided(disputeId, upheld);

            // Interaction: propagate the verdict to the dispute manager last.
            disputes.resolve(disputeId, upheld);
        }
    }

    /// @notice Returns the current tally for a dispute.
    /// @param disputeId The dispute to query.
    /// @return The dispute's running vote tally and decision flag.
    function tallyOf(uint256 disputeId) external view returns (Tally memory) {
        return _tallies[disputeId];
    }
}
