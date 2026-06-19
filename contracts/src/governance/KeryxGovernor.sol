// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IVotes} from "../interfaces/IVotes.sol";
import {Timelock} from "../access/Timelock.sol";

/// @title KeryxGovernor
/// @notice Proposal lifecycle (propose/vote/queue/execute) over IVotes power, executing through the Timelock.
contract KeryxGovernor {
    /// @notice Snapshot voting-power source consulted for thresholds and vote weights.
    IVotes public immutable votes;
    /// @notice Timelock that queues and executes successful proposals.
    Timelock public immutable timelock;

    /// @notice Blocks to wait after proposal creation before voting opens.
    uint256 public votingDelay;
    /// @notice Number of blocks the voting window stays open.
    uint256 public votingPeriod;
    /// @notice Minimum voting power required to create a proposal.
    uint256 public proposalThreshold;
    /// @notice Minimum total participating votes (for + abstain) required for a quorum.
    uint256 public quorumVotes;

    enum ProposalState {
        Pending,
        Active,
        Defeated,
        Succeeded,
        Queued,
        Executed,
        Cancelled
    }

    struct Proposal {
        address proposer;
        uint256 startBlock;
        uint256 endBlock;
        uint256 forVotes;
        uint256 againstVotes;
        uint256 abstainVotes;
        bool queued;
        bool executed;
        bool cancelled;
    }

    /// @notice Proposal records keyed by deterministic proposal id.
    mapping(uint256 => Proposal) internal _proposals;
    /// @notice Tracks whether an address has already cast a vote on a proposal.
    mapping(uint256 => mapping(address => bool)) public hasVoted;

    event ProposalCreated(
        uint256 indexed id,
        address proposer,
        address target,
        uint256 value,
        bytes data,
        string description
    );
    event VoteCast(address indexed voter, uint256 indexed id, uint8 support, uint256 weight);
    event ProposalQueued(uint256 indexed id, bytes32 opId);
    event ProposalExecuted(uint256 indexed id);
    event ProposalCancelled(uint256 indexed id);

    error BelowThreshold();
    error NotActive();
    error AlreadyVoted();
    error NotSucceeded();
    error AlreadyQueuedOrExecuted();

    /// @notice Wires the governor to its voting-power source and timelock and sets governance parameters.
    constructor(
        IVotes votes_,
        Timelock timelock_,
        uint256 votingDelay_,
        uint256 votingPeriod_,
        uint256 proposalThreshold_,
        uint256 quorumVotes_
    ) {
        votes = votes_;
        timelock = timelock_;
        votingDelay = votingDelay_;
        votingPeriod = votingPeriod_;
        proposalThreshold = proposalThreshold_;
        quorumVotes = quorumVotes_;
    }

    /// @notice Creates a proposal to execute a single call once it succeeds and clears the timelock.
    /// @return id Deterministic identifier derived from the proposed call and description.
    function propose(
        address target,
        uint256 value,
        bytes calldata data,
        string calldata description
    ) external returns (uint256 id) {
        if (votes.getVotes(msg.sender) < proposalThreshold) revert BelowThreshold();

        id = uint256(
            keccak256(abi.encode(target, value, keccak256(data), keccak256(bytes(description))))
        );

        Proposal storage p = _proposals[id];
        if (p.proposer != address(0)) revert AlreadyQueuedOrExecuted();

        uint256 startBlock = block.number + votingDelay;
        uint256 endBlock = startBlock + votingPeriod;

        p.proposer = msg.sender;
        p.startBlock = startBlock;
        p.endBlock = endBlock;

        emit ProposalCreated(id, msg.sender, target, value, data, description);
    }

    /// @notice Casts a vote on an active proposal weighted by the caller's current voting power.
    /// @param support 0 = against, 1 = for, 2 = abstain.
    function castVote(uint256 id, uint8 support) external {
        Proposal storage p = _proposals[id];
        if (p.proposer == address(0)) revert NotActive();
        if (block.number < p.startBlock || block.number > p.endBlock) revert NotActive();
        if (p.cancelled) revert NotActive();
        if (hasVoted[id][msg.sender]) revert AlreadyVoted();

        uint256 weight = votes.getVotes(msg.sender);

        hasVoted[id][msg.sender] = true;

        if (support == 0) {
            p.againstVotes += weight;
        } else if (support == 1) {
            p.forVotes += weight;
        } else {
            p.abstainVotes += weight;
        }

        emit VoteCast(msg.sender, id, support, weight);
    }

    /// @notice Queues a succeeded proposal's call into the Timelock for delayed execution.
    function queue(
        uint256 id,
        address target,
        uint256 value,
        bytes calldata data,
        bytes32 salt
    ) external {
        Proposal storage p = _proposals[id];
        if (_state(p) != ProposalState.Succeeded) revert NotSucceeded();
        if (p.queued || p.executed) revert AlreadyQueuedOrExecuted();

        p.queued = true;

        bytes32 opId = timelock.queue(target, value, data, salt);

        emit ProposalQueued(id, opId);
    }

    /// @notice Executes a queued proposal through the Timelock after its delay has elapsed.
    function execute(
        uint256 id,
        address target,
        uint256 value,
        bytes calldata data,
        bytes32 salt
    ) external payable {
        Proposal storage p = _proposals[id];
        if (!p.queued) revert NotSucceeded();
        if (p.executed) revert AlreadyQueuedOrExecuted();
        if (p.cancelled) revert NotSucceeded();

        p.executed = true;

        timelock.execute{value: value}(target, value, data, salt);

        emit ProposalExecuted(id);
    }

    /// @notice Cancels a proposal that has not yet executed; callable by the original proposer.
    function cancel(uint256 id) external {
        Proposal storage p = _proposals[id];
        if (p.proposer == address(0)) revert NotActive();
        if (p.executed) revert AlreadyQueuedOrExecuted();
        if (msg.sender != p.proposer) revert NotActive();

        p.cancelled = true;

        emit ProposalCancelled(id);
    }

    /// @notice Returns the current lifecycle state of a proposal.
    function state(uint256 id) external view returns (ProposalState) {
        return _state(_proposals[id]);
    }

    /// @notice Returns the full stored record for a proposal.
    function getProposal(uint256 id) external view returns (Proposal memory) {
        return _proposals[id];
    }

    /// @dev Derives the lifecycle state of a proposal from its stored fields and the current block.
    function _state(Proposal storage p) internal view returns (ProposalState) {
        if (p.proposer == address(0)) revert NotActive();
        if (p.cancelled) return ProposalState.Cancelled;
        if (p.executed) return ProposalState.Executed;
        if (p.queued) return ProposalState.Queued;
        if (block.number < p.startBlock) return ProposalState.Pending;
        if (block.number <= p.endBlock) return ProposalState.Active;

        uint256 participating = p.forVotes + p.abstainVotes;
        if (p.forVotes > p.againstVotes && participating >= quorumVotes) {
            return ProposalState.Succeeded;
        }
        return ProposalState.Defeated;
    }
}
