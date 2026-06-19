// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {PriceOracle} from "./PriceOracle.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title TWAPOracle
/// @notice Accumulates price*time observations from the spot PriceOracle to expose
///         a manipulation-resistant time-weighted average price (TWAP) over a window.
contract TWAPOracle {
    /// @notice Role registry consulted for authorization decisions.
    AccessController public immutable acl;

    /// @notice Spot price source whose value is sampled on each update.
    PriceOracle public immutable spot;

    /// @notice A single price accumulator snapshot taken at a given timestamp.
    struct Observation {
        uint64 timestamp;
        uint256 priceCumulative;
    }

    /// @dev Append-only history of cumulative-price snapshots.
    Observation[] internal _observations;

    /// @notice Running sum of price*elapsedSeconds since deployment.
    uint256 public cumulative;

    /// @notice Timestamp of the most recent observation.
    uint64 public lastTimestamp;

    /// @notice Spot price recorded at the most recent observation.
    uint256 public lastPrice;

    /// @notice Emitted whenever a new observation is recorded.
    event Observed(uint64 timestamp, uint256 price, uint256 cumulative);

    /// @notice Thrown when a consult is attempted before any observation exists.
    error NoObservations();

    /// @notice Thrown when the requested averaging period cannot be satisfied.
    error PeriodTooShort();

    /// @notice Wires the oracle to its access controller and spot price source,
    ///         seeding the first observation from the current spot price.
    /// @param acl_ The access controller used for authorization.
    /// @param spot_ The spot price oracle to sample.
    constructor(AccessController acl_, PriceOracle spot_) {
        acl = acl_;
        spot = spot_;

        uint256 price = spot_.getPrice();
        uint64 nowTs = uint64(block.timestamp);

        lastPrice = price;
        lastTimestamp = nowTs;
        // cumulative starts at zero; the first window accrues from this seed point.
        _observations.push(Observation({timestamp: nowTs, priceCumulative: 0}));

        emit Observed(nowTs, price, 0);
    }

    /// @notice Samples the spot price and accrues price*time into the cumulative
    ///         accumulator, appending a new observation.
    /// @dev Follows checks-effects-interactions: the external getPrice read happens
    ///      before any state mutation. Multiple calls within the same second simply
    ///      refresh the stored spot price without double-counting elapsed time.
    function update() external {
        uint256 price = spot.getPrice();
        uint64 nowTs = uint64(block.timestamp);

        uint64 prevTs = lastTimestamp;
        uint256 elapsed = nowTs > prevTs ? uint256(nowTs - prevTs) : 0;

        // Accrue the previous price over the elapsed interval (TWAP convention).
        cumulative += lastPrice * elapsed;

        lastPrice = price;
        lastTimestamp = nowTs;
        _observations.push(Observation({timestamp: nowTs, priceCumulative: cumulative}));

        emit Observed(nowTs, price, cumulative);
    }

    /// @notice Returns the time-weighted average price over the trailing `period`
    ///         seconds, derived from the recorded cumulative observations.
    /// @param period The averaging window in seconds; must be positive.
    /// @return twap The time-weighted average price over the window.
    function consult(uint256 period) external view returns (uint256 twap) {
        if (period == 0) revert PeriodTooShort();

        uint256 count = _observations.length;
        if (count == 0) revert NoObservations();

        uint64 nowTs = uint64(block.timestamp);

        // Current cumulative value extrapolated to the present moment.
        uint256 endCumulative = cumulative + lastPrice * (uint256(nowTs - lastTimestamp));

        uint64 target = nowTs >= period ? uint64(nowTs - period) : 0;

        // Earliest observation must predate the window start for a full average.
        Observation memory oldest = _observations[0];
        if (oldest.timestamp > target) revert PeriodTooShort();

        // Find the latest observation at or before the target window start.
        Observation memory startObs = oldest;
        for (uint256 i = count; i > 0; ) {
            Observation memory obs = _observations[i - 1];
            if (obs.timestamp <= target) {
                startObs = obs;
                break;
            }
            unchecked {
                --i;
            }
        }

        uint256 elapsed = uint256(nowTs - startObs.timestamp);
        if (elapsed == 0) revert PeriodTooShort();

        twap = (endCumulative - startObs.priceCumulative) / elapsed;
    }

    /// @notice Returns the number of recorded observations.
    /// @return The observation count.
    function observationCount() external view returns (uint256) {
        return _observations.length;
    }
}
