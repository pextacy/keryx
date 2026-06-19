// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "./Pausable.sol";
import "./AccessController.sol";

/// @title GuardianPause
/// @notice Guardian-role-gated emergency pause switch. Other Keryx contracts can
///         read this contract's `paused()` view to halt sensitive operations
///         during an incident. Only holders of the AccessController's
///         GUARDIAN_ROLE may toggle the switch, keeping the emergency lever under
///         the same role registry the rest of the suite trusts.
contract GuardianPause is Pausable {
    /// @notice Role registry consulted for guardian authorization. Immutable so
    ///         the trust anchor cannot be swapped after deployment.
    AccessController public immutable acl;

    /// @notice Thrown when a caller without GUARDIAN_ROLE attempts to (un)pause.
    error NotGuardian();

    /// @notice Restricts a function to accounts holding the GUARDIAN_ROLE.
    modifier onlyGuardian() {
        if (!acl.hasRole(acl.GUARDIAN_ROLE(), msg.sender)) revert NotGuardian();
        _;
    }

    /// @notice Wires the pause switch to a role registry.
    /// @param acl_ The AccessController whose GUARDIAN_ROLE gates this switch.
    constructor(AccessController acl_) {
        acl = acl_;
    }

    /// @notice Engages the emergency pause. Reverts if already paused.
    /// @dev Guarded by GUARDIAN_ROLE; emits Paused via the base contract.
    function pause() external onlyGuardian {
        _pause();
    }

    /// @notice Lifts the emergency pause. Reverts if not currently paused.
    /// @dev Guarded by GUARDIAN_ROLE; emits Unpaused via the base contract.
    function unpause() external onlyGuardian {
        _unpause();
    }
}
