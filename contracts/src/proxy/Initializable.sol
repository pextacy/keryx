// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title Initializable
/// @notice One-time initializer guard for proxy-deployed implementations. Replaces
///         constructors for contracts deployed behind proxies, supporting versioned
///         (re)initialization and the ability to lock the logic contract.
abstract contract Initializable {
    /// @notice Highest initializer version that has run; type(uint8).max means locked.
    uint8 private _initialized;

    /// @notice True only while an initializer chain is executing.
    bool private _initializing;

    /// @notice Emitted when a contract is initialized to a given version.
    event Initialized(uint8 version);

    /// @notice Thrown when an initializer is invoked after it has already run.
    error AlreadyInitialized();

    /// @notice Thrown when an onlyInitializing function runs outside initialization.
    error NotInitializing();

    /// @notice Guards the top-level initializer so it runs exactly once.
    /// @dev Treats version 1 as the canonical first initializer. While nested calls
    ///      are in progress the guard is permissive so parent initializers may invoke
    ///      child initializers; the effect (event + version bump) is applied once.
    modifier initializer() {
        bool isTopLevelCall = !_initializing;
        if (
            !(isTopLevelCall && _initialized < 1) &&
            !(address(this).code.length == 0 && _initialized == 1)
        ) {
            revert AlreadyInitialized();
        }
        _initialized = 1;
        if (isTopLevelCall) {
            _initializing = true;
        }
        _;
        if (isTopLevelCall) {
            _initializing = false;
            emit Initialized(1);
        }
    }

    /// @notice Guards a versioned reinitializer that may run once per ascending version.
    /// @param version The initialization version this reinitializer sets; must be
    ///                strictly greater than any prior version.
    modifier reinitializer(uint8 version) {
        if (_initializing || _initialized >= version) {
            revert AlreadyInitialized();
        }
        _initialized = version;
        _initializing = true;
        _;
        _initializing = false;
        emit Initialized(version);
    }

    /// @notice Restricts a function to only be callable from within an initializer.
    modifier onlyInitializing() {
        if (!_initializing) {
            revert NotInitializing();
        }
        _;
    }

    /// @notice Locks the contract, preventing any future (re)initialization.
    /// @dev Intended to be called in the constructor of logic/implementation
    ///      contracts so the implementation itself can never be initialized.
    function _disableInitializers() internal {
        if (_initializing) {
            revert AlreadyInitialized();
        }
        if (_initialized != type(uint8).max) {
            _initialized = type(uint8).max;
            emit Initialized(type(uint8).max);
        }
    }

    /// @notice Returns the highest initializer version that has been run.
    function _getInitializedVersion() internal view returns (uint8) {
        return _initialized;
    }

    /// @notice Returns whether an initializer chain is currently executing.
    function _isInitializing() internal view returns (bool) {
        return _initializing;
    }
}
