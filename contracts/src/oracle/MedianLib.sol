// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title MedianLib
/// @notice Pure in-place sort and median computation over a uint256 array for oracle aggregation.
library MedianLib {
    /// @notice Thrown when the median of an empty array is requested.
    error EmptyArray();

    /// @notice Computes the median of `values`, sorting the array in place.
    /// @dev For an even-length array the lower-mean of the two central elements is returned,
    ///      using an overflow-safe average. Sorts in place, so the caller's array is mutated.
    /// @param values The array to compute the median of; mutated to sorted order.
    /// @return The median value.
    function median(uint256[] memory values) internal pure returns (uint256) {
        uint256 len = values.length;
        if (len == 0) revert EmptyArray();

        sort(values);

        uint256 mid = len / 2;
        if (len % 2 == 1) {
            return values[mid];
        }

        // Even length: average the two central elements without overflowing.
        uint256 lo = values[mid - 1];
        uint256 hi = values[mid];
        // lo <= hi after sorting, so (hi - lo) cannot underflow.
        return lo + (hi - lo) / 2;
    }

    /// @notice Sorts `values` in place in ascending order using insertion sort.
    /// @dev Insertion sort is chosen for its simplicity and good performance on the
    ///      small reporter sets typical of oracle aggregation. Stable and in-place.
    /// @param values The array to sort in place.
    function sort(uint256[] memory values) internal pure {
        uint256 len = values.length;
        for (uint256 i = 1; i < len; ++i) {
            uint256 key = values[i];
            uint256 j = i;
            while (j > 0 && values[j - 1] > key) {
                values[j] = values[j - 1];
                unchecked {
                    --j;
                }
            }
            values[j] = key;
        }
    }
}
