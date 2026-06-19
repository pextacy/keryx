// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "./DisputeManager.sol";

/// @title EvidenceRegistry
/// @notice Append-only log of evidence hashes/URIs submitted per dispute by either party.
contract EvidenceRegistry {
    /// @notice Dispute manager whose disputes this registry logs evidence against.
    DisputeManager public immutable disputes;

    /// @notice A single piece of evidence attached to a dispute.
    struct Evidence {
        address submitter;
        bytes32 evidenceHash;
        string uri;
        uint64 submittedAt;
    }

    /// @dev disputeId => append-only list of submitted evidence.
    mapping(uint256 => Evidence[]) internal _evidence;

    event EvidenceSubmitted(
        uint256 indexed disputeId,
        address indexed submitter,
        bytes32 evidenceHash,
        string uri
    );

    error EmptyEvidence();

    /// @notice Wire the registry to the dispute manager it serves.
    constructor(DisputeManager disputes_) {
        disputes = disputes_;
    }

    /// @notice Append a new piece of evidence to a dispute's log.
    /// @param disputeId The dispute the evidence pertains to.
    /// @param evidenceHash Content hash of the evidence payload.
    /// @param uri Off-chain pointer to the evidence content.
    function submitEvidence(
        uint256 disputeId,
        bytes32 evidenceHash,
        string calldata uri
    ) external {
        if (evidenceHash == bytes32(0) && bytes(uri).length == 0) {
            revert EmptyEvidence();
        }

        _evidence[disputeId].push(
            Evidence({
                submitter: msg.sender,
                evidenceHash: evidenceHash,
                uri: uri,
                submittedAt: uint64(block.timestamp)
            })
        );

        emit EvidenceSubmitted(disputeId, msg.sender, evidenceHash, uri);
    }

    /// @notice Number of evidence entries logged for a dispute.
    function evidenceCount(uint256 disputeId) external view returns (uint256) {
        return _evidence[disputeId].length;
    }

    /// @notice Read a single evidence entry for a dispute by index.
    function evidenceAt(uint256 disputeId, uint256 index)
        external
        view
        returns (Evidence memory)
    {
        return _evidence[disputeId][index];
    }
}
