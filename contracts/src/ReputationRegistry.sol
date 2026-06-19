// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Owned} from "./auth/Owned.sol";
import {IReputationRegistry} from "./interfaces/IReputationRegistry.sol";
import {IIdentityRegistry} from "./interfaces/IIdentityRegistry.sol";
import {GroundingMath} from "./libraries/GroundingMath.sol";

/// @title ReputationRegistry
/// @notice ERC-8004-inspired reputation. Each settled citation accrues weighted feedback
///         (the grounding score `gBps`) to the cited author's identity. This is the
///         on-chain signal "which sources agents keep grounding answers in" — earned, not
///         self-declared. Only authorized writers (the settlement contract) may accrue.
contract ReputationRegistry is Owned, IReputationRegistry {
    IIdentityRegistry public immutable identity;

    struct Rep {
        uint256 score; // sum of gBps across settled citations
        uint256 citations; // count of settled citations
    }

    mapping(uint256 => Rep) internal _rep;
    mapping(address => bool) public authorized;

    event AuthorizedSet(address indexed writer, bool allowed);
    event ReputationAccrued(uint256 indexed agentId, uint16 gBps, uint256 newScore, uint256 newCount);

    error NotAuthorized();
    error UnknownAgent();
    error InvalidScore();

    modifier onlyAuthorized() {
        if (!authorized[msg.sender]) revert NotAuthorized();
        _;
    }

    constructor(address owner_, IIdentityRegistry identity_) Owned(owner_) {
        identity = identity_;
    }

    function setAuthorized(address writer, bool allowed) external onlyOwner {
        authorized[writer] = allowed;
        emit AuthorizedSet(writer, allowed);
    }

    function accrue(uint256 agentId, uint16 gBps) external onlyAuthorized {
        if (gBps > GroundingMath.BPS) revert InvalidScore();
        if (identity.walletOf(agentId) == address(0)) revert UnknownAgent();
        Rep storage r = _rep[agentId];
        r.score += gBps;
        r.citations += 1;
        emit ReputationAccrued(agentId, gBps, r.score, r.citations);
    }

    function reputationOf(uint256 agentId) external view returns (uint256 score, uint256 citations, uint256 avgBps) {
        Rep storage r = _rep[agentId];
        score = r.score;
        citations = r.citations;
        avgBps = citations == 0 ? 0 : score / citations;
    }
}
