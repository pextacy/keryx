// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title AddressSetLib
/// @notice Enumerable address set backed by a values array plus a 1-based index
///         map, supporting O(1) add/remove/contains and O(1) indexed access.
/// @dev Positions are stored as 1-based so that the default zero value of the
///      `positions` mapping unambiguously means "not present". Removal uses the
///      swap-and-pop technique to keep the values array dense.
library AddressSetLib {
    /// @notice Enumerable set of addresses.
    /// @dev `positions[v]` holds (index in `values`) + 1; 0 means absent.
    struct Set {
        address[] values;
        mapping(address => uint256) positions;
    }

    /// @notice Adds `v` to the set.
    /// @param s The set storage reference.
    /// @param v The address to add.
    /// @return added True if the address was not already present and was added.
    function add(Set storage s, address v) internal returns (bool added) {
        if (s.positions[v] != 0) {
            return false;
        }
        s.values.push(v);
        // Position is 1-based: length after push equals (index + 1).
        s.positions[v] = s.values.length;
        return true;
    }

    /// @notice Removes `v` from the set using swap-and-pop.
    /// @param s The set storage reference.
    /// @param v The address to remove.
    /// @return removed True if the address was present and was removed.
    function remove(Set storage s, address v) internal returns (bool removed) {
        uint256 position = s.positions[v];
        if (position == 0) {
            return false;
        }

        uint256 valueIndex = position - 1;
        uint256 lastIndex = s.values.length - 1;

        if (valueIndex != lastIndex) {
            address lastValue = s.values[lastIndex];
            s.values[valueIndex] = lastValue;
            s.positions[lastValue] = position; // 1-based position of moved element
        }

        s.values.pop();
        delete s.positions[v];
        return true;
    }

    /// @notice Returns whether `v` is in the set.
    /// @param s The set storage reference.
    /// @param v The address to check.
    /// @return True if `v` is a member.
    function contains(Set storage s, address v) internal view returns (bool) {
        return s.positions[v] != 0;
    }

    /// @notice Returns the number of members in the set.
    /// @param s The set storage reference.
    /// @return The element count.
    function length(Set storage s) internal view returns (uint256) {
        return s.values.length;
    }

    /// @notice Returns the member stored at index `i`.
    /// @dev Reverts via array bounds check if `i >= length(s)`. Ordering is not
    ///      stable across removals due to swap-and-pop.
    /// @param s The set storage reference.
    /// @param i The index to read.
    /// @return The address at index `i`.
    function at(Set storage s, uint256 i) internal view returns (address) {
        return s.values[i];
    }

    /// @notice Returns a copy of all members as a memory array.
    /// @param s The set storage reference.
    /// @return A memory array of every member address.
    function valuesOf(Set storage s) internal view returns (address[] memory) {
        return s.values;
    }
}
