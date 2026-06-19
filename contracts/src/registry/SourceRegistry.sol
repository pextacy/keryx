// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Owned} from "../auth/Owned.sol";
import {IIdentityRegistry} from "../interfaces/IIdentityRegistry.sol";

/// @title SourceRegistry
/// @notice Canonical catalog of citable sources. Each `sourceId` maps to a URI, an
///         owning agent identity, a content hash and an active flag. The owner plus a
///         set of authorized callers (e.g. ingestion or licensing modules) may register
///         and mutate entries; ownership of an entry is anchored to a registered agentId
///         in the IdentityRegistry so downstream citation/settlement flows can resolve a
///         payable author wallet.
contract SourceRegistry is Owned {
    /// @notice Identity registry used to validate that an owning agentId exists.
    IIdentityRegistry public immutable identity;

    struct Source {
        uint256 ownerAgentId;
        string uri;
        bytes32 contentHash;
        bool active;
        uint64 registeredAt;
    }

    /// @dev sourceId => source record. `registeredAt == 0` denotes a non-existent entry.
    mapping(bytes32 => Source) internal _sources;

    /// @notice Total number of distinct sources ever registered.
    uint256 public totalSources;

    /// @notice Callers (besides the owner) permitted to register and mutate sources.
    mapping(address => bool) public authorized;

    event SourceRegistered(bytes32 indexed sourceId, uint256 indexed ownerAgentId, string uri);
    event SourceUpdated(bytes32 indexed sourceId, string uri, bool active);
    event AuthorizedSet(address indexed caller, bool allowed);

    error NotAuthorized();
    error UnknownAgent();
    error AlreadyExists();
    error UnknownSource();

    /// @dev Owner is always authorized implicitly; the `authorized` map extends write
    ///      access to additional modules.
    modifier onlyAuthorized() {
        if (msg.sender != owner && !authorized[msg.sender]) revert NotAuthorized();
        _;
    }

    constructor(address owner_, IIdentityRegistry identity_) Owned(owner_) {
        if (address(identity_) == address(0)) revert ZeroAddress();
        identity = identity_;
    }

    /// @notice Grant or revoke write access for a caller.
    function setAuthorized(address caller, bool allowed) external onlyOwner {
        if (caller == address(0)) revert ZeroAddress();
        authorized[caller] = allowed;
        emit AuthorizedSet(caller, allowed);
    }

    /// @notice Register a new citable source.
    /// @param sourceId   Caller-chosen unique identifier for the source.
    /// @param ownerAgentId Registered agent identity that owns the source.
    /// @param uri        Off-chain pointer (e.g. ipfs/https) to the source content.
    /// @param contentHash Cryptographic hash binding the URI to its content.
    function registerSource(
        bytes32 sourceId,
        uint256 ownerAgentId,
        string calldata uri,
        bytes32 contentHash
    ) external onlyAuthorized {
        // Checks.
        if (_sources[sourceId].registeredAt != 0) revert AlreadyExists();
        if (identity.walletOf(ownerAgentId) == address(0)) revert UnknownAgent();

        // Effects.
        _sources[sourceId] = Source({
            ownerAgentId: ownerAgentId,
            uri: uri,
            contentHash: contentHash,
            active: true,
            registeredAt: uint64(block.timestamp)
        });
        unchecked {
            totalSources++;
        }

        emit SourceRegistered(sourceId, ownerAgentId, uri);
    }

    /// @notice Toggle the active flag of an existing source.
    function setActive(bytes32 sourceId, bool active) external onlyAuthorized {
        Source storage s = _sources[sourceId];
        if (s.registeredAt == 0) revert UnknownSource();

        s.active = active;

        emit SourceUpdated(sourceId, s.uri, active);
    }

    /// @notice Update the off-chain URI of an existing source.
    function updateUri(bytes32 sourceId, string calldata uri) external onlyAuthorized {
        Source storage s = _sources[sourceId];
        if (s.registeredAt == 0) revert UnknownSource();

        s.uri = uri;

        emit SourceUpdated(sourceId, uri, s.active);
    }

    /// @notice Return the full record for a source.
    function getSource(bytes32 sourceId) external view returns (Source memory) {
        Source memory s = _sources[sourceId];
        if (s.registeredAt == 0) revert UnknownSource();
        return s;
    }

    /// @notice Whether a source exists and is currently active.
    function isActive(bytes32 sourceId) external view returns (bool) {
        Source storage s = _sources[sourceId];
        return s.registeredAt != 0 && s.active;
    }
}
