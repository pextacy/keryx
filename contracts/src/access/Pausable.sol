// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title Pausable
/// @notice Provides whenNotPaused/whenPaused modifiers backed by internal pause/unpause state.
abstract contract Pausable {
    /// @notice Whether the contract is currently paused.
    bool private _paused;

    /// @notice Emitted when the pause is triggered by `account`.
    event Paused(address account);

    /// @notice Emitted when the pause is lifted by `account`.
    event Unpaused(address account);

    /// @notice Thrown when an action is attempted while the contract is paused.
    error EnforcedPause();

    /// @notice Thrown when an action requires the paused state but the contract is not paused.
    error ExpectedPause();

    /// @notice Reverts if the contract is paused.
    modifier whenNotPaused() {
        _requireNotPaused();
        _;
    }

    /// @notice Reverts if the contract is not paused.
    modifier whenPaused() {
        _requirePaused();
        _;
    }

    /// @notice Returns true if the contract is paused, false otherwise.
    function paused() public view returns (bool) {
        return _paused;
    }

    /// @notice Triggers the paused state.
    /// @dev Can only be called when the contract is not paused; emits {Paused}.
    function _pause() internal whenNotPaused {
        _paused = true;
        emit Paused(msg.sender);
    }

    /// @notice Lifts the paused state.
    /// @dev Can only be called when the contract is paused; emits {Unpaused}.
    function _unpause() internal whenPaused {
        _paused = false;
        emit Unpaused(msg.sender);
    }

    /// @notice Reverts with {EnforcedPause} if the contract is paused.
    function _requireNotPaused() internal view {
        if (_paused) revert EnforcedPause();
    }

    /// @notice Reverts with {ExpectedPause} if the contract is not paused.
    function _requirePaused() internal view {
        if (!_paused) revert ExpectedPause();
    }
}
