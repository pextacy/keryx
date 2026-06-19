// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {DisputeManager} from "./DisputeManager.sol";
import {SlashingController} from "../staking/SlashingController.sol";
import {IGroundingConsensus} from "../interfaces/IGroundingConsensus.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title DisputeResolver
/// @notice Couples a resolved dispute to slashing and reputation outcomes in one authorized call.
contract DisputeResolver {
    /// @notice Role registry the suite queries for authorization decisions.
    AccessController public immutable acl;
    /// @notice Source of truth for dispute lifecycle and verdicts.
    DisputeManager public immutable disputes;
    /// @notice Executes bounded slashing against staked offenders.
    SlashingController public immutable slasher;
    /// @notice Finalized grounding consensus consulted during settlement.
    IGroundingConsensus public immutable consensus;
    /// @notice Fixed slash amount applied when a dispute is upheld.
    uint256 public slashAmount;

    /// @notice Arbitrator role identifier (not predefined on AccessController).
    bytes32 public constant ARBITRATOR_ROLE = keccak256("ARBITRATOR_ROLE");

    /// @notice Emitted when a resolved dispute is settled into outcomes.
    event Settled(uint256 indexed disputeId, bool upheld, uint256 slashed);
    /// @notice Emitted when the governed slash amount changes.
    event SlashAmountSet(uint256 amount);

    error NotGovernor();
    error NotArbitrator();
    error NotResolvable();

    /// @notice Wires the resolver to its dependencies and sets the initial slash amount.
    constructor(
        AccessController acl_,
        DisputeManager disputes_,
        SlashingController slasher_,
        IGroundingConsensus consensus_,
        uint256 slashAmount_
    ) {
        acl = acl_;
        disputes = disputes_;
        slasher = slasher_;
        consensus = consensus_;
        slashAmount = slashAmount_;
        emit SlashAmountSet(slashAmount_);
    }

    /// @notice Governor-gated update of the fixed slash amount.
    function setSlashAmount(uint256 amount) external {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        slashAmount = amount;
        emit SlashAmountSet(amount);
    }

    /// @notice Settles a resolved dispute: slashes the offender when the challenge was upheld.
    /// @dev Only callable by arbitrators; requires the dispute to be in the Resolved phase.
    ///      Checks-effects-interactions: reads verdict, then performs the external slash call.
    /// @param disputeId Identifier of the dispute to settle.
    /// @param offender Account whose stake is slashed if the dispute is upheld.
    /// @return slashed Amount of stake actually slashed (zero if not upheld).
    function settleDispute(uint256 disputeId, address offender) external returns (uint256 slashed) {
        if (!acl.hasRole(ARBITRATOR_ROLE, msg.sender)) revert NotArbitrator();

        DisputeManager.Dispute memory d = disputes.getDispute(disputeId);
        if (d.phase != DisputeManager.Phase.Resolved) revert NotResolvable();

        bool upheld = d.upheld;
        if (upheld) {
            bytes32 caseId = keccak256(abi.encodePacked("DISPUTE", disputeId, d.dataHash));
            slashed = slasher.slash(offender, slashAmount, caseId);
        }

        emit Settled(disputeId, upheld, slashed);
    }
}
