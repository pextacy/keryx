// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {MerkleProofLib} from "../util/MerkleProofLib.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title MerkleDistributor
/// @notice Merkle-root gated one-shot claims of tokens against a published
///         allocation tree. Each (index, account, amount) leaf may be claimed
///         exactly once; eligibility is proven against a governor-set root.
contract MerkleDistributor is ReentrancyGuard {
    using SafeTransferLib for IERC20;
    using MerkleProofLib for bytes32[];

    /// @notice Role registry consulted for governor authorization.
    AccessController public immutable acl;

    /// @notice The token distributed to eligible claimants.
    IERC20 public immutable token;

    /// @notice The current merkle root committing the allocation tree.
    bytes32 public merkleRoot;

    /// @dev Packed bitmap of claimed indices: word index => 256-bit claim word.
    mapping(uint256 => uint256) internal _claimedBitMap;

    /// @notice Emitted when the governor publishes a new allocation root.
    event MerkleRootSet(bytes32 root);

    /// @notice Emitted when an allocation leaf is successfully claimed.
    event Claimed(uint256 indexed index, address indexed account, uint256 amount);

    /// @notice Thrown when a non-governor calls a governor-only function.
    error NotGovernor();

    /// @notice Thrown when the leaf index has already been claimed.
    error AlreadyClaimed();

    /// @notice Thrown when the supplied merkle proof does not verify against the root.
    error InvalidProof();

    /// @notice Reverts unless the caller holds the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the distributor to its access controller and token.
    /// @param acl_ The role registry used for authorization decisions.
    /// @param token_ The token distributed against the allocation tree.
    constructor(AccessController acl_, IERC20 token_) {
        acl = acl_;
        token = token_;
    }

    /// @notice Publishes a new allocation merkle root.
    /// @dev Governor-only. Replacing the root rolls over to a new allocation;
    ///      the claimed bitmap is intentionally not reset, so callers must use
    ///      a fresh index space when reusing this distributor for a new tree.
    /// @param root The merkle root committing the new allocation tree.
    function setMerkleRoot(bytes32 root) external onlyGovernor {
        merkleRoot = root;
        emit MerkleRootSet(root);
    }

    /// @notice Returns whether the leaf at `index` has already been claimed.
    /// @param index The allocation index to query.
    /// @return claimed True when the index has been consumed.
    function isClaimed(uint256 index) external view returns (bool) {
        return _isClaimed(index);
    }

    /// @notice Claims an allocation leaf, transferring `amount` of token to `account`.
    /// @dev Anyone may submit a valid proof on behalf of `account`; tokens always
    ///      flow to the leaf's `account`. Checks-effects-interactions: the index is
    ///      marked claimed before the external transfer, and the call is guarded
    ///      against reentrancy.
    /// @param index The unique allocation index for this leaf.
    /// @param account The beneficiary encoded in the leaf and recipient of tokens.
    /// @param amount The token amount encoded in the leaf.
    /// @param proof The merkle proof of inclusion against the current root.
    function claim(
        uint256 index,
        address account,
        uint256 amount,
        bytes32[] calldata proof
    ) external nonReentrant {
        if (_isClaimed(index)) revert AlreadyClaimed();

        bytes32 leaf = keccak256(abi.encodePacked(index, account, amount));
        if (!proof.verify(merkleRoot, leaf)) revert InvalidProof();

        _setClaimed(index);

        emit Claimed(index, account, amount);

        token.safeTransfer(account, amount);
    }

    /// @dev Reads the claimed flag for `index` from the packed bitmap.
    function _isClaimed(uint256 index) internal view returns (bool) {
        uint256 wordIndex = index >> 8;
        uint256 bitIndex = index & 0xff;
        uint256 word = _claimedBitMap[wordIndex];
        uint256 mask = uint256(1) << bitIndex;
        return word & mask == mask;
    }

    /// @dev Marks `index` as claimed in the packed bitmap.
    function _setClaimed(uint256 index) internal {
        uint256 wordIndex = index >> 8;
        uint256 bitIndex = index & 0xff;
        _claimedBitMap[wordIndex] |= (uint256(1) << bitIndex);
    }
}
