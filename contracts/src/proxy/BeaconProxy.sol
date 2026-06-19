// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {UpgradeableBeacon} from "./UpgradeableBeacon.sol";

/// @title BeaconProxy
/// @notice Proxy that resolves its implementation from an UpgradeableBeacon at
///         call time, delegating all calls to the beacon's current implementation.
contract BeaconProxy {
    /// @notice Storage slot holding the beacon address.
    /// @dev keccak256("eip1967.proxy.beacon") - 1, per the ERC-1967 convention.
    bytes32 internal constant BEACON_SLOT =
        0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50;

    /// @notice Emitted when the beacon address is written into BEACON_SLOT.
    event BeaconSet(address indexed beacon);

    /// @notice Thrown when the provided beacon is not a valid contract.
    error InvalidBeacon();

    /// @notice Wires the proxy to a beacon and optionally runs initialization
    ///         data against the beacon's current implementation.
    /// @param beacon_ Address of the UpgradeableBeacon supplying implementations.
    /// @param initData Optional calldata delegatecalled to the implementation.
    constructor(address beacon_, bytes memory initData) {
        _setBeacon(beacon_);
        if (initData.length > 0) {
            address impl = UpgradeableBeacon(beacon_).implementation();
            if (impl.code.length == 0) revert InvalidBeacon();
            (bool ok, bytes memory ret) = impl.delegatecall(initData);
            if (!ok) {
                // Bubble up the revert reason from the implementation.
                assembly {
                    revert(add(ret, 0x20), mload(ret))
                }
            }
        }
    }

    /// @notice Returns the beacon address backing this proxy.
    /// @return The address stored in BEACON_SLOT.
    function beacon() external view returns (address) {
        return _beacon();
    }

    /// @notice Returns the implementation currently advertised by the beacon.
    /// @return The implementation address used for delegation.
    function implementation() external view returns (address) {
        return _implementation();
    }

    /// @notice Delegates all unmatched calls to the beacon's implementation.
    fallback() external payable {
        _delegate(_implementation());
    }

    /// @notice Delegates bare value transfers to the beacon's implementation.
    receive() external payable {
        _delegate(_implementation());
    }

    /// @dev Validates and stores the beacon address into BEACON_SLOT.
    function _setBeacon(address beacon_) private {
        if (beacon_.code.length == 0) revert InvalidBeacon();
        bytes32 slot = BEACON_SLOT;
        assembly {
            sstore(slot, beacon_)
        }
        emit BeaconSet(beacon_);
    }

    /// @dev Reads the beacon address from BEACON_SLOT.
    function _beacon() private view returns (address beacon_) {
        bytes32 slot = BEACON_SLOT;
        assembly {
            beacon_ := sload(slot)
        }
    }

    /// @dev Resolves the implementation address from the configured beacon.
    function _implementation() private view returns (address) {
        return UpgradeableBeacon(_beacon()).implementation();
    }

    /// @dev Delegates the current call to `impl`, forwarding calldata, value,
    ///      and returning or bubbling the result verbatim.
    function _delegate(address impl) private {
        assembly {
            calldatacopy(0, 0, calldatasize())
            let result := delegatecall(gas(), impl, 0, calldatasize(), 0, 0)
            returndatacopy(0, 0, returndatasize())
            switch result
            case 0 {
                revert(0, returndatasize())
            }
            default {
                return(0, returndatasize())
            }
        }
    }
}
