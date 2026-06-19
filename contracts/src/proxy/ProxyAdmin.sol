// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {ERC1967Proxy} from "./ERC1967Proxy.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title ProxyAdmin
/// @notice Governor-owned admin that upgrades ERC-1967 proxies and rotates their admins.
contract ProxyAdmin {
    /// @notice Access controller queried for the GOVERNOR_ROLE.
    AccessController public immutable acl;

    /// @notice Emitted when a managed proxy is pointed at a new implementation.
    event ProxyUpgraded(address indexed proxy, address indexed implementation);
    /// @notice Emitted when a managed proxy's admin is rotated to a new address.
    event ProxyAdminChanged(address indexed proxy, address indexed newAdmin);

    /// @notice Thrown when the caller does not hold the GOVERNOR_ROLE.
    error NotGovernor();

    /// @notice Restricts a function to accounts holding the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the admin to the suite-wide access controller.
    /// @param acl_ The deployed AccessController authorizing governor actions.
    constructor(AccessController acl_) {
        acl = acl_;
    }

    /// @notice Upgrades a proxy this admin controls to a new implementation.
    /// @param proxy The ERC-1967 proxy whose implementation slot is updated.
    /// @param implementation The new implementation contract address.
    function upgrade(ERC1967Proxy proxy, address implementation) external onlyGovernor {
        proxy.upgradeTo(implementation);
        emit ProxyUpgraded(address(proxy), implementation);
    }

    /// @notice Rotates the admin of a proxy this admin currently controls.
    /// @param proxy The ERC-1967 proxy whose admin slot is updated.
    /// @param newAdmin The address that will become the proxy's new admin.
    function changeProxyAdmin(ERC1967Proxy proxy, address newAdmin) external onlyGovernor {
        proxy.changeAdmin(newAdmin);
        emit ProxyAdminChanged(address(proxy), newAdmin);
    }

    /// @notice Reads the current implementation address of a managed proxy.
    /// @param proxy The ERC-1967 proxy to inspect.
    /// @return The implementation contract the proxy delegates to.
    function getProxyImplementation(ERC1967Proxy proxy) external view returns (address) {
        return proxy.implementation();
    }
}
