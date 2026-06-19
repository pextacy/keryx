// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "./AccessController.sol";

/// @title CircuitBreaker
/// @notice Tracks per-asset outflow within a rolling window and trips when a flow cap is exceeded.
contract CircuitBreaker {
    /// @notice Role registry consulted for guardian authorization.
    AccessController public immutable acl;

    /// @notice Per-asset rolling-window outflow limit configuration and live state.
    struct Limit {
        uint256 windowSeconds;
        uint256 maxOutflow;
        uint256 windowStart;
        uint256 outflowInWindow;
        bool tripped;
    }

    /// @notice Per-asset limit records.
    mapping(address => Limit) internal _limits;

    /// @notice Contracts allowed to register outflows (e.g. the Treasury / router).
    mapping(address => bool) public authorized;

    event LimitSet(address indexed asset, uint256 windowSeconds, uint256 maxOutflow);
    event Tripped(address indexed asset, uint256 attempted);
    event Reset(address indexed asset);
    event AuthorizedSet(address indexed caller, bool allowed);

    error NotGuardian();
    error NotAuthorized();
    error BreakerTripped(address asset);

    /// @notice Restricts a call to accounts holding the guardian role.
    modifier onlyGuardian() {
        if (!acl.hasRole(acl.GUARDIAN_ROLE(), msg.sender)) revert NotGuardian();
        _;
    }

    /// @notice Restricts a call to authorized outflow registrars.
    modifier onlyAuthorized() {
        if (!authorized[msg.sender]) revert NotAuthorized();
        _;
    }

    /// @notice Wires the access controller used for guardian checks.
    /// @param acl_ The deployed AccessController instance.
    constructor(AccessController acl_) {
        acl = acl_;
    }

    /// @notice Grants or revokes the right to register outflows for an asset.
    /// @param caller The contract or account whose authorization is being set.
    /// @param allowed Whether the caller may register outflows.
    function setAuthorized(address caller, bool allowed) external onlyGuardian {
        authorized[caller] = allowed;
        emit AuthorizedSet(caller, allowed);
    }

    /// @notice Configures the rolling-window flow cap for an asset and clears live state.
    /// @param asset The asset the limit applies to.
    /// @param windowSeconds The length of the rolling window in seconds.
    /// @param maxOutflow The maximum cumulative outflow tolerated within a window.
    function setLimit(address asset, uint256 windowSeconds, uint256 maxOutflow) external onlyGuardian {
        Limit storage lim = _limits[asset];
        lim.windowSeconds = windowSeconds;
        lim.maxOutflow = maxOutflow;
        lim.windowStart = block.timestamp;
        lim.outflowInWindow = 0;
        lim.tripped = false;
        emit LimitSet(asset, windowSeconds, maxOutflow);
        emit Reset(asset);
    }

    /// @notice Records an outflow for an asset, rolling the window and tripping on cap breach.
    /// @param asset The asset being moved out.
    /// @param amount The amount of outflow to account for.
    function registerOutflow(address asset, uint256 amount) external onlyAuthorized {
        Limit storage lim = _limits[asset];

        // Already tripped: reject until a guardian resets.
        if (lim.tripped) revert BreakerTripped(asset);

        // Assets with no configured cap are unrestricted.
        if (lim.maxOutflow == 0) {
            return;
        }

        // Roll the window forward if the current one has elapsed.
        if (lim.windowSeconds == 0 || block.timestamp >= lim.windowStart + lim.windowSeconds) {
            lim.windowStart = block.timestamp;
            lim.outflowInWindow = 0;
        }

        uint256 newOutflow = lim.outflowInWindow + amount;
        if (newOutflow > lim.maxOutflow) {
            lim.tripped = true;
            emit Tripped(asset, newOutflow);
            revert BreakerTripped(asset);
        }

        lim.outflowInWindow = newOutflow;
    }

    /// @notice Clears a tripped breaker and restarts the window for an asset.
    /// @param asset The asset whose breaker is being reset.
    function reset(address asset) external onlyGuardian {
        Limit storage lim = _limits[asset];
        lim.tripped = false;
        lim.windowStart = block.timestamp;
        lim.outflowInWindow = 0;
        emit Reset(asset);
    }

    /// @notice Returns whether the breaker for an asset is currently tripped.
    /// @param asset The asset to query.
    /// @return Whether the asset's breaker has tripped.
    function isTripped(address asset) external view returns (bool) {
        return _limits[asset].tripped;
    }
}
