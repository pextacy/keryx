// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {ITreasury} from "../interfaces/ITreasury.sol";
import {IERC20} from "../interfaces/IERC20.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";
import {AccessController} from "../access/AccessController.sol";
import {CircuitBreaker} from "../access/CircuitBreaker.sol";

/// @title Treasury
/// @notice Holds protocol-owned assets; governor-gated withdrawals run through the circuit breaker before any outflow.
contract Treasury is ITreasury, ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice Role registry the treasury queries for governor authorization.
    AccessController public immutable acl;

    /// @notice Circuit breaker consulted (and updated) on every withdrawal.
    CircuitBreaker public breaker;

    /// @notice Internally accounted balance per token (only counts assets received via deposit/withdraw).
    mapping(address => uint256) internal _accounted;

    event Deposited(address indexed token, address indexed from, uint256 amount);
    event Withdrawn(address indexed token, address indexed to, uint256 amount);
    event BreakerSet(address breaker);

    error NotGovernor();
    error InsufficientBalance();

    /// @notice Restricts a call to accounts holding the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the access controller and the initial circuit breaker.
    /// @param acl_ The deployed role registry.
    /// @param breaker_ The circuit breaker tracking per-asset outflow.
    constructor(AccessController acl_, CircuitBreaker breaker_) {
        acl = acl_;
        breaker = breaker_;
        emit BreakerSet(address(breaker_));
    }

    /// @notice Governor swaps the circuit breaker implementation.
    /// @param breaker_ The new circuit breaker.
    function setBreaker(CircuitBreaker breaker_) external onlyGovernor {
        breaker = breaker_;
        emit BreakerSet(address(breaker_));
    }

    /// @notice Pulls `amount` of `token` from the caller into the treasury and credits the internal ledger.
    /// @param token The ERC20 asset being deposited.
    /// @param amount The amount to deposit.
    function deposit(address token, uint256 amount) external nonReentrant {
        // Effects: account for the incoming balance before the external transfer-in.
        _accounted[token] += amount;
        emit Deposited(token, msg.sender, amount);
        // Interactions.
        IERC20(token).safeTransferFrom(msg.sender, address(this), amount);
    }

    /// @notice Governor withdraws `amount` of `token` to `to`, registering the outflow with the breaker first.
    /// @param token The ERC20 asset being withdrawn.
    /// @param to The recipient of the funds.
    /// @param amount The amount to withdraw.
    function withdraw(address token, address to, uint256 amount) external onlyGovernor nonReentrant {
        // Checks.
        uint256 accounted = _accounted[token];
        if (amount > accounted) revert InsufficientBalance();

        // Effects: debit the ledger before any external interaction.
        unchecked {
            _accounted[token] = accounted - amount;
        }
        emit Withdrawn(token, to, amount);

        // Interactions: trip/track the breaker, then move the funds. A tripped
        // breaker reverts inside registerOutflow, reverting the whole withdrawal.
        breaker.registerOutflow(token, amount);
        IERC20(token).safeTransfer(to, amount);
    }

    /// @notice Returns the internally accounted balance of `token`.
    /// @param token The ERC20 asset to query.
    function balanceOf(address token) external view returns (uint256) {
        return _accounted[token];
    }
}
