// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title InsuranceFund
/// @notice Backstop reserve that covers settlement shortfalls and absorbs
///         slashed stake. Anyone may top up the reserve, authorized callers
///         (e.g. the settlement router or slashing controller) draw coverage
///         payments against it, and the governor caps cumulative coverage and
///         manages the authorized caller set.
contract InsuranceFund is ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice Role registry the fund queries for governance authorization.
    AccessController public immutable acl;
    /// @notice ERC-20 reserve asset held and paid out by the fund.
    IERC20 public immutable asset;

    /// @notice Maximum cumulative amount the fund is permitted to pay out as coverage.
    uint256 public coverageCap;
    /// @notice Running total of coverage already paid out over the fund's lifetime.
    uint256 public totalCovered;

    /// @notice Authorized callers permitted to draw coverage from the fund.
    mapping(address => bool) public authorized;

    /// @notice Emitted when the reserve is topped up.
    event Deposited(address indexed from, uint256 amount);
    /// @notice Emitted when coverage is paid out to a recipient.
    event CoveragePaid(address indexed to, uint256 amount, bytes32 indexed reason);
    /// @notice Emitted when the governor updates the cumulative coverage cap.
    event CoverageCapSet(uint256 cap);
    /// @notice Emitted when the governor changes an authorized caller's status.
    event AuthorizedSet(address indexed caller, bool allowed);

    /// @notice Thrown when a governor-only function is called by a non-governor.
    error NotGovernor();
    /// @notice Thrown when a coverage draw is attempted by an unauthorized caller.
    error NotAuthorized();
    /// @notice Thrown when a coverage draw would exceed the cumulative coverage cap.
    error CapExceeded();
    /// @notice Thrown when the fund's balance is insufficient to honor a draw.
    error InsufficientFund();

    /// @dev Restricts a function to accounts holding the governor role.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Deploys the fund wired to a role registry, reserve asset and cap.
    /// @param acl_ The access controller used for governance authorization.
    /// @param asset_ The ERC-20 token held as the backstop reserve.
    /// @param coverageCap_ The initial cumulative coverage cap.
    constructor(AccessController acl_, IERC20 asset_, uint256 coverageCap_) {
        acl = acl_;
        asset = asset_;
        coverageCap = coverageCap_;
        emit CoverageCapSet(coverageCap_);
    }

    /// @notice Grants or revokes a caller's permission to draw coverage.
    /// @param caller The account whose authorization is being updated.
    /// @param allowed Whether the caller may draw coverage.
    function setAuthorized(address caller, bool allowed) external onlyGovernor {
        authorized[caller] = allowed;
        emit AuthorizedSet(caller, allowed);
    }

    /// @notice Updates the cumulative coverage cap.
    /// @param cap The new lifetime coverage cap.
    function setCoverageCap(uint256 cap) external onlyGovernor {
        coverageCap = cap;
        emit CoverageCapSet(cap);
    }

    /// @notice Tops up the reserve by pulling `amount` of the asset from the caller.
    /// @dev The caller must have approved this contract for at least `amount`.
    /// @param amount The amount of the reserve asset to deposit.
    function deposit(uint256 amount) external nonReentrant {
        asset.safeTransferFrom(msg.sender, address(this), amount);
        emit Deposited(msg.sender, amount);
    }

    /// @notice Draws coverage from the reserve to `to`, capped by the remaining
    ///         allowance under the coverage cap.
    /// @dev Authorized callers only. The amount paid is the lesser of `amount`
    ///      and the remaining headroom under the cap; reverts if either there is
    ///      no headroom left or the fund cannot cover the requested payment.
    /// @param to The recipient of the coverage payment.
    /// @param amount The requested coverage amount.
    /// @param reason An opaque identifier describing the coverage cause.
    /// @return paid The actual amount transferred to the recipient.
    function cover(address to, uint256 amount, bytes32 reason)
        external
        nonReentrant
        returns (uint256 paid)
    {
        if (!authorized[msg.sender]) revert NotAuthorized();

        // Determine remaining headroom under the cumulative cap.
        if (totalCovered >= coverageCap) revert CapExceeded();
        uint256 headroom = coverageCap - totalCovered;

        // Clamp the payout to the cap headroom.
        paid = amount > headroom ? headroom : amount;

        // Ensure the reserve can honor the (clamped) payment.
        if (paid > asset.balanceOf(address(this))) revert InsufficientFund();

        // Effects before interaction.
        totalCovered += paid;

        // Interaction.
        asset.safeTransfer(to, paid);

        emit CoveragePaid(to, paid, reason);
    }

    /// @notice Returns the coverage currently drawable: the smaller of the
    ///         on-hand reserve balance and the remaining cap headroom.
    /// @return The amount of coverage that could be paid out right now.
    function available() external view returns (uint256) {
        uint256 balance = asset.balanceOf(address(this));
        uint256 headroom = totalCovered >= coverageCap ? 0 : coverageCap - totalCovered;
        return balance < headroom ? balance : headroom;
    }
}
