// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "./AccessController.sol";

/// @title Guardian
/// @notice Single guardian council that can veto queued timelock operations within a veto window.
contract Guardian {
    /// @notice Access controller queried for guardian authorization.
    AccessController public immutable acl;

    /// @notice Tracks whether an operation has been vetoed by a guardian.
    mapping(bytes32 => bool) public vetoed;

    /// @notice Emitted when a guardian vetoes a queued operation.
    event Vetoed(bytes32 indexed operationId, address indexed guardian);

    /// @notice Thrown when the caller does not hold the guardian role.
    error NotGuardian();

    /// @notice Wires the guardian to the suite-wide access controller.
    /// @param acl_ The deployed AccessController used for role checks.
    constructor(AccessController acl_) {
        acl = acl_;
    }

    /// @notice Vetoes a queued timelock operation, preventing its execution.
    /// @dev Only callable by an account holding the GUARDIAN_ROLE. Idempotent
    ///      re-vetoes are permitted and re-emit the event for off-chain observers.
    /// @param operationId The timelock operation identifier to veto.
    function veto(bytes32 operationId) external {
        if (!acl.hasRole(acl.GUARDIAN_ROLE(), msg.sender)) revert NotGuardian();
        vetoed[operationId] = true;
        emit Vetoed(operationId, msg.sender);
    }

    /// @notice Returns whether an operation has been vetoed.
    /// @param operationId The timelock operation identifier to query.
    /// @return True if the operation has been vetoed by a guardian.
    function isVetoed(bytes32 operationId) external view returns (bool) {
        return vetoed[operationId];
    }
}
