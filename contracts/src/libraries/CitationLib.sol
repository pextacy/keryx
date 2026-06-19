// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title CitationLib
/// @notice The on-chain citation record and its commitment. A settled answer carries a
///         set of these; the attestation commits to them via `hash()` so the signed
///         body stays compact while the full set is verifiable.
library CitationLib {
    struct Citation {
        bytes32 sourceId; // stable id of the cited source
        address author; // payee wallet (must be a registered identity)
        uint16 gBps; // grounding score in basis points (g * 10000)
        uint256 amount; // USDC atomic units settled to this author
    }

    /// @notice Deterministic commitment to a citation set (matches `att.citationsRoot`).
    function hash(Citation[] memory cites) internal pure returns (bytes32) {
        return keccak256(abi.encode(cites));
    }
}
