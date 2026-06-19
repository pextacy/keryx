// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {KeryxGovToken} from "../governance/KeryxGovToken.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title EmissionSchedule
/// @notice Decaying-per-epoch KRX emission accounting that mints freshly issued
///         supply to the reward distributor. Each elapsed epoch emits an amount
///         that decays geometrically by `decayBps` relative to the prior epoch,
///         capping the protocol's long-run inflation. Governor-gated parameters.
contract EmissionSchedule {
    /// @notice Role registry consulted for governor authorization.
    AccessController public immutable acl;
    /// @notice The KRX governance token this schedule mints. This contract must
    ///         hold GOVERNOR_ROLE on `acl` so its mint calls succeed.
    KeryxGovToken public immutable krx;

    /// @notice Recipient of newly minted emissions (typically the reward distributor).
    address public emissionTarget;
    /// @notice Seconds per emission epoch.
    uint256 public epochLength;
    /// @notice KRX minted for the next epoch to be emitted.
    uint256 public emissionPerEpoch;
    /// @notice Per-epoch geometric decay applied to `emissionPerEpoch`, in bps.
    uint16 public decayBps;
    /// @notice Timestamp marking the start of the most recently emitted epoch.
    uint64 public lastEpochTime;
    /// @notice Count of epochs emitted so far.
    uint256 public currentEpoch;

    /// @notice Basis-points denominator (100%).
    uint16 public constant MAX_BPS = 10000;

    /// @notice Emitted when an epoch's emission is minted to the target.
    event Emitted(uint256 indexed epoch, uint256 amount, address target);
    /// @notice Emitted when emission parameters are updated by governance.
    event ParamsSet(uint256 epochLength, uint256 emissionPerEpoch, uint16 decayBps);
    /// @notice Emitted when the emission target is updated by governance.
    event TargetSet(address target);

    /// @notice Thrown when a non-governor calls a governor-only function.
    error NotGovernor();
    /// @notice Thrown when `emitEpoch` is called before a full epoch has elapsed.
    error EpochNotElapsed();

    /// @dev Restricts a call to holders of the suite GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the schedule and seeds its initial parameters.
    /// @param acl_ The access controller used for authorization.
    /// @param krx_ The KRX governance token to mint.
    /// @param emissionTarget_ The recipient of minted emissions.
    /// @param epochLength_ Seconds per epoch.
    /// @param emissionPerEpoch_ KRX minted in the first epoch.
    /// @param decayBps_ Per-epoch geometric decay in bps (<= MAX_BPS).
    constructor(
        AccessController acl_,
        KeryxGovToken krx_,
        address emissionTarget_,
        uint256 epochLength_,
        uint256 emissionPerEpoch_,
        uint16 decayBps_
    ) {
        acl = acl_;
        krx = krx_;
        emissionTarget = emissionTarget_;
        epochLength = epochLength_;
        emissionPerEpoch = emissionPerEpoch_;
        decayBps = decayBps_ > MAX_BPS ? MAX_BPS : decayBps_;
        // Anchor the first epoch to deployment time so the first emission becomes
        // claimable exactly one `epochLength` later.
        lastEpochTime = uint64(block.timestamp);

        emit TargetSet(emissionTarget_);
        emit ParamsSet(epochLength_, emissionPerEpoch_, decayBps);
    }

    /// @notice Updates the epoch length, base emission, and decay rate.
    /// @dev Decay is clamped to MAX_BPS to keep the geometric factor in [0, 1].
    /// @param epochLength_ New seconds per epoch.
    /// @param emissionPerEpoch_ New base emission for the next epoch.
    /// @param decayBps_ New per-epoch decay in bps.
    function setParams(
        uint256 epochLength_,
        uint256 emissionPerEpoch_,
        uint16 decayBps_
    ) external onlyGovernor {
        epochLength = epochLength_;
        emissionPerEpoch = emissionPerEpoch_;
        decayBps = decayBps_ > MAX_BPS ? MAX_BPS : decayBps_;

        emit ParamsSet(epochLength_, emissionPerEpoch_, decayBps);
    }

    /// @notice Updates the recipient of minted emissions.
    /// @param target The new emission target.
    function setTarget(address target) external onlyGovernor {
        emissionTarget = target;
        emit TargetSet(target);
    }

    /// @notice Mints the current epoch's emission to the target and advances the
    ///         schedule, applying geometric decay to the next epoch's amount.
    /// @dev Follows checks-effects-interactions: all schedule state is mutated
    ///      before the external mint call. Reverts if a full epoch has not yet
    ///      elapsed or while emission is configured to zero length.
    /// @return minted The amount of KRX minted for this epoch.
    function emitEpoch() external returns (uint256 minted) {
        uint256 length = epochLength;
        if (length == 0 || block.timestamp < uint256(lastEpochTime) + length) {
            revert EpochNotElapsed();
        }

        minted = emissionPerEpoch;
        uint256 epoch = currentEpoch + 1;
        address target = emissionTarget;

        // Effects: advance the epoch pointer, decay the next emission, and roll
        // the epoch start forward by exactly one epoch (no drift across catch-up).
        currentEpoch = epoch;
        lastEpochTime = uint64(uint256(lastEpochTime) + length);
        emissionPerEpoch = (minted * (MAX_BPS - decayBps)) / MAX_BPS;

        // Interactions: mint the emission to the target.
        if (minted > 0) {
            krx.mint(target, minted);
        }

        emit Emitted(epoch, minted, target);
    }

    /// @notice Returns the emission claimable right now without mutating state.
    /// @dev Mirrors `emitEpoch`'s elapsed-epoch gate: zero until a full epoch
    ///      has passed, then the current `emissionPerEpoch`.
    /// @return The KRX amount that `emitEpoch` would mint if called now.
    function pendingEmission() external view returns (uint256) {
        uint256 length = epochLength;
        if (length == 0 || block.timestamp < uint256(lastEpochTime) + length) {
            return 0;
        }
        return emissionPerEpoch;
    }
}
