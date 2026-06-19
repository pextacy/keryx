// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title BondingCurve
/// @notice Pure linear bonding-curve math for KRX listing bonds. The instantaneous
///         spot price at a given supply `s` is `base + slope * s`. The cost to mint
///         (or refund to burn) a quantity of shares is the closed-form integral of the
///         linear price function over the affected supply range, evaluated exactly with
///         the trapezoid identity to avoid precision loss.
library BondingCurve {
    /// @notice Thrown when an intermediate or final computation would exceed uint256.
    error Overflow();

    /// @notice Spot (instantaneous) price of one share at the given supply.
    /// @dev Price = base + slope * supply. Reverts on overflow.
    /// @param supply Current bond share supply.
    /// @param slope Linear price slope per share.
    /// @param base Price floor at zero supply.
    /// @return Spot price at `supply`.
    function spotPrice(uint256 supply, uint256 slope, uint256 base) internal pure returns (uint256) {
        // term = slope * supply
        uint256 term;
        unchecked {
            term = slope * supply;
            if (supply != 0 && term / supply != slope) revert Overflow();
        }
        uint256 price;
        unchecked {
            price = base + term;
            if (price < base) revert Overflow();
        }
        return price;
    }

    /// @notice KRX cost to mint `amount` shares starting from `currentSupply`.
    /// @dev Cost is the integral of (base + slope * s) over s in [currentSupply, currentSupply + amount):
    ///      cost = amount * base + slope * (amount * currentSupply + amount * (amount - 1) / 2).
    ///      The triangular term uses the (amount * (amount - 1) / 2) discrete-step convention so that
    ///      minting then immediately burning the same shares is symmetric. Reverts on any overflow.
    /// @param currentSupply Bond shares already outstanding before the mint.
    /// @param amount Number of shares to mint.
    /// @param slope Linear price slope per share.
    /// @param base Price floor at zero supply.
    /// @return cost Total KRX cost for the mint.
    function costToMint(uint256 currentSupply, uint256 amount, uint256 slope, uint256 base)
        internal
        pure
        returns (uint256 cost)
    {
        return _areaUnderCurve(currentSupply, amount, slope, base);
    }

    /// @notice KRX refund for burning `amount` shares down from `currentSupply`.
    /// @dev Refund is the integral of (base + slope * s) over s in [currentSupply - amount, currentSupply),
    ///      i.e. the exact inverse of `costToMint` evaluated over the same share band so that a
    ///      mint-then-burn round-trip is conservative and value-preserving. Reverts if `amount`
    ///      exceeds `currentSupply` (underflow) or on any arithmetic overflow.
    /// @param currentSupply Bond shares outstanding before the burn.
    /// @param amount Number of shares to burn.
    /// @param slope Linear price slope per share.
    /// @param base Price floor at zero supply.
    /// @return refund Total KRX refunded for the burn.
    function refundToBurn(uint256 currentSupply, uint256 amount, uint256 slope, uint256 base)
        internal
        pure
        returns (uint256 refund)
    {
        if (amount > currentSupply) revert Overflow();
        // Area over the band [currentSupply - amount, currentSupply) equals the cost that
        // would have been charged to mint `amount` shares starting from (currentSupply - amount).
        uint256 startSupply;
        unchecked {
            startSupply = currentSupply - amount;
        }
        return _areaUnderCurve(startSupply, amount, slope, base);
    }

    /// @dev Closed-form area under the linear curve `base + slope * s` over the discrete band
    ///      s in [startSupply, startSupply + amount):
    ///      area = amount * base + slope * (amount * startSupply + amount * (amount - 1) / 2).
    ///      Every multiplication and addition is checked for overflow.
    function _areaUnderCurve(uint256 startSupply, uint256 amount, uint256 slope, uint256 base)
        private
        pure
        returns (uint256 area)
    {
        if (amount == 0) {
            return 0;
        }

        // baseComponent = amount * base
        uint256 baseComponent;
        unchecked {
            baseComponent = amount * base;
            if (base != 0 && baseComponent / base != amount) revert Overflow();
        }

        // linearOffset = amount * startSupply
        uint256 linearOffset;
        unchecked {
            linearOffset = amount * startSupply;
            if (startSupply != 0 && linearOffset / startSupply != amount) revert Overflow();
        }

        // triangle = amount * (amount - 1) / 2
        // Compute amount * (amount - 1) with overflow check, then halve (always exact: one factor is even).
        uint256 triangle;
        unchecked {
            uint256 amtMinusOne = amount - 1;
            uint256 product = amount * amtMinusOne;
            if (amtMinusOne != 0 && product / amtMinusOne != amount) revert Overflow();
            triangle = product / 2;
        }

        // sumSupply = linearOffset + triangle
        uint256 sumSupply;
        unchecked {
            sumSupply = linearOffset + triangle;
            if (sumSupply < linearOffset) revert Overflow();
        }

        // slopeComponent = slope * sumSupply
        uint256 slopeComponent;
        unchecked {
            slopeComponent = slope * sumSupply;
            if (sumSupply != 0 && slopeComponent / sumSupply != slope) revert Overflow();
        }

        // area = baseComponent + slopeComponent
        unchecked {
            area = baseComponent + slopeComponent;
            if (area < baseComponent) revert Overflow();
        }
    }
}
