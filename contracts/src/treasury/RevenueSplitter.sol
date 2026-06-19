// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title RevenueSplitter
/// @notice Splits accumulated protocol revenue held by this contract across a
///         fixed set of bps-weighted payees (e.g. treasury / insurance /
///         buyback). Governor configures the payees; anyone may trigger a
///         distribution of an arbitrary token's full balance pro-rata to shares.
contract RevenueSplitter is ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice Role registry consulted for governor-gated configuration.
    AccessController public immutable acl;

    /// @notice A single revenue recipient and its share of distributions in bps.
    struct Payee {
        address account;
        uint16 bps;
    }

    /// @dev The configured payee set; shares must always sum to MAX_BPS.
    Payee[] internal _payees;

    /// @notice Full-share denominator; configured shares must sum to this value.
    uint16 public constant MAX_BPS = 10000;

    /// @notice Emitted when the payee set is (re)configured.
    /// @param accounts The recipient addresses, in order.
    /// @param shares The bps share for each corresponding account.
    event PayeesSet(address[] accounts, uint16[] shares);

    /// @notice Emitted when a token balance is distributed across the payees.
    /// @param token The token that was distributed.
    /// @param total The total amount paid out across all payees.
    event Distributed(address indexed token, uint256 total);

    /// @notice Thrown when a non-governor calls a governor-only function.
    error NotGovernor();
    /// @notice Thrown when configured shares do not sum to exactly MAX_BPS,
    ///         or when the accounts/shares array lengths differ or are empty.
    error BpsSumMismatch();
    /// @notice Thrown when a distribution is attempted with a zero balance.
    error NothingToDistribute();

    /// @notice Restricts a function to accounts holding the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the splitter to the protocol access controller.
    /// @param acl_ The deployed AccessController used for authorization.
    constructor(AccessController acl_) {
        acl = acl_;
    }

    /// @notice Replaces the payee set with a new bps-weighted configuration.
    /// @dev Governor-only. Shares must sum to exactly MAX_BPS and the two arrays
    ///      must be non-empty and equal length. The previous configuration is
    ///      cleared entirely before the new one is written.
    /// @param accounts The recipient addresses in payout order.
    /// @param shares The bps share for each corresponding account.
    function setPayees(address[] calldata accounts, uint16[] calldata shares)
        external
        onlyGovernor
    {
        uint256 len = accounts.length;
        if (len == 0 || len != shares.length) revert BpsSumMismatch();

        uint256 sum;
        for (uint256 i; i < len; ++i) {
            sum += shares[i];
        }
        if (sum != MAX_BPS) revert BpsSumMismatch();

        // Effects: clear the existing set and write the new payees.
        delete _payees;
        for (uint256 i; i < len; ++i) {
            _payees.push(Payee({account: accounts[i], bps: shares[i]}));
        }

        emit PayeesSet(accounts, shares);
    }

    /// @notice Distributes this contract's full balance of `token` to the payees.
    /// @dev Permissionless. Pays each payee its bps share; any rounding dust is
    ///      assigned to the final payee so the entire balance is always swept.
    ///      Follows checks-effects-interactions: the total is computed up front
    ///      and the call is reentrancy-guarded.
    /// @param token The ERC-20 token to distribute.
    /// @return total The total amount distributed (the full pre-call balance).
    function distribute(IERC20 token) external nonReentrant returns (uint256 total) {
        uint256 n = _payees.length;
        if (n == 0) revert BpsSumMismatch();

        total = token.balanceOf(address(this));
        if (total == 0) revert NothingToDistribute();

        uint256 paid;
        // Interactions: pay each payee its share; the last absorbs rounding dust.
        for (uint256 i; i < n; ++i) {
            Payee storage p = _payees[i];
            uint256 amount;
            if (i + 1 == n) {
                amount = total - paid;
            } else {
                amount = (total * p.bps) / MAX_BPS;
                paid += amount;
            }
            if (amount != 0) {
                token.safeTransfer(p.account, amount);
            }
        }

        emit Distributed(address(token), total);
    }

    /// @notice Returns the current payee configuration.
    /// @return The array of configured payees with their bps shares.
    function payees() external view returns (Payee[] memory) {
        return _payees;
    }
}
