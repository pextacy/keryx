// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title UUPSUpgradeable
/// @notice Implementation-side UUPS upgrade authorization. Inheriting implementations
///         override `_authorizeUpgrade` to gate upgrades; `upgradeTo` writes the new
///         implementation address into the ERC-1967 implementation slot of the executing
///         proxy context and emits {Upgraded}.
abstract contract UUPSUpgradeable {
    /// @notice ERC-1967 implementation slot: keccak256("eip1967.proxy.implementation") - 1.
    bytes32 internal constant IMPLEMENTATION_SLOT =
        0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

    /// @notice Emitted when the implementation is upgraded.
    event Upgraded(address indexed implementation);

    /// @notice Thrown when an upgrade is not authorized by the inheriting implementation.
    error UpgradeUnauthorized();

    /// @notice Thrown when the proposed implementation address is zero.
    error InvalidImplementation();

    /// @notice Authorization hook for upgrades; must be implemented by the inheriting contract.
    /// @dev Should revert (e.g. with {UpgradeUnauthorized}) when the caller is not permitted.
    /// @param newImplementation The address of the new implementation contract.
    function _authorizeUpgrade(address newImplementation) internal virtual;

    /// @notice Upgrades the proxy to a new implementation after authorization.
    /// @dev Checks-effects-interactions: authorize, then write slot, then emit event.
    ///      Intended to be called through a proxy delegatecall so the slot write lands
    ///      in the proxy's storage.
    /// @param newImplementation The address of the new implementation contract.
    function upgradeTo(address newImplementation) external {
        if (newImplementation == address(0)) revert InvalidImplementation();
        _authorizeUpgrade(newImplementation);

        bytes32 slot = IMPLEMENTATION_SLOT;
        assembly {
            sstore(slot, newImplementation)
        }

        emit Upgraded(newImplementation);
    }

    /// @notice Returns the ERC-1967 implementation slot, identifying this as a UUPS-compatible
    ///         implementation (EIP-1822 proxiableUUID).
    /// @return The ERC-1967 implementation storage slot.
    function proxiableUUID() external pure returns (bytes32) {
        return IMPLEMENTATION_SLOT;
    }
}
