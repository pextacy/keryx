// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessController} from "../access/AccessController.sol";

/// @title PriceOracle
/// @notice Oracle-role-pushed KRX/USDC spot price with staleness checks.
contract PriceOracle {
    /// @notice Access controller queried for ORACLE_ROLE and GOVERNOR_ROLE authorization.
    AccessController public immutable acl;

    /// @notice Last pushed KRX/USDC spot price, scaled to PRICE_DECIMALS.
    uint256 public price;

    /// @notice Block timestamp at which `price` was last updated.
    uint64 public updatedAt;

    /// @notice Maximum age (in seconds) before a price is considered stale.
    uint256 public maxStaleness;

    /// @notice Fixed-point decimals used for `price`.
    uint8 public constant PRICE_DECIMALS = 18;

    /// @notice Emitted when an oracle pushes a fresh price.
    event PricePushed(uint256 price, uint64 timestamp);

    /// @notice Emitted when the governor updates the staleness threshold.
    event MaxStalenessSet(uint256 maxStaleness);

    /// @notice Thrown when a non-oracle caller attempts to push a price.
    error NotOracle();

    /// @notice Thrown when a non-governor caller attempts a governed change.
    error NotGovernor();

    /// @notice Thrown when reading a price that is older than `maxStaleness`.
    error StalePrice();

    /// @notice Thrown when a zero price is pushed.
    error ZeroPrice();

    /// @notice Restricts a function to addresses holding the ORACLE_ROLE.
    modifier onlyOracle() {
        if (!acl.hasRole(acl.ORACLE_ROLE(), msg.sender)) revert NotOracle();
        _;
    }

    /// @notice Restricts a function to addresses holding the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the access controller and the initial staleness threshold.
    /// @param acl_ The deployed AccessController used for authorization.
    /// @param maxStaleness_ The initial maximum price age in seconds.
    constructor(AccessController acl_, uint256 maxStaleness_) {
        acl = acl_;
        maxStaleness = maxStaleness_;
        emit MaxStalenessSet(maxStaleness_);
    }

    /// @notice Governor-only update of the staleness threshold.
    /// @param maxStaleness_ The new maximum price age in seconds.
    function setMaxStaleness(uint256 maxStaleness_) external onlyGovernor {
        maxStaleness = maxStaleness_;
        emit MaxStalenessSet(maxStaleness_);
    }

    /// @notice Oracle-only push of a fresh KRX/USDC spot price.
    /// @param newPrice The new price scaled to PRICE_DECIMALS; must be non-zero.
    function pushPrice(uint256 newPrice) external onlyOracle {
        if (newPrice == 0) revert ZeroPrice();
        uint64 ts = uint64(block.timestamp);
        price = newPrice;
        updatedAt = ts;
        emit PricePushed(newPrice, ts);
    }

    /// @notice Returns the current price, reverting if it is stale.
    /// @return The most recent non-stale price scaled to PRICE_DECIMALS.
    function getPrice() external view returns (uint256) {
        if (_isStale()) revert StalePrice();
        return price;
    }

    /// @notice Reports whether the current price is older than `maxStaleness`.
    /// @return True if the price is stale, false otherwise.
    function isStale() external view returns (bool) {
        return _isStale();
    }

    /// @dev Internal staleness check shared by getPrice and isStale.
    function _isStale() internal view returns (bool) {
        if (updatedAt == 0) return true;
        return block.timestamp > uint256(updatedAt) + maxStaleness;
    }
}
