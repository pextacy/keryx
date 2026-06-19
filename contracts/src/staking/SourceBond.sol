// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {BondingCurve} from "./BondingCurve.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title SourceBond
/// @notice Bond KRX along a linear bonding curve to list a source; the bond is
///         refundable along the same curve when the source is delisted.
contract SourceBond is ReentrancyGuard {
    using SafeTransferLib for IERC20;
    using BondingCurve for uint256;

    /// @notice KRX token escrowed as the listing bond.
    IERC20 public immutable krx;

    /// @notice Role registry consulted for governor-gated actions.
    AccessController public immutable acl;

    /// @notice Linear bonding-curve slope (price increase per share).
    uint256 public slope;

    /// @notice Linear bonding-curve base price (price at zero supply).
    uint256 public base;

    /// @notice Total bond shares outstanding across all sources.
    uint256 public totalBonded;

    /// @notice Bond shares held per source.
    mapping(bytes32 => uint256) public bondedShares;

    /// @notice Address that owns (and may unbond) a source's bond.
    mapping(bytes32 => address) public bondHolder;

    event Bonded(bytes32 indexed sourceId, address indexed holder, uint256 shares, uint256 cost);
    event Unbonded(bytes32 indexed sourceId, address indexed holder, uint256 shares, uint256 refund);
    event CurveSet(uint256 slope, uint256 base);

    error NotGovernor();
    error NotBondHolder();
    error AlreadyBonded();
    error ZeroShares();

    /// @notice Restricts a call to accounts holding the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the bond token, access controller and initial curve parameters.
    constructor(IERC20 krx_, AccessController acl_, uint256 slope_, uint256 base_) {
        krx = krx_;
        acl = acl_;
        slope = slope_;
        base = base_;
        emit CurveSet(slope_, base_);
    }

    /// @notice Governor updates the bonding-curve parameters for future bonds.
    /// @dev Existing bonds are refunded against the curve in force at unbond time.
    function setCurve(uint256 slope_, uint256 base_) external onlyGovernor {
        slope = slope_;
        base = base_;
        emit CurveSet(slope_, base_);
    }

    /// @notice Bond `shares` of KRX along the curve to list `sourceId`.
    /// @dev A source may only be bonded once until fully unbonded; the caller
    ///      becomes its bond holder. Pulls the computed KRX cost from the caller.
    function bond(bytes32 sourceId, uint256 shares) external nonReentrant returns (uint256 cost) {
        if (shares == 0) revert ZeroShares();
        if (bondedShares[sourceId] != 0) revert AlreadyBonded();

        cost = totalBonded.costToMint(shares, slope, base);

        // Effects.
        bondedShares[sourceId] = shares;
        bondHolder[sourceId] = msg.sender;
        totalBonded += shares;

        // Interactions.
        krx.safeTransferFrom(msg.sender, address(this), cost);

        emit Bonded(sourceId, msg.sender, shares, cost);
    }

    /// @notice Unbond `shares` from `sourceId`, delisting it (in part or full) and
    ///         refunding the curve value to the bond holder.
    /// @dev Only the recorded bond holder may unbond. When the bond is fully
    ///      withdrawn the holder slot is cleared so the source can be re-listed.
    function unbond(bytes32 sourceId, uint256 shares) external nonReentrant returns (uint256 refund) {
        if (shares == 0) revert ZeroShares();
        address holder = bondHolder[sourceId];
        if (holder != msg.sender) revert NotBondHolder();

        uint256 current = bondedShares[sourceId];
        if (shares > current) revert ZeroShares();

        refund = totalBonded.refundToBurn(shares, slope, base);

        // Effects.
        uint256 remaining = current - shares;
        bondedShares[sourceId] = remaining;
        totalBonded -= shares;
        if (remaining == 0) {
            bondHolder[sourceId] = address(0);
        }

        // Interactions.
        krx.safeTransfer(msg.sender, refund);

        emit Unbonded(sourceId, msg.sender, shares, refund);
    }

    /// @notice Quotes the KRX cost to bond `shares` at the current total supply.
    function quoteBond(uint256 shares) external view returns (uint256) {
        return totalBonded.costToMint(shares, slope, base);
    }
}
