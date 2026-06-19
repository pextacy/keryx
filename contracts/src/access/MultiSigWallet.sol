// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AddressSetLib} from "../util/AddressSetLib.sol";

/// @title MultiSigWallet
/// @notice M-of-N owner confirmation wallet used to custody the Keryx protocol
///         admin keys. Owners submit transactions, gather `threshold`
///         confirmations, and then any owner may execute the call. Owner-set and
///         threshold changes are themselves only possible through a confirmed
///         self-call, so the wallet governs its own configuration.
contract MultiSigWallet {
    using AddressSetLib for AddressSetLib.Set;

    /// @notice Enumerable set of current owners.
    AddressSetLib.Set internal _owners;

    /// @notice Number of confirmations required to execute a transaction.
    uint256 public threshold;

    /// @notice A queued wallet transaction.
    struct Tx {
        address to;
        uint256 value;
        bytes data;
        bool executed;
        uint256 confirmations;
    }

    /// @notice Total number of transactions ever submitted (also the next id).
    uint256 public txCount;

    /// @notice Transaction storage keyed by transaction id.
    mapping(uint256 => Tx) internal _txs;

    /// @notice Whether a given owner has confirmed a given transaction.
    mapping(uint256 => mapping(address => bool)) public confirmed;

    event Submit(uint256 indexed txId, address indexed to, uint256 value, bytes data);
    event Confirm(uint256 indexed txId, address indexed owner);
    event Revoke(uint256 indexed txId, address indexed owner);
    event Execute(uint256 indexed txId);
    event OwnerAdded(address owner);
    event OwnerRemoved(address owner);
    event ThresholdChanged(uint256 threshold);

    error NotOwner();
    error NotWallet();
    error AlreadyConfirmed();
    error NotConfirmed();
    error AlreadyExecuted();
    error NotEnoughConfirmations();
    error InvalidThreshold();
    error ExecutionFailed();

    /// @notice Restricts a call to current owners.
    modifier onlyOwner() {
        if (!_owners.contains(msg.sender)) revert NotOwner();
        _;
    }

    /// @notice Restricts a call to the wallet itself (i.e. via `execute`).
    modifier onlyWallet() {
        if (msg.sender != address(this)) revert NotWallet();
        _;
    }

    /// @notice Initializes the owner set and confirmation threshold.
    /// @param owners_ The initial, de-duplicated, non-zero owner addresses.
    /// @param threshold_ Required confirmations; must be in [1, owners.length].
    constructor(address[] memory owners_, uint256 threshold_) {
        uint256 len = owners_.length;
        for (uint256 i = 0; i < len; ++i) {
            address owner = owners_[i];
            // add() returns false on zero-position; the zero address would map to
            // position 0 and is therefore implicitly rejected as a duplicate, so
            // we reject it explicitly to avoid an unusable owner slot.
            if (owner == address(0)) revert NotOwner();
            if (_owners.add(owner)) {
                emit OwnerAdded(owner);
            }
        }
        if (threshold_ == 0 || threshold_ > _owners.length()) revert InvalidThreshold();
        threshold = threshold_;
        emit ThresholdChanged(threshold_);
    }

    /// @notice Accepts plain ETH transfers into the wallet.
    receive() external payable {}

    /// @notice Submits a new transaction and auto-confirms it for the submitter.
    /// @param to Target address of the call.
    /// @param value Wei to forward with the call.
    /// @param data Calldata for the call.
    /// @return txId The id assigned to the new transaction.
    function submit(address to, uint256 value, bytes calldata data)
        external
        onlyOwner
        returns (uint256 txId)
    {
        txId = txCount;
        _txs[txId] = Tx({to: to, value: value, data: data, executed: false, confirmations: 0});
        unchecked {
            txCount = txId + 1;
        }
        emit Submit(txId, to, value, data);

        // Submitting owner implicitly confirms.
        _confirm(txId);
    }

    /// @notice Confirms a pending transaction as the calling owner.
    /// @param txId The transaction id to confirm.
    function confirm(uint256 txId) external onlyOwner {
        _confirm(txId);
    }

    /// @notice Revokes a prior confirmation as the calling owner.
    /// @param txId The transaction id to revoke a confirmation on.
    function revoke(uint256 txId) external onlyOwner {
        Tx storage t = _txs[txId];
        if (t.executed) revert AlreadyExecuted();
        if (!confirmed[txId][msg.sender]) revert NotConfirmed();

        confirmed[txId][msg.sender] = false;
        unchecked {
            t.confirmations -= 1;
        }
        emit Revoke(txId, msg.sender);
    }

    /// @notice Executes a transaction once it has reached `threshold` confirmations.
    /// @param txId The transaction id to execute.
    /// @return result The raw return data of the executed call.
    function execute(uint256 txId) external onlyOwner returns (bytes memory result) {
        Tx storage t = _txs[txId];
        if (t.executed) revert AlreadyExecuted();
        if (t.confirmations < threshold) revert NotEnoughConfirmations();

        // Effects before interaction.
        t.executed = true;

        (bool ok, bytes memory ret) = t.to.call{value: t.value}(t.data);
        if (!ok) revert ExecutionFailed();

        emit Execute(txId);
        return ret;
    }

    /// @notice Adds a new owner; callable only by the wallet via a confirmed tx.
    /// @param owner The address to add as an owner.
    function addOwner(address owner) external onlyWallet {
        if (owner == address(0)) revert NotOwner();
        if (!_owners.add(owner)) revert NotOwner();
        emit OwnerAdded(owner);
    }

    /// @notice Removes an owner; callable only by the wallet via a confirmed tx.
    /// @dev Reverts if removal would drop the owner count below the threshold.
    /// @param owner The owner to remove.
    function removeOwner(address owner) external onlyWallet {
        if (!_owners.remove(owner)) revert NotOwner();
        if (_owners.length() < threshold) revert InvalidThreshold();
        emit OwnerRemoved(owner);
    }

    /// @notice Updates the confirmation threshold; callable only via the wallet.
    /// @param threshold_ The new threshold; must be in [1, owners.length].
    function setThreshold(uint256 threshold_) external onlyWallet {
        if (threshold_ == 0 || threshold_ > _owners.length()) revert InvalidThreshold();
        threshold = threshold_;
        emit ThresholdChanged(threshold_);
    }

    /// @notice Returns whether `account` is a current owner.
    /// @param account The address to query.
    /// @return True if `account` is an owner.
    function isOwner(address account) external view returns (bool) {
        return _owners.contains(account);
    }

    /// @notice Returns the full list of current owners.
    /// @return The owner addresses.
    function getOwners() external view returns (address[] memory) {
        return _owners.valuesOf();
    }

    /// @dev Records a confirmation for `txId` from `msg.sender` (an owner).
    function _confirm(uint256 txId) internal {
        Tx storage t = _txs[txId];
        if (t.executed) revert AlreadyExecuted();
        if (confirmed[txId][msg.sender]) revert AlreadyConfirmed();

        confirmed[txId][msg.sender] = true;
        unchecked {
            t.confirmations += 1;
        }
        emit Confirm(txId, msg.sender);
    }
}
