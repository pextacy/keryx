// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title TokenVesting
/// @notice Cliff + linear vesting of KRX grants to contributors. Governors fund
///         and create schedules; beneficiaries pull their vested tokens over
///         time, and governors may revoke unvested tokens from revocable grants.
contract TokenVesting is ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice Role registry queried for governor authorization.
    AccessController public immutable acl;
    /// @notice The KRX token distributed by this vesting contract.
    IERC20 public immutable token;

    /// @notice A single contributor vesting grant.
    /// @dev `total` is the full grant size; `released` tracks tokens already
    ///      claimed. On revoke, `total` is trimmed to the amount vested at the
    ///      revocation timestamp so no further tokens accrue.
    struct Schedule {
        address beneficiary;
        uint256 total;
        uint256 released;
        uint64 start;
        uint64 cliff;
        uint64 duration;
        bool revocable;
        bool revoked;
    }

    /// @notice Number of schedules ever created; also the id of the next schedule.
    uint256 public totalSchedules;

    /// @dev Schedule storage keyed by sequential id.
    mapping(uint256 => Schedule) internal _schedules;

    /// @notice Emitted when a governor creates and funds a new vesting schedule.
    event ScheduleCreated(
        uint256 indexed id,
        address indexed beneficiary,
        uint256 total,
        uint64 start,
        uint64 cliff,
        uint64 duration
    );
    /// @notice Emitted when vested tokens are released to a beneficiary.
    event Released(uint256 indexed id, uint256 amount);
    /// @notice Emitted when a governor revokes a schedule, refunding unvested tokens.
    event Revoked(uint256 indexed id, uint256 refund);

    /// @notice Thrown when a governor-only function is called by a non-governor.
    error NotGovernor();
    /// @notice Thrown when release is called by someone other than the beneficiary.
    error NotBeneficiary();
    /// @notice Thrown when revoking a schedule that was not flagged revocable.
    error NotRevocable();
    /// @notice Thrown when revoking a schedule that was already revoked.
    error AlreadyRevoked();
    /// @notice Thrown when a release would transfer zero tokens.
    error NothingVested();
    /// @notice Thrown when schedule parameters are invalid.
    error BadParams();

    /// @dev Restricts a function to accounts holding the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the vesting contract to its access controller and token.
    /// @param acl_ The role registry used for governor authorization.
    /// @param token_ The KRX token to be vested.
    constructor(AccessController acl_, IERC20 token_) {
        if (address(acl_) == address(0) || address(token_) == address(0)) revert BadParams();
        acl = acl_;
        token = token_;
    }

    /// @notice Creates and funds a new vesting schedule, pulling `total` tokens
    ///         from the caller (a governor) into escrow.
    /// @dev Requires the governor to have approved this contract for `total`.
    ///      The cliff is expressed as an absolute timestamp and must lie within
    ///      [start, start + duration].
    /// @param beneficiary The recipient of the vesting grant.
    /// @param total The full grant size in token atomic units.
    /// @param start The unix timestamp at which vesting begins.
    /// @param cliff The unix timestamp before which nothing vests.
    /// @param duration The total vesting duration in seconds from `start`.
    /// @param revocable Whether a governor may later revoke unvested tokens.
    /// @return id The id of the newly created schedule.
    function createSchedule(
        address beneficiary,
        uint256 total,
        uint64 start,
        uint64 cliff,
        uint64 duration,
        bool revocable
    ) external onlyGovernor nonReentrant returns (uint256 id) {
        if (
            beneficiary == address(0) ||
            total == 0 ||
            duration == 0 ||
            cliff < start ||
            cliff > start + duration
        ) revert BadParams();

        id = totalSchedules;
        unchecked {
            totalSchedules = id + 1;
        }

        _schedules[id] = Schedule({
            beneficiary: beneficiary,
            total: total,
            released: 0,
            start: start,
            cliff: cliff,
            duration: duration,
            revocable: revocable,
            revoked: false
        });

        emit ScheduleCreated(id, beneficiary, total, start, cliff, duration);

        // Interaction last: pull the grant into escrow.
        token.safeTransferFrom(msg.sender, address(this), total);
    }

    /// @notice Returns the cumulative amount vested for a schedule as of now.
    /// @param id The schedule id.
    /// @return The total tokens vested (including any already released).
    function vestedAmount(uint256 id) external view returns (uint256) {
        return _vestedAmount(_schedules[id]);
    }

    /// @notice Releases all currently vested-but-unreleased tokens to the
    ///         schedule's beneficiary.
    /// @dev Callable only by the beneficiary. Follows checks-effects-interactions.
    /// @param id The schedule id.
    /// @return amount The amount of tokens transferred to the beneficiary.
    function release(uint256 id) external nonReentrant returns (uint256 amount) {
        Schedule storage s = _schedules[id];
        if (msg.sender != s.beneficiary) revert NotBeneficiary();

        uint256 vested = _vestedAmount(s);
        amount = vested - s.released;
        if (amount == 0) revert NothingVested();

        // Effects.
        s.released = vested;

        emit Released(id, amount);

        // Interaction.
        token.safeTransfer(s.beneficiary, amount);
    }

    /// @notice Revokes a revocable schedule, returning all not-yet-vested tokens
    ///         to the caller (a governor). Already-vested tokens remain claimable
    ///         by the beneficiary.
    /// @param id The schedule id.
    /// @return refund The amount of unvested tokens returned to the governor.
    function revoke(uint256 id) external onlyGovernor nonReentrant returns (uint256 refund) {
        Schedule storage s = _schedules[id];
        if (!s.revocable) revert NotRevocable();
        if (s.revoked) revert AlreadyRevoked();

        uint256 vested = _vestedAmount(s);
        refund = s.total - vested;

        // Effects: freeze vesting at the current vested amount.
        s.revoked = true;
        s.total = vested;

        emit Revoked(id, refund);

        // Interaction: return unvested tokens to the governor.
        if (refund != 0) {
            token.safeTransfer(msg.sender, refund);
        }
    }

    /// @notice Returns the full stored schedule struct for an id.
    /// @param id The schedule id.
    /// @return The schedule record.
    function getSchedule(uint256 id) external view returns (Schedule memory) {
        return _schedules[id];
    }

    /// @dev Computes the cumulative vested amount for a schedule at the current
    ///      block timestamp using a cliff + linear curve. Returns the (capped)
    ///      `total` once `start + duration` has elapsed, zero before the cliff.
    /// @param s The schedule to evaluate.
    /// @return The cumulative vested amount.
    function _vestedAmount(Schedule storage s) internal view returns (uint256) {
        uint256 ts = block.timestamp;

        if (ts < s.cliff) {
            return 0;
        }

        uint256 end = uint256(s.start) + uint256(s.duration);
        if (ts >= end) {
            return s.total;
        }

        uint256 elapsed = ts - uint256(s.start);
        return (s.total * elapsed) / uint256(s.duration);
    }
}
