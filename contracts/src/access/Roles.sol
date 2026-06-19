// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title Roles
/// @notice Bytes32 role -> member mapping with an admin-role hierarchy; base for
///         role-gated contracts. Each role has an admin role whose holders may
///         grant and revoke it; the DEFAULT_ADMIN_ROLE administers itself.
abstract contract Roles {
    /// @notice The root admin role; admin of every role unless reconfigured.
    bytes32 public constant DEFAULT_ADMIN_ROLE = 0x00;

    /// @notice role => account => membership flag.
    mapping(bytes32 => mapping(address => bool)) internal _roleMembers;

    /// @notice role => admin role that controls it.
    mapping(bytes32 => bytes32) internal _roleAdmin;

    /// @notice Emitted when `account` is granted `role` by `sender`.
    event RoleGranted(bytes32 indexed role, address indexed account, address indexed sender);
    /// @notice Emitted when `account` loses `role` (revoke or renounce) by `sender`.
    event RoleRevoked(bytes32 indexed role, address indexed account, address indexed sender);
    /// @notice Emitted when the admin role controlling `role` changes.
    event RoleAdminChanged(bytes32 indexed role, bytes32 previousAdmin, bytes32 newAdmin);

    /// @notice Thrown when `account` lacks a required `role`.
    error MissingRole(bytes32 role, address account);

    /// @notice Reverts unless the caller holds `role`.
    modifier onlyRole(bytes32 role) {
        _checkRole(role, msg.sender);
        _;
    }

    /// @notice Returns whether `account` holds `role`.
    function hasRole(bytes32 role, address account) public view returns (bool) {
        return _roleMembers[role][account];
    }

    /// @notice Returns the admin role that controls `role`.
    function getRoleAdmin(bytes32 role) public view returns (bytes32) {
        return _roleAdmin[role];
    }

    /// @notice Grants `role` to `account`. Caller must hold the admin of `role`.
    function grantRole(bytes32 role, address account) external {
        _checkRole(getRoleAdmin(role), msg.sender);
        _grantRole(role, account);
    }

    /// @notice Revokes `role` from `account`. Caller must hold the admin of `role`.
    function revokeRole(bytes32 role, address account) external {
        _checkRole(getRoleAdmin(role), msg.sender);
        _revokeRole(role, account);
    }

    /// @notice Caller renounces `role` for itself.
    function renounceRole(bytes32 role) external {
        _revokeRole(role, msg.sender);
    }

    /// @notice Internal unconditional grant used by constructors/bootstrapping.
    function _setupRole(bytes32 role, address account) internal {
        _grantRole(role, account);
    }

    /// @notice Internal setter for the admin role of `role`.
    function _setRoleAdmin(bytes32 role, bytes32 adminRole) internal {
        bytes32 previousAdmin = _roleAdmin[role];
        if (previousAdmin != adminRole) {
            _roleAdmin[role] = adminRole;
            emit RoleAdminChanged(role, previousAdmin, adminRole);
        }
    }

    /// @dev Reverts with MissingRole if `account` does not hold `role`.
    function _checkRole(bytes32 role, address account) internal view {
        if (!_roleMembers[role][account]) {
            revert MissingRole(role, account);
        }
    }

    /// @dev Idempotent grant; emits only on actual state change.
    function _grantRole(bytes32 role, address account) internal {
        if (!_roleMembers[role][account]) {
            _roleMembers[role][account] = true;
            emit RoleGranted(role, account, msg.sender);
        }
    }

    /// @dev Idempotent revoke; emits only on actual state change.
    function _revokeRole(bytes32 role, address account) internal {
        if (_roleMembers[role][account]) {
            _roleMembers[role][account] = false;
            emit RoleRevoked(role, account, msg.sender);
        }
    }
}
