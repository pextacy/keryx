// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessController} from "../access/AccessController.sol";

/// @title UpgradeableBeacon
/// @notice Single beacon holding the shared implementation address for a fleet
///         of beacon proxies. Governor-role accounts (queried from the suite's
///         AccessController) may upgrade the implementation for every proxy at once.
contract UpgradeableBeacon {
    /// @notice Role registry the beacon queries for upgrade authorization.
    AccessController public immutable acl;

    /// @notice Current shared implementation address served to all beacon proxies.
    address public implementation;

    /// @notice Emitted whenever the shared implementation is set or changed.
    event Upgraded(address indexed implementation);

    /// @notice Thrown when a caller lacks the GOVERNOR_ROLE.
    error NotGovernor();

    /// @notice Thrown when the supplied implementation has no contract code.
    error InvalidImplementation();

    /// @notice Restricts a function to holders of the AccessController GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @param acl_ The deployed AccessController authorizing upgrades.
    /// @param implementation_ The initial shared implementation address.
    constructor(AccessController acl_, address implementation_) {
        acl = acl_;
        _setImplementation(implementation_);
    }

    /// @notice Points every proxy reading this beacon at a new implementation.
    /// @param newImplementation The new shared implementation contract address.
    function upgradeTo(address newImplementation) external onlyGovernor {
        _setImplementation(newImplementation);
    }

    /// @dev Validates the target has code, updates state, then emits the event.
    function _setImplementation(address newImplementation) private {
        if (newImplementation.code.length == 0) revert InvalidImplementation();
        implementation = newImplementation;
        emit Upgraded(newImplementation);
    }
}
