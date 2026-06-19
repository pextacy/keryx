// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title Multicall
/// @notice Aggregates multiple delegatecalls to self into one transaction for batched admin ops.
/// @dev Each entry in `data` is an ABI-encoded call to a function on this same contract,
///      executed via `delegatecall` so that `msg.sender` and storage context are preserved
///      across the batch. Reverts the entire transaction if any sub-call fails.
abstract contract Multicall {
    /// @notice Thrown when the sub-call at the given index reverts without bubbling a reason.
    /// @param index The position in the `data` array that failed.
    error MulticallFailed(uint256 index);

    /// @notice Executes a batch of delegatecalls against this contract in a single transaction.
    /// @dev Uses `delegatecall` to `address(this)` so that the original caller and storage
    ///      layout are preserved for every encoded call. If a sub-call reverts with return
    ///      data, that revert reason is bubbled up verbatim; otherwise a `MulticallFailed`
    ///      error carrying the failing index is raised. The whole batch is atomic.
    /// @param data The list of ABI-encoded function calls to execute against this contract.
    /// @return results The ABI-encoded return data from each successful sub-call, in order.
    function multicall(bytes[] calldata data) external returns (bytes[] memory results) {
        uint256 length = data.length;
        results = new bytes[](length);

        for (uint256 i = 0; i < length; ) {
            (bool success, bytes memory returnData) = address(this).delegatecall(data[i]);

            if (!success) {
                // Bubble up the original revert reason when present.
                if (returnData.length > 0) {
                    assembly {
                        let returnDataSize := mload(returnData)
                        revert(add(returnData, 0x20), returnDataSize)
                    }
                }
                revert MulticallFailed(i);
            }

            results[i] = returnData;

            unchecked {
                ++i;
            }
        }
    }
}
