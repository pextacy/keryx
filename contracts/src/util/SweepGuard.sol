// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {SafeTransferLib} from "./SafeTransferLib.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title SweepGuard
/// @notice Governor-only recovery of stray tokens accidentally sent to protocol
///         contracts, while forbidding the sweep of protocol-protected tokens.
contract SweepGuard {
    using SafeTransferLib for IERC20;

    /// @notice Role registry consulted for governor authorization.
    AccessController public immutable acl;

    /// @notice Tokens flagged as protected and therefore not sweepable.
    mapping(address => bool) public protectedToken;

    /// @notice Emitted when stray tokens are recovered to a destination.
    event Swept(address indexed token, address indexed to, uint256 amount);

    /// @notice Emitted when a token's protected status is changed.
    event ProtectedSet(address indexed token, bool protectedStatus);

    /// @notice Thrown when the caller lacks the GOVERNOR_ROLE.
    error NotGovernor();

    /// @notice Thrown when attempting to sweep a protected token.
    error TokenProtected();

    /// @param acl_ The deployed AccessController used for authorization.
    constructor(AccessController acl_) {
        acl = acl_;
    }

    /// @dev Restricts callers to holders of the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Flags or unflags a token as protected from sweeping.
    /// @param token The token address whose protected status to set.
    /// @param status True to protect the token, false to allow sweeping.
    function setProtected(address token, bool status) external onlyGovernor {
        protectedToken[token] = status;
        emit ProtectedSet(token, status);
    }

    /// @notice Recovers stray (non-protected) tokens to a destination address.
    /// @param token The ERC20 token to recover.
    /// @param to The recipient of the recovered tokens.
    /// @param amount The amount of tokens to transfer out.
    function sweep(IERC20 token, address to, uint256 amount) external onlyGovernor {
        if (protectedToken[address(token)]) revert TokenProtected();

        // Effects/interactions: emit then transfer (no internal state to mutate).
        emit Swept(address(token), to, amount);
        token.safeTransfer(to, amount);
    }
}
