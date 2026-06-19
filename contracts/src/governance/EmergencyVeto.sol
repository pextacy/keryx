// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessController} from "../access/AccessController.sol";
import {KeryxGovernor} from "./KeryxGovernor.sol";

/// @title EmergencyVeto
/// @notice Guardian-driven cancellation of in-flight governor proposals deemed
///         malicious. A holder of the AccessController GUARDIAN_ROLE may force
///         the KeryxGovernor to cancel a proposal before it is executed.
contract EmergencyVeto {
    /// @notice Role registry consulted for guardian authorization.
    AccessController public immutable acl;

    /// @notice Governor whose proposals can be vetoed.
    KeryxGovernor public immutable governor;

    /// @notice Emitted when a guardian vetoes (cancels) a proposal.
    event ProposalVetoed(uint256 indexed proposalId, address indexed guardian);

    /// @notice Thrown when the caller does not hold the guardian role.
    error NotGuardian();

    /// @notice Restricts a function to accounts holding the guardian role.
    modifier onlyGuardian() {
        if (!acl.hasRole(acl.GUARDIAN_ROLE(), msg.sender)) revert NotGuardian();
        _;
    }

    /// @notice Wires the veto module to the access controller and governor.
    /// @param acl_ Role registry providing guardian authorization.
    /// @param governor_ Governor whose proposals may be vetoed.
    constructor(AccessController acl_, KeryxGovernor governor_) {
        acl = acl_;
        governor = governor_;
    }

    /// @notice Cancels an in-flight governor proposal as a guardian action.
    /// @dev Effects: emits the veto event, then interacts with the external
    ///      governor to perform the cancellation (checks-effects-interactions).
    /// @param proposalId Identifier of the proposal to cancel.
    function vetoProposal(uint256 proposalId) external onlyGuardian {
        emit ProposalVetoed(proposalId, msg.sender);
        governor.cancel(proposalId);
    }
}
