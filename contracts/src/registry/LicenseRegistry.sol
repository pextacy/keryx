// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Owned} from "../auth/Owned.sol";
import {SourceRegistry} from "./SourceRegistry.sol";

/// @title LicenseRegistry
/// @notice Binds each registered source to its license terms: commercial-reuse and
///         derivatives flags, a minimum toll (atomic units), and an attribution/terms URI.
contract LicenseRegistry is Owned {
    /// @notice Canonical source catalog this registry licenses against.
    SourceRegistry public immutable sources;

    /// @notice License terms attached to a source.
    struct License {
        bool commercialAllowed;
        bool derivativesAllowed;
        uint256 minTollAtomic;
        string termsURI;
    }

    mapping(bytes32 => License) internal _licenses;

    /// @notice Callers (besides the owner) permitted to set license terms.
    mapping(address => bool) public authorized;

    event LicenseSet(
        bytes32 indexed sourceId,
        bool commercialAllowed,
        bool derivativesAllowed,
        uint256 minTollAtomic,
        string termsURI
    );
    event AuthorizedSet(address indexed caller, bool allowed);

    error NotAuthorized();
    error UnknownSource();

    /// @notice Restricts to the owner or an authorized caller.
    modifier onlyAuthorized() {
        if (msg.sender != owner && !authorized[msg.sender]) revert NotAuthorized();
        _;
    }

    /// @notice Wires the owner and the immutable source registry reference.
    constructor(address owner_, SourceRegistry sources_) Owned(owner_) {
        sources = sources_;
    }

    /// @notice Grants or revokes a caller's authorization to set licenses.
    function setAuthorized(address caller, bool allowed) external onlyOwner {
        authorized[caller] = allowed;
        emit AuthorizedSet(caller, allowed);
    }

    /// @notice Sets (or overwrites) the license terms bound to a known source.
    function setLicense(
        bytes32 sourceId,
        bool commercialAllowed,
        bool derivativesAllowed,
        uint256 minTollAtomic,
        string calldata termsURI
    ) external onlyAuthorized {
        if (sources.getSource(sourceId).registeredAt == 0) revert UnknownSource();

        _licenses[sourceId] = License({
            commercialAllowed: commercialAllowed,
            derivativesAllowed: derivativesAllowed,
            minTollAtomic: minTollAtomic,
            termsURI: termsURI
        });

        emit LicenseSet(sourceId, commercialAllowed, derivativesAllowed, minTollAtomic, termsURI);
    }

    /// @notice Returns the full license terms for a source.
    function getLicense(bytes32 sourceId) external view returns (License memory) {
        return _licenses[sourceId];
    }

    /// @notice Returns the minimum toll (atomic units) required to cite a source.
    function minToll(bytes32 sourceId) external view returns (uint256) {
        return _licenses[sourceId].minTollAtomic;
    }
}
