// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title AttestationLib
/// @notice EIP-712 typed hashing + signer recovery for the citation attestation —
///         the on-chain analog of agent/attestation/ (the signed
///         {query_hash, answer_hash, citations[], agent_pubkey, ts}). The agent signs
///         the typed digest with its secp256k1 key; the CitationRegistry recovers the
///         signer and requires it to equal the declared agent.
library AttestationLib {
    /// @dev The attestation as committed on-chain. `citationsRoot` commits to the full
    ///      citation set (keccak of the encoded citations) so the body stays compact.
    struct Attestation {
        bytes32 queryHash;
        bytes32 answerHash;
        bytes32 citationsRoot;
        address agent;
        uint64 ts;
        uint256 nonce;
    }

    bytes32 internal constant ATTESTATION_TYPEHASH = keccak256(
        "Attestation(bytes32 queryHash,bytes32 answerHash,bytes32 citationsRoot,address agent,uint64 ts,uint256 nonce)"
    );

    bytes32 internal constant EIP712_DOMAIN_TYPEHASH =
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");

    function domainSeparator(address verifyingContract) internal view returns (bytes32) {
        return keccak256(
            abi.encode(
                EIP712_DOMAIN_TYPEHASH,
                keccak256(bytes("Keryx")),
                keccak256(bytes("1")),
                block.chainid,
                verifyingContract
            )
        );
    }

    function hashStruct(Attestation memory a) internal pure returns (bytes32) {
        return
            keccak256(
                abi.encode(ATTESTATION_TYPEHASH, a.queryHash, a.answerHash, a.citationsRoot, a.agent, a.ts, a.nonce)
            );
    }

    function digest(Attestation memory a, bytes32 sep) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked("\x19\x01", sep, hashStruct(a)));
    }

    /// @notice Recover the signer of an attestation from a 65-byte signature.
    function recoverSigner(Attestation memory a, bytes32 sep, bytes memory sig) internal pure returns (address) {
        if (sig.length != 65) return address(0);
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := mload(add(sig, 0x20))
            s := mload(add(sig, 0x40))
            v := byte(0, mload(add(sig, 0x60)))
        }
        if (v < 27) v += 27;
        // Reject malleable high-s signatures (EIP-2).
        if (uint256(s) > 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0) {
            return address(0);
        }
        return ecrecover(digest(a, sep), v, r, s);
    }
}
