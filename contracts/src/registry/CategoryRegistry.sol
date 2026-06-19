// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "../auth/Owned.sol";

/// @title CategoryRegistry
/// @notice Hierarchical content-category taxonomy and per-source category assignment.
contract CategoryRegistry is Owned {
    /// @notice A node in the category taxonomy tree.
    struct Category {
        bytes32 parent;
        string label;
        bool exists;
    }

    /// @dev categoryId => category record.
    mapping(bytes32 => Category) internal _categories;

    /// @notice sourceId => assigned categoryId.
    mapping(bytes32 => bytes32) public categoryOfSource;

    /// @notice Callers permitted to mutate taxonomy and assignments.
    mapping(address => bool) public authorized;

    event CategoryCreated(bytes32 indexed categoryId, bytes32 indexed parent, string label);
    event SourceCategorized(bytes32 indexed sourceId, bytes32 indexed categoryId);
    event AuthorizedSet(address indexed caller, bool allowed);

    error NotAuthorized();
    error AlreadyExists();
    error UnknownCategory();

    /// @dev Restricts to the owner or an explicitly authorized caller.
    modifier onlyAuthorized() {
        if (msg.sender != owner && !authorized[msg.sender]) revert NotAuthorized();
        _;
    }

    /// @param owner_ Initial owner of the registry.
    constructor(address owner_) Owned(owner_) {}

    /// @notice Grant or revoke authorization for a caller.
    /// @param caller Address whose authorization is being set.
    /// @param allowed True to authorize, false to revoke.
    function setAuthorized(address caller, bool allowed) external onlyOwner {
        authorized[caller] = allowed;
        emit AuthorizedSet(caller, allowed);
    }

    /// @notice Create a new category, optionally rooted under an existing parent.
    /// @param categoryId Unique identifier for the new category.
    /// @param parent Parent category id, or bytes32(0) for a root category.
    /// @param label Human-readable label for the category.
    function createCategory(bytes32 categoryId, bytes32 parent, string calldata label) external onlyAuthorized {
        if (_categories[categoryId].exists) revert AlreadyExists();
        if (parent != bytes32(0) && !_categories[parent].exists) revert UnknownCategory();

        _categories[categoryId] = Category({parent: parent, label: label, exists: true});

        emit CategoryCreated(categoryId, parent, label);
    }

    /// @notice Assign a source to an existing category.
    /// @param sourceId Source identifier being categorized.
    /// @param categoryId Target category identifier; must exist.
    function assignCategory(bytes32 sourceId, bytes32 categoryId) external onlyAuthorized {
        if (!_categories[categoryId].exists) revert UnknownCategory();

        categoryOfSource[sourceId] = categoryId;

        emit SourceCategorized(sourceId, categoryId);
    }

    /// @notice Fetch a category record by id.
    /// @param categoryId Category identifier to look up; must exist.
    /// @return The stored category record.
    function getCategory(bytes32 categoryId) external view returns (Category memory) {
        Category memory cat = _categories[categoryId];
        if (!cat.exists) revert UnknownCategory();
        return cat;
    }
}
