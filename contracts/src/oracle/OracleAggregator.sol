// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {MedianLib} from "./MedianLib.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title OracleAggregator
/// @notice Collects per-feed submissions from oracle-role reporters and exposes their
///         median as a manipulation-resistant value. Requiring a quorum of independent
///         reporters before a median is readable bounds the influence of any single
///         reporter on the aggregated result.
contract OracleAggregator {
    using MedianLib for uint256[];

    /// @notice Access controller queried for ORACLE_ROLE and GOVERNOR_ROLE authorization.
    AccessController public immutable acl;

    /// @notice Latest value submitted by each reporter, keyed by feed identifier.
    mapping(bytes32 => mapping(address => uint256)) internal _submissions;

    /// @notice Ordered list of distinct reporters that have submitted to each feed.
    mapping(bytes32 => address[]) internal _reporters;

    /// @notice Minimum number of distinct reporters required before a median is readable.
    uint256 public minReporters;

    /// @notice Emitted whenever a reporter submits (or updates) a value for a feed.
    event Submitted(bytes32 indexed feedId, address indexed reporter, uint256 value);

    /// @notice Emitted when the governor updates the minimum reporter quorum.
    event MinReportersSet(uint256 minReporters);

    /// @notice Thrown when a non-oracle caller attempts to submit a value.
    error NotOracle();

    /// @notice Thrown when a non-governor caller attempts a governed change.
    error NotGovernor();

    /// @notice Thrown when a median is requested for a feed below the reporter quorum.
    error TooFewReporters();

    /// @notice Restricts a function to addresses holding the ORACLE_ROLE.
    modifier onlyOracle() {
        if (!acl.hasRole(acl.ORACLE_ROLE(), msg.sender)) revert NotOracle();
        _;
    }

    /// @notice Restricts a function to addresses holding the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the access controller and the initial reporter quorum.
    /// @param acl_ The deployed AccessController used for authorization.
    /// @param minReporters_ The initial minimum distinct-reporter quorum for reads.
    constructor(AccessController acl_, uint256 minReporters_) {
        acl = acl_;
        minReporters = minReporters_;
        emit MinReportersSet(minReporters_);
    }

    /// @notice Governor-only update of the minimum reporter quorum.
    /// @param minReporters_ The new minimum number of distinct reporters required.
    function setMinReporters(uint256 minReporters_) external onlyGovernor {
        minReporters = minReporters_;
        emit MinReportersSet(minReporters_);
    }

    /// @notice Oracle-only submission of a value for a feed.
    /// @dev The reporter is registered once per feed; subsequent submissions overwrite
    ///      the reporter's prior value without growing the reporter set, so each reporter
    ///      contributes exactly one data point to the median.
    /// @param feedId The feed identifier being reported on.
    /// @param value The value submitted by the caller.
    function submit(bytes32 feedId, uint256 value) external onlyOracle {
        // A first-time reporter for this feed is recorded with a sentinel before the
        // value is stored; track membership by checking the prior reporter set.
        if (!_isReporter(feedId, msg.sender)) {
            _reporters[feedId].push(msg.sender);
        }

        _submissions[feedId][msg.sender] = value;

        emit Submitted(feedId, msg.sender, value);
    }

    /// @notice Returns the median of all reporter submissions for a feed.
    /// @dev Reverts when fewer than `minReporters` distinct reporters have submitted,
    ///      preventing a manipulable value from being read under a thin quorum.
    /// @param feedId The feed identifier to aggregate.
    /// @return The median of the current per-reporter submissions.
    function medianOf(bytes32 feedId) external view returns (uint256) {
        address[] storage reporters = _reporters[feedId];
        uint256 count = reporters.length;
        if (count < minReporters || count == 0) revert TooFewReporters();

        uint256[] memory values = new uint256[](count);
        mapping(address => uint256) storage feedSubs = _submissions[feedId];
        for (uint256 i = 0; i < count; ++i) {
            values[i] = feedSubs[reporters[i]];
        }

        return values.median();
    }

    /// @notice Returns the number of distinct reporters that have submitted to a feed.
    /// @param feedId The feed identifier to query.
    /// @return The count of distinct reporters for the feed.
    function reporterCount(bytes32 feedId) external view returns (uint256) {
        return _reporters[feedId].length;
    }

    /// @notice Whether `reporter` has already submitted to `feedId`.
    /// @dev Linear scan over the feed's reporter set; reporter sets are small oracle
    ///      committees, so the cost is bounded and acceptable for the submit path.
    /// @param feedId The feed identifier to check.
    /// @param reporter The reporter address to look for.
    /// @return True if the reporter is already registered for the feed.
    function _isReporter(bytes32 feedId, address reporter) internal view returns (bool) {
        address[] storage reporters = _reporters[feedId];
        uint256 count = reporters.length;
        for (uint256 i = 0; i < count; ++i) {
            if (reporters[i] == reporter) return true;
        }
        return false;
    }
}
