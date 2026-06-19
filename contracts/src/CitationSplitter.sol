// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Owned} from "./auth/Owned.sol";
import {IERC20} from "./interfaces/IERC20.sol";
import {GroundingMath} from "./libraries/GroundingMath.sol";

/// @title CitationSplitter
/// @notice Moves USDC from the paying agent to cited authors. Two modes:
///         - `distribute`: pay each author an explicit per-citation amount (the toll).
///         - `splitWeighted`: split a fixed pot across authors by grounding weight
///           (the recursive/weighted-split innovation — a source that grounded more
///           earns more). Pulls via `transferFrom`, so the payer approves this contract.
///         Authorized-only so a third party can't drain someone's standing allowance.
contract CitationSplitter is Owned {
    mapping(address => bool) public authorized;

    event AuthorizedSet(address indexed caller, bool allowed);
    event Distributed(address indexed token, address indexed from, uint256 total, uint256 count);

    error NotAuthorized();
    error LengthMismatch();
    error NothingToPay();
    error TransferFailed();
    error ZeroAuthor();

    modifier onlyAuthorized() {
        if (!authorized[msg.sender]) revert NotAuthorized();
        _;
    }

    constructor(address owner_) Owned(owner_) {}

    function setAuthorized(address caller, bool allowed) external onlyOwner {
        authorized[caller] = allowed;
        emit AuthorizedSet(caller, allowed);
    }

    /// @notice Pay each author `amounts[i]` of `token`, pulled from `from`.
    function distribute(IERC20 token, address from, address[] calldata authors, uint256[] calldata amounts)
        external
        onlyAuthorized
        returns (uint256 total)
    {
        if (authors.length != amounts.length) revert LengthMismatch();
        if (authors.length == 0) revert NothingToPay();
        for (uint256 i = 0; i < authors.length; i++) {
            if (authors[i] == address(0)) revert ZeroAuthor();
            _pull(token, from, authors[i], amounts[i]);
            total += amounts[i];
        }
        emit Distributed(address(token), from, total, authors.length);
    }

    /// @notice Split `pot` across `authors` by grounding weight `gBps`; last author
    ///         absorbs the rounding remainder so the full pot is distributed.
    function splitWeighted(IERC20 token, address from, uint256 pot, address[] calldata authors, uint16[] calldata gBps)
        external
        onlyAuthorized
        returns (uint256 distributed)
    {
        if (authors.length != gBps.length) revert LengthMismatch();
        if (authors.length == 0 || pot == 0) revert NothingToPay();
        uint256 totalG;
        for (uint256 i = 0; i < gBps.length; i++) {
            totalG += gBps[i];
        }
        if (totalG == 0) revert NothingToPay();
        for (uint256 i = 0; i < authors.length; i++) {
            if (authors[i] == address(0)) revert ZeroAuthor();
            uint256 amount = i == authors.length - 1 ? pot - distributed : (pot * gBps[i]) / totalG;
            _pull(token, from, authors[i], amount);
            distributed += amount;
        }
        emit Distributed(address(token), from, distributed, authors.length);
    }

    function _pull(IERC20 token, address from, address to, uint256 amount) internal {
        if (amount == 0) return;
        if (!token.transferFrom(from, to, amount)) revert TransferFailed();
    }
}
