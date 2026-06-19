// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Owned} from "./auth/Owned.sol";
import {IIdentityRegistry} from "./interfaces/IIdentityRegistry.sol";

/// @title IdentityRegistry
/// @notice ERC-8004-inspired identity layer. Every Keryx author/agent is one identity
///         (`agentId`) bound to a wallet, plus a metadata URI (e.g. the source feed).
///         Self-sovereign `register()` for agents; `registerFor()` lets the owner seed
///         the curated author set. All N authors live in THIS ONE contract — the correct
///         EVM pattern (a mapping), not one contract per author.
contract IdentityRegistry is Owned, IIdentityRegistry {
    struct Agent {
        address wallet;
        string metadataURI;
        uint64 registeredAt;
    }

    uint256 public totalAgents;
    mapping(uint256 => Agent) internal _agents;
    mapping(address => uint256) internal _idOf;

    event AgentRegistered(uint256 indexed agentId, address indexed wallet, string metadataURI);
    event AgentUpdated(uint256 indexed agentId, address indexed wallet, string metadataURI);

    error AlreadyRegistered();
    error NotRegistered();
    error ZeroWallet();

    constructor(address owner_) Owned(owner_) {}

    /// @notice Register the caller as an agent identity.
    function register(string calldata metadataURI) external returns (uint256) {
        return _register(msg.sender, metadataURI);
    }

    /// @notice Owner seeds an author identity (curated registry / RSSHub ingest).
    function registerFor(address wallet, string calldata metadataURI) external onlyOwner returns (uint256) {
        return _register(wallet, metadataURI);
    }

    function _register(address wallet, string calldata metadataURI) internal returns (uint256 id) {
        if (wallet == address(0)) revert ZeroWallet();
        if (_idOf[wallet] != 0) revert AlreadyRegistered();
        id = ++totalAgents; // ids start at 1; 0 means "unregistered"
        _agents[id] = Agent({wallet: wallet, metadataURI: metadataURI, registeredAt: uint64(block.timestamp)});
        _idOf[wallet] = id;
        emit AgentRegistered(id, wallet, metadataURI);
    }

    /// @notice Update the caller's own metadata URI.
    function updateMetadata(string calldata metadataURI) external {
        uint256 id = _idOf[msg.sender];
        if (id == 0) revert NotRegistered();
        _agents[id].metadataURI = metadataURI;
        emit AgentUpdated(id, msg.sender, metadataURI);
    }

    function agentIdOf(address wallet) external view returns (uint256) {
        return _idOf[wallet];
    }

    function walletOf(uint256 agentId) external view returns (address) {
        return _agents[agentId].wallet;
    }

    function metadataOf(uint256 agentId) external view returns (string memory) {
        return _agents[agentId].metadataURI;
    }

    function isRegistered(address wallet) external view returns (bool) {
        return _idOf[wallet] != 0;
    }
}
