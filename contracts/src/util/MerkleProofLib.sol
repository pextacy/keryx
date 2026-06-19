// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title MerkleProofLib
/// @notice Verifies a keccak256 sorted-pair merkle proof against a root.
/// @dev Each proof element is hashed with the running hash by ordering the two
///      values numerically (sorted pair) before keccak256, so the tree must be
///      built with the same sorted-pair convention. Pure, no storage, no events.
library MerkleProofLib {
    /// @notice Returns true if `leaf` can be proven to belong to the tree
    ///         identified by `root` using `proof`.
    /// @param proof The sibling hashes from leaf to root (bottom-up order).
    /// @param root The expected merkle root.
    /// @param leaf The leaf to prove membership of.
    /// @return ok True when the computed root equals `root`.
    function verify(bytes32[] memory proof, bytes32 root, bytes32 leaf)
        internal
        pure
        returns (bool ok)
    {
        return processProof(proof, leaf) == root;
    }

    /// @notice Computes the merkle root implied by `leaf` and `proof`.
    /// @dev Folds each proof element into the running hash using a sorted pair
    ///      (the numerically smaller value is hashed first) to make the tree
    ///      order-independent at each level.
    /// @param proof The sibling hashes from leaf to root (bottom-up order).
    /// @param leaf The leaf to start the computation from.
    /// @return computedHash The reconstructed merkle root.
    function processProof(bytes32[] memory proof, bytes32 leaf)
        internal
        pure
        returns (bytes32 computedHash)
    {
        computedHash = leaf;
        uint256 length = proof.length;
        for (uint256 i = 0; i < length; ++i) {
            computedHash = _hashPair(computedHash, proof[i]);
        }
    }

    /// @notice Hashes two nodes as a sorted pair: keccak256 of the smaller value
    ///         concatenated with the larger value.
    /// @param a The first node.
    /// @param b The second node.
    /// @return result The sorted-pair keccak256 hash.
    function _hashPair(bytes32 a, bytes32 b) private pure returns (bytes32 result) {
        return a < b ? _efficientHash(a, b) : _efficientHash(b, a);
    }

    /// @notice keccak256 of the tight concatenation of `a` and `b` using scratch space.
    /// @param a The high-order 32 bytes.
    /// @param b The low-order 32 bytes.
    /// @return value The keccak256 hash of `a || b`.
    function _efficientHash(bytes32 a, bytes32 b) private pure returns (bytes32 value) {
        assembly {
            mstore(0x00, a)
            mstore(0x20, b)
            value := keccak256(0x00, 0x40)
        }
    }
}
