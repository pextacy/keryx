// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title ERC1967Proxy
/// @notice Minimal ERC-1967 transparent-slot proxy delegating all calls to an implementation.
contract ERC1967Proxy {
    /// @notice ERC-1967 implementation slot: keccak256("eip1967.proxy.implementation") - 1.
    bytes32 internal constant IMPLEMENTATION_SLOT =
        0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;
    /// @notice ERC-1967 admin slot: keccak256("eip1967.proxy.admin") - 1.
    bytes32 internal constant ADMIN_SLOT =
        0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103;

    /// @notice Emitted when the implementation address is upgraded.
    event Upgraded(address indexed implementation);
    /// @notice Emitted when the proxy admin is changed.
    event AdminChanged(address previousAdmin, address newAdmin);

    /// @notice Thrown when a non-admin calls an admin-only function.
    error NotAdmin();
    /// @notice Thrown when an implementation address is not a contract.
    error InvalidImplementation();

    /// @notice Deploys the proxy, sets the implementation and admin, and runs optional init data.
    /// @param implementation_ The initial implementation contract address.
    /// @param admin_ The admin authorized to upgrade and rotate the admin.
    /// @param initData Optional calldata delegatecalled into the implementation on construction.
    constructor(address implementation_, address admin_, bytes memory initData) {
        _setImplementation(implementation_);
        _setAdmin(admin_);

        if (initData.length > 0) {
            (bool success, bytes memory ret) = implementation_.delegatecall(initData);
            if (!success) {
                _revertWithReturndata(ret);
            }
        }
    }

    /// @notice Upgrades the proxy to a new implementation. Admin only.
    /// @param newImplementation The new implementation contract address.
    function upgradeTo(address newImplementation) external {
        if (msg.sender != _admin()) revert NotAdmin();
        _setImplementation(newImplementation);
    }

    /// @notice Rotates the proxy admin. Admin only.
    /// @param newAdmin The new admin address.
    function changeAdmin(address newAdmin) external {
        if (msg.sender != _admin()) revert NotAdmin();
        address previousAdmin = _admin();
        _setAdmin(newAdmin);
        emit AdminChanged(previousAdmin, newAdmin);
    }

    /// @notice Returns the current implementation address.
    function implementation() external view returns (address) {
        return _implementation();
    }

    /// @notice Returns the current admin address.
    function admin() external view returns (address) {
        return _admin();
    }

    /// @notice Delegates all unmatched calls to the current implementation.
    fallback() external payable {
        _delegate(_implementation());
    }

    /// @notice Accepts plain ether transfers, delegating to the implementation.
    receive() external payable {
        _delegate(_implementation());
    }

    /// @dev Reads the implementation address from the ERC-1967 slot.
    function _implementation() internal view returns (address impl) {
        bytes32 slot = IMPLEMENTATION_SLOT;
        assembly {
            impl := sload(slot)
        }
    }

    /// @dev Validates and writes the implementation address to the ERC-1967 slot.
    function _setImplementation(address newImplementation) internal {
        if (newImplementation.code.length == 0) revert InvalidImplementation();
        bytes32 slot = IMPLEMENTATION_SLOT;
        assembly {
            sstore(slot, newImplementation)
        }
        emit Upgraded(newImplementation);
    }

    /// @dev Reads the admin address from the ERC-1967 slot.
    function _admin() internal view returns (address adm) {
        bytes32 slot = ADMIN_SLOT;
        assembly {
            adm := sload(slot)
        }
    }

    /// @dev Writes the admin address to the ERC-1967 slot.
    function _setAdmin(address newAdmin) internal {
        bytes32 slot = ADMIN_SLOT;
        assembly {
            sstore(slot, newAdmin)
        }
    }

    /// @dev Delegatecalls into the implementation, forwarding calldata and returndata.
    function _delegate(address impl) internal {
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

    /// @dev Bubbles up a returndata revert reason, or reverts plainly if none.
    function _revertWithReturndata(bytes memory ret) internal pure {
        if (ret.length > 0) {
            assembly {
                revert(add(ret, 0x20), mload(ret))
            }
        }
        revert InvalidImplementation();
    }
}
