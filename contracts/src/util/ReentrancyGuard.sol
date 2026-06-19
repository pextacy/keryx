// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title ReentrancyGuard
/// @notice Dependency-free reentrancy guard exposing a nonReentrant modifier
///         used by all value-moving Keryx contracts. Uses a status flag set to
///         2 while a guarded call is executing and 1 otherwise (1/2 avoids the
///         repeated zero-to-nonzero SSTORE cost of a boolean flag).
abstract contract ReentrancyGuard {
    /// @notice Thrown when a nonReentrant function is re-entered.
    error Reentrancy();

    /// @dev 1 == not entered, 2 == entered. Internal so derived contracts may
    ///      inspect it if needed; lazily initialised to 1 on first guarded call.
    uint256 internal _status;

    /// @notice Blocks reentrant calls into any function it guards.
    /// @dev Treats an uninitialised status (0) as "not entered" so no
    ///      constructor wiring is required.
    modifier nonReentrant() {
        if (_status == 2) revert Reentrancy();
        _status = 2;
        _;
        _status = 1;
    }
}
