// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title Owned
/// @notice Minimal single-owner access control. Dependency-free (no OpenZeppelin) so
///         the Keryx suite builds offline. `onlyOwner` gates admin; ownership is
///         two-step-free but emits on transfer for off-chain indexing.
abstract contract Owned {
    address public owner;

    event OwnershipTransferred(address indexed from, address indexed to);

    error NotOwner();
    error ZeroAddress();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    constructor(address owner_) {
        if (owner_ == address(0)) revert ZeroAddress();
        owner = owner_;
        emit OwnershipTransferred(address(0), owner_);
    }

    function transferOwnership(address to) external onlyOwner {
        if (to == address(0)) revert ZeroAddress();
        emit OwnershipTransferred(owner, to);
        owner = to;
    }
}
