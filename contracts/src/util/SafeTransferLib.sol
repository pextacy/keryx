// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";

/// @title SafeTransferLib
/// @notice Wraps IERC20 transfer/transferFrom/approve so calls revert on a
///         `false` return value or on missing/short return data, while still
///         tolerating non-standard tokens that return nothing on success.
library SafeTransferLib {
    /// @notice Thrown when a token `transfer` fails or returns falsey data.
    error TransferFailed();
    /// @notice Thrown when a token `transferFrom` fails or returns falsey data.
    error TransferFromFailed();
    /// @notice Thrown when a token `approve` fails or returns falsey data.
    error ApproveFailed();

    /// @notice Calls `token.transfer(to, amount)` and reverts unless it succeeds.
    /// @param token The ERC-20 token to move.
    /// @param to The recipient of the transfer.
    /// @param amount The amount of tokens to transfer.
    function safeTransfer(IERC20 token, address to, uint256 amount) internal {
        bytes memory data = abi.encodeWithSelector(IERC20.transfer.selector, to, amount);
        if (!_call(address(token), data)) revert TransferFailed();
    }

    /// @notice Calls `token.transferFrom(from, to, amount)` and reverts unless it succeeds.
    /// @param token The ERC-20 token to move.
    /// @param from The address tokens are pulled from.
    /// @param to The recipient of the transfer.
    /// @param amount The amount of tokens to transfer.
    function safeTransferFrom(IERC20 token, address from, address to, uint256 amount) internal {
        bytes memory data = abi.encodeWithSelector(IERC20.transferFrom.selector, from, to, amount);
        if (!_call(address(token), data)) revert TransferFromFailed();
    }

    /// @notice Calls `token.approve(spender, amount)` and reverts unless it succeeds.
    /// @param token The ERC-20 token to approve.
    /// @param spender The address being granted the allowance.
    /// @param amount The allowance amount to set.
    function safeApprove(IERC20 token, address spender, uint256 amount) internal {
        bytes memory data = abi.encodeWithSelector(IERC20.approve.selector, spender, amount);
        if (!_call(address(token), data)) revert ApproveFailed();
    }

    /// @dev Performs a low-level call to a token and validates the result.
    ///      Returns true only when: the target has deployed code, the call did
    ///      not revert, and the return data is either empty (non-standard token)
    ///      or a single ABI-encoded `true` word.
    /// @param token The token contract address.
    /// @param data The ABI-encoded call payload.
    /// @return success Whether the call should be treated as a successful transfer.
    function _call(address token, bytes memory data) private returns (bool success) {
        if (token.code.length == 0) return false;

        (bool ok, bytes memory ret) = token.call(data);
        if (!ok) return false;

        // Success if no return data (non-compliant tokens) or an explicit `true`.
        return ret.length == 0 || (ret.length == 32 && abi.decode(ret, (bool)));
    }
}
