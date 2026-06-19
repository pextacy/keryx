// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "../auth/Owned.sol";

/// @title MetadataResolver
/// @notice Generic key->URI resolver for arbitrary off-chain metadata pointers
///         shared across the Keryx suite. The owner manages an authorization set;
///         the owner and any authorized caller may write records. Anyone may read.
contract MetadataResolver is Owned {
    /// @notice key => stored metadata value (typically a URI/pointer).
    mapping(bytes32 => string) internal _records;

    /// @notice Callers permitted to write records (in addition to the owner).
    mapping(address => bool) public authorized;

    /// @notice Emitted whenever a record is set or overwritten.
    event RecordSet(bytes32 indexed key, string value);

    /// @notice Emitted when a caller's write authorization changes.
    event AuthorizedSet(address indexed caller, bool allowed);

    /// @notice Thrown when a non-owner, non-authorized caller attempts a write.
    error NotAuthorized();

    /// @param owner_ Initial owner with admin rights over the authorization set.
    constructor(address owner_) Owned(owner_) {}

    /// @notice Restricts writes to the owner or an authorized caller.
    modifier onlyAuthorized() {
        if (msg.sender != owner && !authorized[msg.sender]) revert NotAuthorized();
        _;
    }

    /// @notice Grant or revoke write authorization for a caller.
    /// @param caller The address whose authorization is being changed.
    /// @param allowed True to grant write access, false to revoke.
    function setAuthorized(address caller, bool allowed) external onlyOwner {
        authorized[caller] = allowed;
        emit AuthorizedSet(caller, allowed);
    }

    /// @notice Set or overwrite the metadata value stored under a key.
    /// @param key The record key.
    /// @param value The metadata value (e.g. an off-chain URI) to store.
    function setRecord(bytes32 key, string calldata value) external onlyAuthorized {
        _records[key] = value;
        emit RecordSet(key, value);
    }

    /// @notice Resolve the metadata value stored under a key.
    /// @param key The record key to look up.
    /// @return The stored value, or an empty string if unset.
    function resolve(bytes32 key) external view returns (string memory) {
        return _records[key];
    }
}
