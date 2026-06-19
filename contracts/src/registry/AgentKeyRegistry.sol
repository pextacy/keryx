// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Owned} from "../auth/Owned.sol";
import {IIdentityRegistry} from "../interfaces/IIdentityRegistry.sol";

/// @title AgentKeyRegistry
/// @notice Tracks the set of active signing keys bound to each agent identity and
///         supports key rotation and revocation. The wallet that owns an agent id
///         (per the IdentityRegistry) manages that agent's keys; the contract owner
///         retains administrative override for emergency rotation/revocation.
/// @dev Authorization is derived live from the IdentityRegistry: only the wallet
///      currently mapped to `agentId` (or the contract owner) may mutate that agent's
///      keys. State changes follow checks-effects-interactions; there are no external
///      value transfers so the flow is purely internal bookkeeping.
contract AgentKeyRegistry is Owned {
    /// @notice Identity registry mapping agentId <-> controlling wallet.
    IIdentityRegistry public immutable identity;

    /// @notice agentId => key => active flag.
    mapping(uint256 => mapping(address => bool)) internal _activeKeys;

    /// @notice agentId => its designated primary signing key.
    mapping(uint256 => address) public primaryKey;

    /// @notice Emitted when a key becomes active for an agent.
    event KeyAdded(uint256 indexed agentId, address indexed key);
    /// @notice Emitted when a previously active key is revoked.
    event KeyRevoked(uint256 indexed agentId, address indexed key);
    /// @notice Emitted when an agent's primary key is set.
    event PrimaryKeySet(uint256 indexed agentId, address indexed key);

    /// @notice Caller is neither the agent's controlling wallet nor the contract owner.
    error NotAgentOwner();
    /// @notice The supplied agentId is not registered in the identity registry.
    error UnknownAgent();
    /// @notice The supplied key is not currently active for the agent.
    error KeyNotActive();

    /// @notice Zero address supplied where a non-zero key was required.
    error ZeroKey();
    /// @notice Key already active for the agent.
    error KeyAlreadyActive();

    /// @param owner_ Administrative owner with override authority.
    /// @param identity_ The identity registry used to resolve agent controllers.
    constructor(address owner_, IIdentityRegistry identity_) Owned(owner_) {
        if (address(identity_) == address(0)) revert ZeroAddress();
        identity = identity_;
    }

    /// @dev Reverts unless the agent exists and msg.sender controls it (or is owner).
    function _authorize(uint256 agentId) internal view {
        address wallet = identity.walletOf(agentId);
        if (wallet == address(0)) revert UnknownAgent();
        if (msg.sender != wallet && msg.sender != owner) revert NotAgentOwner();
    }

    /// @notice Activate a new signing key for `agentId`.
    /// @param agentId The agent identity gaining the key.
    /// @param key The signing key to activate.
    function addKey(uint256 agentId, address key) external {
        if (key == address(0)) revert ZeroKey();
        _authorize(agentId);
        if (_activeKeys[agentId][key]) revert KeyAlreadyActive();

        _activeKeys[agentId][key] = true;

        // Bootstrap the primary key on first activation for convenience.
        if (primaryKey[agentId] == address(0)) {
            primaryKey[agentId] = key;
            emit PrimaryKeySet(agentId, key);
        }

        emit KeyAdded(agentId, key);
    }

    /// @notice Revoke an active signing key for `agentId`.
    /// @param agentId The agent identity losing the key.
    /// @param key The signing key to revoke.
    function revokeKey(uint256 agentId, address key) external {
        _authorize(agentId);
        if (!_activeKeys[agentId][key]) revert KeyNotActive();

        _activeKeys[agentId][key] = false;

        // Clear the primary designation if the revoked key was primary.
        if (primaryKey[agentId] == key) {
            primaryKey[agentId] = address(0);
            emit PrimaryKeySet(agentId, address(0));
        }

        emit KeyRevoked(agentId, key);
    }

    /// @notice Designate an already-active key as the agent's primary signing key.
    /// @param agentId The agent identity.
    /// @param key The active key to promote to primary.
    function setPrimaryKey(uint256 agentId, address key) external {
        if (key == address(0)) revert ZeroKey();
        _authorize(agentId);
        if (!_activeKeys[agentId][key]) revert KeyNotActive();

        primaryKey[agentId] = key;
        emit PrimaryKeySet(agentId, key);
    }

    /// @notice Whether `key` is currently an active signing key for `agentId`.
    function isActiveKey(uint256 agentId, address key) external view returns (bool) {
        return _activeKeys[agentId][key];
    }
}
