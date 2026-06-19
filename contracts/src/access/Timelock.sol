// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessController} from "./AccessController.sol";
import {Guardian} from "./Guardian.sol";

/// @title Timelock
/// @notice Queues, delays, and executes governance operations; honors Guardian vetoes.
/// @dev Operations are identified by a deterministic hash of their call payload and a
///      caller-supplied salt. A queued operation may only be executed once its delay has
///      elapsed and provided no Guardian has vetoed it. State transitions follow the
///      checks-effects-interactions pattern: the operation is marked Done before the
///      external call is dispatched.
contract Timelock {
    /// @notice Access controller queried for governor authorization.
    AccessController public immutable acl;

    /// @notice Guardian council consulted for operation vetoes prior to execution.
    Guardian public immutable guardian;

    /// @notice Minimum delay (in seconds) enforced between queueing and executing an operation.
    uint256 public minDelay;

    /// @notice Lifecycle state of a queued operation.
    enum OpState {
        Unset,
        Queued,
        Done,
        Cancelled
    }

    /// @notice A scheduled governance operation.
    /// @param target The contract the operation calls.
    /// @param value The native value forwarded with the call.
    /// @param data The calldata dispatched to the target.
    /// @param eta The earliest timestamp at which the operation may execute.
    /// @param state The current lifecycle state of the operation.
    struct Operation {
        address target;
        uint256 value;
        bytes data;
        uint64 eta;
        OpState state;
    }

    /// @notice Operation records keyed by their deterministic identifier.
    mapping(bytes32 => Operation) internal _ops;

    /// @notice Emitted when an operation is queued.
    event Queued(bytes32 indexed id, address target, uint256 value, bytes data, uint64 eta);

    /// @notice Emitted when a queued operation is successfully executed.
    event Executed(bytes32 indexed id);

    /// @notice Emitted when a queued operation is cancelled.
    event Cancelled(bytes32 indexed id);

    /// @notice Emitted when the minimum delay is updated.
    event MinDelaySet(uint256 minDelay);

    /// @notice Thrown when the caller does not hold the governor role.
    error NotGovernor();

    /// @notice Thrown when an operation is not yet ready (eta unreached or not queued).
    error NotReady();

    /// @notice Thrown when queueing an operation whose id is already in use.
    error AlreadyQueued();

    /// @notice Thrown when referencing an operation that was never queued.
    error UnknownOp();

    /// @notice Thrown when attempting to execute an operation the Guardian vetoed.
    error OpVetoed();

    /// @notice Thrown when the target call reverts during execution.
    error CallFailed();

    /// @notice Restricts a function to accounts holding the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the timelock to the access controller and guardian and sets the initial delay.
    /// @param acl_ The deployed AccessController used for governor checks.
    /// @param guardian_ The deployed Guardian consulted for vetoes.
    /// @param minDelay_ The initial minimum delay in seconds.
    constructor(AccessController acl_, Guardian guardian_, uint256 minDelay_) {
        acl = acl_;
        guardian = guardian_;
        minDelay = minDelay_;
        emit MinDelaySet(minDelay_);
    }

    /// @notice Updates the minimum execution delay.
    /// @dev Only callable by a governor. New delays apply to subsequently queued operations.
    /// @param newDelay The new minimum delay in seconds.
    function setMinDelay(uint256 newDelay) external onlyGovernor {
        minDelay = newDelay;
        emit MinDelaySet(newDelay);
    }

    /// @notice Computes the deterministic identifier for an operation.
    /// @param target The contract the operation calls.
    /// @param value The native value forwarded with the call.
    /// @param data The calldata dispatched to the target.
    /// @param salt A caller-supplied value disambiguating otherwise-identical operations.
    /// @return The operation identifier.
    function hashOperation(address target, uint256 value, bytes calldata data, bytes32 salt)
        public
        pure
        returns (bytes32)
    {
        return keccak256(abi.encode(target, value, data, salt));
    }

    /// @notice Queues a governance operation for delayed execution.
    /// @dev Only callable by a governor. The operation's eta is set to the current
    ///      timestamp plus the current minimum delay.
    /// @param target The contract the operation calls.
    /// @param value The native value forwarded with the call.
    /// @param data The calldata dispatched to the target.
    /// @param salt A caller-supplied value disambiguating otherwise-identical operations.
    /// @return id The operation identifier.
    function queue(address target, uint256 value, bytes calldata data, bytes32 salt)
        external
        onlyGovernor
        returns (bytes32 id)
    {
        id = hashOperation(target, value, data, salt);
        if (_ops[id].state != OpState.Unset) revert AlreadyQueued();

        uint64 eta = uint64(block.timestamp + minDelay);
        _ops[id] = Operation({
            target: target,
            value: value,
            data: data,
            eta: eta,
            state: OpState.Queued
        });

        emit Queued(id, target, value, data, eta);
    }

    /// @notice Executes a previously queued operation once ready and not vetoed.
    /// @dev Only callable by a governor. Follows checks-effects-interactions: the
    ///      operation is marked Done before the external call is dispatched.
    /// @param target The contract the operation calls.
    /// @param value The native value forwarded with the call.
    /// @param data The calldata dispatched to the target.
    /// @param salt The salt used when the operation was queued.
    /// @return The raw return data from the target call.
    function execute(address target, uint256 value, bytes calldata data, bytes32 salt)
        external
        payable
        onlyGovernor
        returns (bytes memory)
    {
        bytes32 id = hashOperation(target, value, data, salt);
        Operation storage op = _ops[id];

        if (op.state != OpState.Queued) revert NotReady();
        if (block.timestamp < op.eta) revert NotReady();
        if (guardian.isVetoed(id)) revert OpVetoed();

        // Effects: mark done before interaction to guard against reentrant re-execution.
        op.state = OpState.Done;

        // Interaction.
        (bool ok, bytes memory ret) = target.call{value: value}(data);
        if (!ok) revert CallFailed();

        emit Executed(id);
        return ret;
    }

    /// @notice Cancels a queued operation, preventing its execution.
    /// @dev Only callable by a governor and only for operations still in the Queued state.
    /// @param id The operation identifier to cancel.
    function cancel(bytes32 id) external onlyGovernor {
        Operation storage op = _ops[id];
        if (op.state == OpState.Unset) revert UnknownOp();
        if (op.state != OpState.Queued) revert NotReady();

        op.state = OpState.Cancelled;
        emit Cancelled(id);
    }

    /// @notice Returns the full record for an operation.
    /// @param id The operation identifier to query.
    /// @return The stored operation.
    function getOperation(bytes32 id) external view returns (Operation memory) {
        return _ops[id];
    }
}
