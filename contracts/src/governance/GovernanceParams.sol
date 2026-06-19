// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessController} from "../access/AccessController.sol";

/// @title GovernanceParams
/// @notice Central governed key/value store of protocol parameters readable by any module.
contract GovernanceParams {
    /// @notice Role registry consulted for governor authorization.
    AccessController public immutable acl;

    /// @notice Governed uint256 parameters keyed by an opaque identifier.
    mapping(bytes32 => uint256) internal _uintParams;

    /// @notice Governed address parameters keyed by an opaque identifier.
    mapping(bytes32 => address) internal _addressParams;

    /// @notice Emitted when a uint256 parameter is set.
    event UintParamSet(bytes32 indexed key, uint256 value);

    /// @notice Emitted when an address parameter is set.
    event AddressParamSet(bytes32 indexed key, address value);

    /// @notice Thrown when a non-governor attempts a mutating call.
    error NotGovernor();

    /// @notice Restricts a function to accounts holding the governor role.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @param acl_ The access controller used for governor authorization.
    constructor(AccessController acl_) {
        acl = acl_;
    }

    /// @notice Sets a governed uint256 parameter.
    /// @param key The parameter identifier.
    /// @param value The new value to store.
    function setUint(bytes32 key, uint256 value) external onlyGovernor {
        _uintParams[key] = value;
        emit UintParamSet(key, value);
    }

    /// @notice Sets a governed address parameter.
    /// @param key The parameter identifier.
    /// @param value The new value to store.
    function setAddress(bytes32 key, address value) external onlyGovernor {
        _addressParams[key] = value;
        emit AddressParamSet(key, value);
    }

    /// @notice Reads a governed uint256 parameter.
    /// @param key The parameter identifier.
    /// @return The stored value (zero if unset).
    function getUint(bytes32 key) external view returns (uint256) {
        return _uintParams[key];
    }

    /// @notice Reads a governed address parameter.
    /// @param key The parameter identifier.
    /// @return The stored value (zero address if unset).
    function getAddress(bytes32 key) external view returns (address) {
        return _addressParams[key];
    }
}
