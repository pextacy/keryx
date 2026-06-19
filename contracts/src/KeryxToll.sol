// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Owned} from "./auth/Owned.sol";
import {GroundingMath} from "./libraries/GroundingMath.sol";

/// @title KeryxToll
/// @notice On-chain settlement economics — the canonical, owner-tunable mirror of
///         shared/config.py (floor $0.000001, toll band $0.001–$0.01, threshold T=0.5),
///         expressed in USDC atomic units (6 decimals) and basis points. Nothing is
///         hardcoded in business-logic contracts; they read it from here.
contract KeryxToll is Owned {
    using GroundingMath for uint16;

    uint256 public floorAtomic; // e.g. 1      = $0.000001
    uint256 public tollMin; //     e.g. 1_000  = $0.001
    uint256 public tollMax; //     e.g. 10_000 = $0.01
    uint16 public thresholdBps; // e.g. 5_000  = g >= 0.5

    event TollUpdated(uint256 floorAtomic, uint256 tollMin, uint256 tollMax, uint16 thresholdBps);

    error TollBandUnordered();
    error ThresholdTooHigh();

    constructor(address owner_, uint256 floor_, uint256 min_, uint256 max_, uint16 thresholdBps_) Owned(owner_) {
        _set(floor_, min_, max_, thresholdBps_);
    }

    function setToll(uint256 floor_, uint256 min_, uint256 max_, uint16 thresholdBps_) external onlyOwner {
        _set(floor_, min_, max_, thresholdBps_);
    }

    function _set(uint256 floor_, uint256 min_, uint256 max_, uint16 thresholdBps_) internal {
        if (max_ < min_) revert TollBandUnordered();
        if (thresholdBps_ > GroundingMath.BPS) revert ThresholdTooHigh();
        floorAtomic = floor_;
        tollMin = min_;
        tollMax = max_;
        thresholdBps = thresholdBps_;
        emit TollUpdated(floor_, min_, max_, thresholdBps_);
    }

    /// @notice Per-citation toll for grounding score `gBps`, scaled within the band.
    function amountFor(uint16 gBps) external view returns (uint256) {
        return GroundingMath.amountForG(floorAtomic, tollMin, tollMax, gBps);
    }

    /// @notice Whether `gBps` clears the gate (g >= T).
    function isCited(uint16 gBps) external view returns (bool) {
        return GroundingMath.isCited(gBps, thresholdBps);
    }
}
