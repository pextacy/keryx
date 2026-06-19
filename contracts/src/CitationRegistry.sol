// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Owned} from "./auth/Owned.sol";
import {AttestationLib} from "./libraries/AttestationLib.sol";

/// @title CitationRegistry
/// @notice On-chain log of signed citation attestations — the audit trail behind every
///         payment (the on-chain analog of agent/attestation/). Verifies the agent's
///         EIP-712 signature, rejects replays by digest, and stores the attestation body.
///         Recording is authorized-only so it stays bound to the settlement path.
contract CitationRegistry is Owned {
    using AttestationLib for AttestationLib.Attestation;

    bytes32 public immutable DOMAIN_SEPARATOR;

    struct Stored {
        bytes32 queryHash;
        bytes32 answerHash;
        bytes32 citationsRoot;
        address agent;
        uint64 ts;
        uint256 nonce;
        uint64 recordedAt;
    }

    uint256 public totalAttestations;
    mapping(uint256 => Stored) internal _attestations;
    mapping(bytes32 => bool) public consumed; // digest -> recorded (replay guard)
    mapping(address => bool) public authorized;

    event AuthorizedSet(address indexed caller, bool allowed);
    event AttestationRecorded(uint256 indexed id, address indexed agent, bytes32 digest, bytes32 citationsRoot);

    error NotAuthorized();
    error BadSignature();
    error AlreadyRecorded();

    modifier onlyAuthorized() {
        if (!authorized[msg.sender]) revert NotAuthorized();
        _;
    }

    constructor(address owner_) Owned(owner_) {
        DOMAIN_SEPARATOR = AttestationLib.domainSeparator(address(this));
    }

    function setAuthorized(address caller, bool allowed) external onlyOwner {
        authorized[caller] = allowed;
        emit AuthorizedSet(caller, allowed);
    }

    /// @notice Verify + store a signed attestation. Reverts on bad signature or replay.
    function recordAttestation(AttestationLib.Attestation calldata att, bytes calldata sig)
        external
        onlyAuthorized
        returns (uint256 id)
    {
        address signer = AttestationLib.recoverSigner(att, DOMAIN_SEPARATOR, sig);
        if (signer == address(0) || signer != att.agent) revert BadSignature();

        bytes32 d = AttestationLib.digest(att, DOMAIN_SEPARATOR);
        if (consumed[d]) revert AlreadyRecorded();
        consumed[d] = true;

        id = ++totalAttestations;
        _attestations[id] = Stored({
            queryHash: att.queryHash,
            answerHash: att.answerHash,
            citationsRoot: att.citationsRoot,
            agent: att.agent,
            ts: att.ts,
            nonce: att.nonce,
            recordedAt: uint64(block.timestamp)
        });
        emit AttestationRecorded(id, att.agent, d, att.citationsRoot);
    }

    /// @notice Recover the signer of an attestation (view helper for clients).
    function recover(AttestationLib.Attestation calldata att, bytes calldata sig) external view returns (address) {
        return AttestationLib.recoverSigner(att, DOMAIN_SEPARATOR, sig);
    }

    function getAttestation(uint256 id) external view returns (Stored memory) {
        return _attestations[id];
    }
}
