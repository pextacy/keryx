// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title Airdrop
/// @notice Governor-pushed batched direct token transfers for curated author rewards.
contract Airdrop is ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice Role registry queried for governor authorization.
    AccessController public immutable acl;

    /// @notice Token distributed to recipients.
    IERC20 public immutable token;

    /// @notice Emitted after a batch of transfers completes.
    event AirdropExecuted(uint256 count, uint256 total);

    /// @notice Caller does not hold the governor role.
    error NotGovernor();

    /// @notice Recipients and amounts arrays differ in length.
    error LengthMismatch();

    /// @notice The provided batch contains no recipients.
    error EmptyBatch();

    /// @notice Wires the access controller and distribution token.
    /// @param acl_ Role registry consulted for governor authorization.
    /// @param token_ ERC20 token to distribute.
    constructor(AccessController acl_, IERC20 token_) {
        acl = acl_;
        token = token_;
    }

    /// @notice Pushes a batch of direct token transfers to curated recipients.
    /// @dev Governor-only. Pulls the aggregate total from the caller, then fans
    ///      out individual transfers (checks-effects-interactions, reentrancy-guarded).
    /// @param recipients Addresses receiving rewards.
    /// @param amounts Per-recipient amounts, aligned with `recipients`.
    /// @return total Sum of all distributed amounts.
    function drop(address[] calldata recipients, uint256[] calldata amounts)
        external
        nonReentrant
        returns (uint256 total)
    {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();

        uint256 count = recipients.length;
        if (count != amounts.length) revert LengthMismatch();
        if (count == 0) revert EmptyBatch();

        for (uint256 i = 0; i < count; ++i) {
            total += amounts[i];
        }

        token.safeTransferFrom(msg.sender, address(this), total);

        for (uint256 i = 0; i < count; ++i) {
            token.safeTransfer(recipients[i], amounts[i]);
        }

        emit AirdropExecuted(count, total);
    }
}
