// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {KeryxSettlement} from "../KeryxSettlement.sol";
import {FeeManager} from "../treasury/FeeManager.sol";
import {CircuitBreaker} from "../access/CircuitBreaker.sol";
import {AttestationLib} from "../libraries/AttestationLib.sol";
import {CitationLib} from "../libraries/CitationLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";
import {AccessController} from "../access/AccessController.sol";
import {IERC20} from "../interfaces/IERC20.sol";

/// @title SettlementRouter
/// @notice Batches many citation settlements into a single transaction. For each answer
///         in the batch it routes through the canonical KeryxSettlement orchestrator,
///         registers the resulting USDC outflow against the per-asset CircuitBreaker, and
///         skims the protocol fee via the FeeManager. The whole batch reverts if the
///         breaker trips, so a runaway settlement volume can never drain the system.
/// @dev Only accounts holding the SETTLER_ROLE may invoke the batch. The router never
///      custodies funds: KeryxSettlement pulls USDC directly from msg.sender to each
///      cited author, and the FeeManager pulls the fee from msg.sender to the treasury.
contract SettlementRouter is ReentrancyGuard {
    /// @notice Role registry consulted for settler authorization decisions.
    AccessController public immutable acl;

    /// @notice Canonical settlement orchestrator each answer is routed through.
    KeryxSettlement public immutable settlement;

    /// @notice Fee skimmer that forwards the protocol cut to the treasury.
    FeeManager public immutable feeManager;

    /// @notice Per-asset outflow circuit breaker guarding total settled volume.
    CircuitBreaker public immutable breaker;

    /// @notice USDC token settled and metered by this router.
    address public immutable usdc;

    event BatchSettled(uint256 count, uint256 totalPaid, uint256 totalFee);

    error EmptyBatch();
    error LengthMismatch();
    error NotSettler();

    /// @notice Restricts a call to accounts holding the settler role.
    modifier onlySettler() {
        if (!acl.hasRole(acl.SETTLER_ROLE(), msg.sender)) revert NotSettler();
        _;
    }

    /// @notice Wires the router to its access controller and settlement dependencies.
    /// @param acl_ The deployed AccessController instance.
    /// @param settlement_ The KeryxSettlement orchestrator answers are routed through.
    /// @param feeManager_ The FeeManager that skims the protocol fee.
    /// @param breaker_ The CircuitBreaker that meters per-asset outflow.
    /// @param usdc_ The USDC token address settled by this router.
    constructor(
        AccessController acl_,
        KeryxSettlement settlement_,
        FeeManager feeManager_,
        CircuitBreaker breaker_,
        address usdc_
    ) {
        acl = acl_;
        settlement = settlement_;
        feeManager = feeManager_;
        breaker = breaker_;
        usdc = usdc_;
    }

    /// @notice Settle a batch of signed answers in one transaction.
    /// @dev For each answer i, routes (atts[i], cites[i], sigs[i]) through KeryxSettlement,
    ///      accumulates the paid amount, registers it against the breaker (which reverts the
    ///      whole batch if the cap is exceeded), and skims the protocol fee. Checks are
    ///      performed up front; external interactions follow per the checks-effects-interactions
    ///      pattern, all guarded by nonReentrant.
    /// @param atts The signed attestations, one per answer.
    /// @param cites The citation sets, one inner array per answer (parallel to atts).
    /// @param sigs The attestation signatures (parallel to atts).
    /// @return totalPaid The aggregate USDC paid to cited authors across the batch.
    function settleBatch(
        AttestationLib.Attestation[] calldata atts,
        CitationLib.Citation[][] calldata cites,
        bytes[] calldata sigs
    ) external nonReentrant onlySettler returns (uint256 totalPaid) {
        uint256 count = atts.length;
        if (count == 0) revert EmptyBatch();
        if (cites.length != count || sigs.length != count) revert LengthMismatch();

        uint256 totalFee;
        for (uint256 i = 0; i < count; i++) {
            (, uint256 paid) = settlement.settle(atts[i], cites[i], sigs[i]);
            totalPaid += paid;

            // Meter outflow first: reverts the whole batch if the breaker is tripped.
            breaker.registerOutflow(usdc, paid);

            // Skim the protocol fee on the gross amount paid for this answer.
            (uint256 fee, ) = feeManager.collectFee(_usdcToken(), msg.sender, paid);
            totalFee += fee;
        }

        emit BatchSettled(count, totalPaid, totalFee);
    }

    /// @dev Narrows the stored USDC address to the IERC20 type FeeManager.collectFee expects.
    function _usdcToken() private view returns (IERC20) {
        return IERC20(usdc);
    }
}
