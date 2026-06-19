// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Roles} from "./Roles.sol";

/// @title AccessController
/// @notice Concrete deployable role registry the whole Keryx suite queries for
///         authorization decisions. Wires the canonical protocol roles under the
///         DEFAULT_ADMIN_ROLE hierarchy and seeds the deployer admin.
contract AccessController is Roles {
    /// @notice Role permitted to perform governance-level configuration across modules.
    bytes32 public constant GOVERNOR_ROLE = keccak256("GOVERNOR_ROLE");
    /// @notice Role permitted to trigger emergency pauses and circuit breakers.
    bytes32 public constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");
    /// @notice Role permitted to settle citations and route payments.
    bytes32 public constant SETTLER_ROLE = keccak256("SETTLER_ROLE");
    /// @notice Role permitted to execute bounded slashing against staked balances.
    bytes32 public constant SLASHER_ROLE = keccak256("SLASHER_ROLE");
    /// @notice Role permitted to push oracle prices and grounding scores.
    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");

    /// @notice Deploys the controller, granting the admin account the root admin role.
    /// @param admin The account that receives DEFAULT_ADMIN_ROLE and may bootstrap roles.
    constructor(address admin) {
        if (admin == address(0)) revert MissingRole(DEFAULT_ADMIN_ROLE, admin);

        // Seed the root admin so it can grant/revoke every other role.
        _setupRole(DEFAULT_ADMIN_ROLE, admin);

        // Anchor every canonical protocol role under the root admin hierarchy so
        // the admin (or a contract holding the admin role) can administer them.
        _setRoleAdmin(GOVERNOR_ROLE, DEFAULT_ADMIN_ROLE);
        _setRoleAdmin(GUARDIAN_ROLE, DEFAULT_ADMIN_ROLE);
        _setRoleAdmin(SETTLER_ROLE, DEFAULT_ADMIN_ROLE);
        _setRoleAdmin(SLASHER_ROLE, DEFAULT_ADMIN_ROLE);
        _setRoleAdmin(ORACLE_ROLE, DEFAULT_ADMIN_ROLE);
    }

    /// @notice Grants a role to an account during initial protocol wiring.
    /// @dev Restricted to the root admin. Idempotent: re-bootstrapping an existing
    ///      member emits no event because the underlying grant is a no-op.
    /// @param role The role identifier to grant.
    /// @param account The account that should receive the role.
    function bootstrap(bytes32 role, address account)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        if (account == address(0)) revert MissingRole(role, account);
        _setupRole(role, account);
    }
}
