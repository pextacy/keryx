// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title GroundingMath
/// @notice On-chain mirror of the off-chain grounding economics (shared/config.py):
///         a grounding score `g ∈ [0,1]` is carried as basis points (`gBps ∈ [0,10000]`),
///         the gate pays only when `gBps >= thresholdBps`, and the per-citation toll
///         scales linearly across the [min,max] band by g, never below the floor.
library GroundingMath {
    uint16 internal constant BPS = 10_000;

    error InvalidBps();
    error TollBandUnordered();

    /// @notice True when a source is grounded enough to be cited (paid).
    function isCited(uint16 gBps, uint16 thresholdBps) internal pure returns (bool) {
        if (gBps > BPS || thresholdBps > BPS) revert InvalidBps();
        return gBps >= thresholdBps;
    }

    /// @notice Per-citation toll for grounding score `gBps`, scaled within [min,max] by g,
    ///         clamped to at least `floor`. Pure integer math (USDC atomic units).
    function amountForG(uint256 floor, uint256 tollMin, uint256 tollMax, uint16 gBps)
        internal
        pure
        returns (uint256 amount)
    {
        if (gBps > BPS) revert InvalidBps();
        if (tollMax < tollMin) revert TollBandUnordered();
        amount = tollMin + ((tollMax - tollMin) * gBps) / BPS;
        if (amount < floor) amount = floor;
    }

    /// @notice Weight of one citation in a weighted split: gBps_i / sum(gBps).
    ///         Returned in basis points of the whole; the caller multiplies the pot by it.
    function weightBps(uint16 gBps, uint256 totalGBps) internal pure returns (uint256) {
        if (totalGBps == 0) return 0;
        return (uint256(gBps) * BPS) / totalGBps;
    }
}
