// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title PaymentEscrow
/// @notice Holds USDC for an answer until released by the payer or refunded via an arbiter on dispute.
contract PaymentEscrow is ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice Role registry consulted to authorize refund (arbiter) decisions.
    AccessController public immutable acl;

    /// @notice USDC token held in escrow.
    IERC20 public immutable usdc;

    /// @notice Lifecycle states of an escrowed deal.
    enum State {
        None,
        Funded,
        Released,
        Refunded
    }

    /// @notice An escrowed payment between a payer and a payee.
    struct Deal {
        address payer;
        address payee;
        uint256 amount;
        State state;
    }

    /// @notice Monotonically increasing count of deals ever created (also the next deal id).
    uint256 public totalDeals;

    /// @dev dealId => Deal record.
    mapping(uint256 => Deal) internal _deals;

    /// @notice Emitted when a payer funds a new escrow deal.
    event Funded(uint256 indexed dealId, address indexed payer, address indexed payee, uint256 amount);
    /// @notice Emitted when escrowed funds are released to the payee.
    event Released(uint256 indexed dealId);
    /// @notice Emitted when escrowed funds are refunded to the payer.
    event Refunded(uint256 indexed dealId);

    /// @notice Caller is not the deal's payer.
    error NotPayer();
    /// @notice Caller does not hold the arbiter (guardian) role required to refund.
    error NotArbiter();
    /// @notice Deal is not in the state required for the attempted action.
    error WrongState();
    /// @notice A zero-value escrow was attempted.
    error ZeroAmount();

    /// @notice Wires the escrow to the access controller and the USDC token.
    /// @param acl_ The deployed AccessController used for arbiter authorization.
    /// @param usdc_ The USDC token escrowed by this contract.
    constructor(AccessController acl_, IERC20 usdc_) {
        acl = acl_;
        usdc = usdc_;
    }

    /// @notice Pulls `amount` USDC from the caller into a new escrow deal earmarked for `payee`.
    /// @param payee The recipient who will receive the funds on release.
    /// @param amount The amount of USDC to escrow (must be non-zero).
    /// @return dealId The id of the newly created deal.
    function fund(address payee, uint256 amount) external nonReentrant returns (uint256 dealId) {
        if (amount == 0) revert ZeroAmount();

        // Effects: record the deal before moving funds in for clean accounting.
        dealId = totalDeals;
        unchecked {
            totalDeals = dealId + 1;
        }

        _deals[dealId] = Deal({payer: msg.sender, payee: payee, amount: amount, state: State.Funded});

        emit Funded(dealId, msg.sender, payee, amount);

        // Interaction: pull funds from the payer into escrow.
        usdc.safeTransferFrom(msg.sender, address(this), amount);
    }

    /// @notice Releases an escrowed deal's funds to its payee. Callable only by the payer.
    /// @param dealId The deal to release.
    function release(uint256 dealId) external nonReentrant {
        Deal storage deal = _deals[dealId];
        if (deal.state != State.Funded) revert WrongState();
        if (msg.sender != deal.payer) revert NotPayer();

        // Effects.
        deal.state = State.Released;
        address payee = deal.payee;
        uint256 amount = deal.amount;

        emit Released(dealId);

        // Interaction.
        usdc.safeTransfer(payee, amount);
    }

    /// @notice Refunds an escrowed deal's funds to its payer. Callable only by a guardian (arbiter).
    /// @param dealId The deal to refund.
    function refund(uint256 dealId) external nonReentrant {
        if (!acl.hasRole(acl.GUARDIAN_ROLE(), msg.sender)) revert NotArbiter();

        Deal storage deal = _deals[dealId];
        if (deal.state != State.Funded) revert WrongState();

        // Effects.
        deal.state = State.Refunded;
        address payer = deal.payer;
        uint256 amount = deal.amount;

        emit Refunded(dealId);

        // Interaction.
        usdc.safeTransfer(payer, amount);
    }

    /// @notice Returns the full record for a given deal.
    /// @param dealId The deal to query.
    /// @return The stored Deal struct.
    function getDeal(uint256 dealId) external view returns (Deal memory) {
        return _deals[dealId];
    }
}
