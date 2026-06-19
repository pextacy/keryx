// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "../auth/Owned.sol";

/// @title NonceManager
/// @notice Per-account sequential and per-key bitmap nonce/replay tracking shared by
///         meta-tx style flows. Authorized caller contracts (e.g. routers, settlement
///         relays) consume nonces here so that signed user operations cannot be replayed.
///         Two independent schemes are offered: a monotonic sequential counter per
///         account, and a sparse 256-bit-word bitmap allowing arbitrary, unordered
///         single-use nonces.
contract NonceManager is Owned {
    /// @notice Next expected sequential nonce per account (also equals count consumed).
    mapping(address => uint256) public sequentialNonce;

    /// @notice Per-account word-packed bitmap of consumed unordered nonces.
    ///         Outer key: account. Inner key: word index (nonce >> 8). Value: 256-bit word.
    mapping(address => mapping(uint256 => uint256)) internal _bitmap;

    /// @notice Whether a caller is permitted to consume nonces on behalf of accounts.
    mapping(address => bool) public authorized;

    /// @notice Emitted when an address is granted or revoked authorization.
    event AuthorizedSet(address indexed caller, bool allowed);

    /// @notice Emitted whenever a nonce (sequential or bitmap) is marked consumed.
    event NonceUsed(address indexed account, uint256 nonce);

    /// @notice Thrown when a non-authorized caller attempts a consuming operation.
    error NotAuthorized();

    /// @notice Thrown when a bitmap nonce has already been consumed.
    error NonceAlreadyUsed();

    /// @notice Restricts a function to authorized consumer contracts.
    modifier onlyAuthorized() {
        if (!authorized[msg.sender]) revert NotAuthorized();
        _;
    }

    /// @param owner_ Initial owner permitted to manage the authorization set.
    constructor(address owner_) Owned(owner_) {}

    /// @notice Grant or revoke a caller's authorization to consume nonces.
    /// @param caller The contract or account whose authorization changes.
    /// @param allowed True to authorize, false to revoke.
    function setAuthorized(address caller, bool allowed) external onlyOwner {
        authorized[caller] = allowed;
        emit AuthorizedSet(caller, allowed);
    }

    /// @notice Consume the next sequential nonce for an account.
    /// @param account The account whose sequential counter is advanced.
    /// @return used The nonce value that was consumed by this call.
    function useSequential(address account) external onlyAuthorized returns (uint256 used) {
        // Effects: read-then-increment so the returned value is the consumed slot.
        used = sequentialNonce[account];
        sequentialNonce[account] = used + 1;
        emit NonceUsed(account, used);
    }

    /// @notice Consume a specific unordered nonce from an account's bitmap.
    /// @dev Reverts with NonceAlreadyUsed if the bit was already set.
    /// @param account The account the nonce belongs to.
    /// @param nonce The arbitrary nonce value to mark as consumed.
    function useNonce(address account, uint256 nonce) external onlyAuthorized {
        uint256 wordIndex = nonce >> 8;
        uint256 bit = 1 << (nonce & 0xff);
        uint256 word = _bitmap[account][wordIndex];
        if (word & bit != 0) revert NonceAlreadyUsed();
        _bitmap[account][wordIndex] = word | bit;
        emit NonceUsed(account, nonce);
    }

    /// @notice Query whether a bitmap nonce has been consumed for an account.
    /// @param account The account to query.
    /// @param nonce The nonce value to check.
    /// @return True if the nonce has already been consumed.
    function isUsed(address account, uint256 nonce) external view returns (bool) {
        uint256 wordIndex = nonce >> 8;
        uint256 bit = 1 << (nonce & 0xff);
        return _bitmap[account][wordIndex] & bit != 0;
    }
}
