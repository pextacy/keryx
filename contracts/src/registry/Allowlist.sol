// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessController} from "../access/AccessController.sol";
import {MerkleProofLib} from "../util/MerkleProofLib.sol";

/// @title Allowlist
/// @notice Governor-managed allow/deny list (with optional merkle-root mode)
///         gating participation in the Keryx suite. An account is considered
///         allowed when it is not denied and either explicitly allowed, or
///         (in merkle mode) provably included under the configured root.
contract Allowlist {
    using MerkleProofLib for bytes32[];

    /// @notice Role registry consulted for governor authorization.
    AccessController public immutable acl;

    /// @notice Active merkle root used when `merkleMode` is enabled.
    bytes32 public merkleRoot;

    /// @notice Whether membership is evaluated against `merkleRoot` proofs.
    bool public merkleMode;

    /// @notice Explicit per-account allow flags (used outside merkle mode).
    mapping(address => bool) public allowed;

    /// @notice Explicit per-account deny flags (always override allow).
    mapping(address => bool) public denied;

    /// @notice Emitted when an account's explicit allow status changes.
    event Allowed(address indexed account, bool status);

    /// @notice Emitted when an account's explicit deny status changes.
    event Denied(address indexed account, bool status);

    /// @notice Emitted when the merkle root and/or merkle mode is updated.
    event MerkleRootSet(bytes32 root, bool merkleMode);

    /// @notice Thrown when a non-governor calls a governor-gated function.
    error NotGovernor();

    /// @notice Restricts a function to holders of the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the allowlist to the shared access controller.
    /// @param acl_ The role registry providing governor authorization.
    constructor(AccessController acl_) {
        acl = acl_;
    }

    /// @notice Sets the explicit allow status for an account.
    /// @param account The account whose allow flag is updated.
    /// @param status True to allow, false to clear the allow flag.
    function setAllowed(address account, bool status) external onlyGovernor {
        allowed[account] = status;
        emit Allowed(account, status);
    }

    /// @notice Sets the explicit deny status for an account.
    /// @dev A denied account is never allowed regardless of allow flags or
    ///      merkle proofs.
    /// @param account The account whose deny flag is updated.
    /// @param status True to deny, false to clear the deny flag.
    function setDenied(address account, bool status) external onlyGovernor {
        denied[account] = status;
        emit Denied(account, status);
    }

    /// @notice Configures the merkle root and toggles merkle membership mode.
    /// @param root The new merkle root used for proof-based membership.
    /// @param merkleMode_ True to evaluate membership via merkle proofs.
    function setMerkleRoot(bytes32 root, bool merkleMode_) external onlyGovernor {
        merkleRoot = root;
        merkleMode = merkleMode_;
        emit MerkleRootSet(root, merkleMode_);
    }

    /// @notice Returns whether an account is allowed based on explicit flags.
    /// @dev In merkle mode an empty proof cannot prove inclusion, so only
    ///      explicitly allowlisted (and non-denied) accounts pass here; use
    ///      `isAllowedWithProof` to supply a proof.
    /// @param account The account to check.
    /// @return ok True when the account is permitted to participate.
    function isAllowed(address account) external view returns (bool ok) {
        if (denied[account]) return false;
        return allowed[account];
    }

    /// @notice Returns whether an account is allowed, optionally via merkle proof.
    /// @dev Deny flags always take precedence. When `merkleMode` is enabled the
    ///      account is allowed if it is explicitly allowlisted or the supplied
    ///      proof verifies its leaf against `merkleRoot`. When merkle mode is
    ///      disabled only the explicit allow flag is consulted.
    /// @param account The account to check.
    /// @param proof The sorted-pair merkle proof for the account's leaf.
    /// @return ok True when the account is permitted to participate.
    function isAllowedWithProof(address account, bytes32[] calldata proof)
        external
        view
        returns (bool ok)
    {
        if (denied[account]) return false;
        if (allowed[account]) return true;
        if (!merkleMode) return false;

        bytes32 leaf = keccak256(abi.encodePacked(account));
        return MerkleProofLib.verify(proof, merkleRoot, leaf);
    }
}
