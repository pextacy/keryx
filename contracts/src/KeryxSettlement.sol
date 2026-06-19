// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Owned} from "./auth/Owned.sol";
import {IERC20} from "./interfaces/IERC20.sol";
import {IIdentityRegistry} from "./interfaces/IIdentityRegistry.sol";
import {IReputationRegistry} from "./interfaces/IReputationRegistry.sol";
import {AttestationLib} from "./libraries/AttestationLib.sol";
import {CitationLib} from "./libraries/CitationLib.sol";
import {CitationRegistry} from "./CitationRegistry.sol";
import {CitationSplitter} from "./CitationSplitter.sol";
import {KeryxToll} from "./KeryxToll.sol";

/// @title KeryxSettlement
/// @notice The orchestrator that turns a signed answer into on-chain settlement, tying
///         the whole suite together in one call:
///           1. commit + verify the signed attestation (CitationRegistry),
///           2. gate each citation on g >= T and a registered author (Toll + Identity),
///           3. pay each cited author their toll in USDC (CitationSplitter),
///           4. accrue earned reputation (ReputationRegistry).
///         Payment is on *citation*: a citation with g < T is rejected here, never paid —
///         the on-chain enforcement of "pay on citation, not on fetch."
contract KeryxSettlement is Owned {
    using CitationLib for CitationLib.Citation[];

    IERC20 public immutable usdc;
    CitationRegistry public immutable citations;
    IIdentityRegistry public immutable identity;
    IReputationRegistry public immutable reputation;
    CitationSplitter public immutable splitter;
    KeryxToll public immutable toll;

    event Settled(
        uint256 indexed attestationId,
        address indexed agent,
        address indexed payer,
        uint256 totalPaid,
        uint256 citationCount
    );

    error CitationsRootMismatch();
    error NotGrounded(bytes32 sourceId);
    error AuthorNotRegistered(address author);
    error AmountOutOfBand(uint256 amount);
    error NoCitations();

    constructor(
        address owner_,
        IERC20 usdc_,
        CitationRegistry citations_,
        IIdentityRegistry identity_,
        IReputationRegistry reputation_,
        CitationSplitter splitter_,
        KeryxToll toll_
    ) Owned(owner_) {
        usdc = usdc_;
        citations = citations_;
        identity = identity_;
        reputation = reputation_;
        splitter = splitter_;
        toll = toll_;
    }

    /// @notice Settle one answer: record the attestation, then pay + accrue per cited
    ///         source. USDC is pulled from `msg.sender` (the paying agent), who must have
    ///         approved the CitationSplitter for the total. Returns the attestation id and
    ///         the total USDC paid.
    function settle(AttestationLib.Attestation calldata att, CitationLib.Citation[] calldata cites, bytes calldata sig)
        external
        returns (uint256 attestationId, uint256 totalPaid)
    {
        if (cites.length == 0) revert NoCitations();
        if (att.citationsRoot != CitationLib.hash(cites)) revert CitationsRootMismatch();

        // 1. Verify + log the signed attestation (reverts on bad sig / replay).
        attestationId = citations.recordAttestation(att, sig);

        // 2-4. Gate, accrue, and assemble the payout set.
        address[] memory authors = new address[](cites.length);
        uint256[] memory amounts = new uint256[](cites.length);
        uint256 floor = toll.floorAtomic();
        uint256 maxToll = toll.tollMax();

        for (uint256 i = 0; i < cites.length; i++) {
            CitationLib.Citation calldata c = cites[i];
            if (!toll.isCited(c.gBps)) revert NotGrounded(c.sourceId); // g < T -> never paid
            uint256 agentId = identity.agentIdOf(c.author);
            if (agentId == 0) revert AuthorNotRegistered(c.author);
            if (c.amount < floor || c.amount > maxToll) revert AmountOutOfBand(c.amount);

            reputation.accrue(agentId, c.gBps);
            authors[i] = c.author;
            amounts[i] = c.amount;
            totalPaid += c.amount;
        }

        // 5. Pull USDC from the paying agent to each cited author.
        splitter.distribute(usdc, msg.sender, authors, amounts);

        emit Settled(attestationId, att.agent, msg.sender, totalPaid, cites.length);
    }
}
