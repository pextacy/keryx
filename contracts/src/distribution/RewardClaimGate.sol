// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IReputationRegistry} from "../interfaces/IReputationRegistry.sol";
import {IIdentityRegistry} from "../interfaces/IIdentityRegistry.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title RewardClaimGate
/// @notice Requires a minimum on-chain reputation before an author may claim
///         distribution rewards. Resolves an author wallet to its agent identity,
///         reads the reputation registry, and enforces governed thresholds on both
///         average grounding quality (avgBps) and accrued citation count.
contract RewardClaimGate {
    /// @notice Reputation registry queried for an agent's score and citation history.
    IReputationRegistry public immutable reputation;
    /// @notice Identity registry mapping author wallets to agent identities.
    IIdentityRegistry public immutable identity;
    /// @notice Role registry consulted for governor-level configuration rights.
    AccessController public immutable acl;

    /// @notice Minimum average grounding quality (in basis points) required to claim.
    uint256 public minAvgBps;
    /// @notice Minimum number of accrued citations required to claim.
    uint256 public minCitations;

    /// @notice Emitted whenever the eligibility thresholds are updated.
    event GateSet(uint256 minAvgBps, uint256 minCitations);

    /// @notice Thrown when a non-governor attempts a governance-gated action.
    error NotGovernor();
    /// @notice Thrown when an author does not meet the eligibility thresholds.
    error GateNotMet();

    /// @notice Restricts a function to holders of the governor role.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the gate to its registries and seeds the initial thresholds.
    /// @param reputation_ The reputation registry to read author scores from.
    /// @param identity_ The identity registry resolving wallets to agent identities.
    /// @param acl_ The access controller used for governor authorization.
    /// @param minAvgBps_ The initial minimum average grounding bps threshold.
    /// @param minCitations_ The initial minimum accrued citation count threshold.
    constructor(
        IReputationRegistry reputation_,
        IIdentityRegistry identity_,
        AccessController acl_,
        uint256 minAvgBps_,
        uint256 minCitations_
    ) {
        reputation = reputation_;
        identity = identity_;
        acl = acl_;
        minAvgBps = minAvgBps_;
        minCitations = minCitations_;
        emit GateSet(minAvgBps_, minCitations_);
    }

    /// @notice Updates the eligibility thresholds. Governor only.
    /// @param minAvgBps_ The new minimum average grounding bps threshold.
    /// @param minCitations_ The new minimum accrued citation count threshold.
    function setGate(uint256 minAvgBps_, uint256 minCitations_) external onlyGovernor {
        minAvgBps = minAvgBps_;
        minCitations = minCitations_;
        emit GateSet(minAvgBps_, minCitations_);
    }

    /// @notice Returns whether an author wallet currently satisfies the gate.
    /// @dev An unregistered wallet (agentId == 0) is never eligible. Reputation
    ///      must meet both the average-bps and citation-count thresholds.
    /// @param author The wallet whose eligibility is being evaluated.
    /// @return True if the author meets every configured threshold.
    function checkEligible(address author) external view returns (bool) {
        return _eligible(author);
    }

    /// @notice Reverts unless the author satisfies the gate; used by callers as a guard.
    /// @param author The wallet whose eligibility is being enforced.
    function requireEligible(address author) external view {
        if (!_eligible(author)) revert GateNotMet();
    }

    /// @notice Internal eligibility evaluation shared by the view and the guard.
    /// @param author The wallet whose eligibility is being evaluated.
    /// @return True if the author maps to a registered agent meeting all thresholds.
    function _eligible(address author) internal view returns (bool) {
        uint256 agentId = identity.agentIdOf(author);
        if (agentId == 0) return false;

        (, uint256 citations, uint256 avgBps) = reputation.reputationOf(agentId);

        return avgBps >= minAvgBps && citations >= minCitations;
    }
}
