// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "../auth/Owned.sol";

/// @title RateLimiter
/// @notice Token-bucket per-key rate limiting (refill rate + capacity) consumed by
///         routers and oracles. Each `key` maps to an independent bucket that refills
///         linearly at `refillPerSecond` up to `capacity`. Authorized callers (set by
///         the owner) draw down tokens via `consume`; requests that would exceed the
///         currently available tokens revert with `RateLimitExceeded`.
contract RateLimiter is Owned {
    /// @notice Per-key token-bucket state.
    /// @dev `tokens` and `lastRefill` are lazily reconciled on each consume/configure.
    struct Bucket {
        uint256 capacity;
        uint256 refillPerSecond;
        uint256 tokens;
        uint64 lastRefill;
    }

    /// @notice Key => bucket state.
    mapping(bytes32 => Bucket) internal _buckets;

    /// @notice Callers permitted to consume from buckets.
    mapping(address => bool) public authorized;

    event BucketConfigured(bytes32 indexed key, uint256 capacity, uint256 refillPerSecond);
    event Consumed(bytes32 indexed key, uint256 amount, uint256 remaining);
    event AuthorizedSet(address indexed caller, bool allowed);

    error NotAuthorized();
    error RateLimitExceeded();

    /// @notice Restricts a function to callers the owner has authorized.
    modifier onlyAuthorized() {
        if (!authorized[msg.sender]) revert NotAuthorized();
        _;
    }

    /// @notice Deploys the rate limiter under a single owner.
    /// @param owner_ Address granted owner privileges.
    constructor(address owner_) Owned(owner_) {}

    /// @notice Grants or revokes a caller's authorization to consume tokens.
    /// @param caller Address whose authorization is being set.
    /// @param allowed True to authorize, false to revoke.
    function setAuthorized(address caller, bool allowed) external onlyOwner {
        authorized[caller] = allowed;
        emit AuthorizedSet(caller, allowed);
    }

    /// @notice Configures (or reconfigures) the bucket for a key.
    /// @dev Resets the bucket to full `capacity` and stamps `lastRefill` to now.
    /// @param key Bucket identifier.
    /// @param capacity Maximum number of tokens the bucket can hold.
    /// @param refillPerSecond Tokens regenerated per second, capped at `capacity`.
    function configure(bytes32 key, uint256 capacity, uint256 refillPerSecond) external onlyOwner {
        Bucket storage b = _buckets[key];
        b.capacity = capacity;
        b.refillPerSecond = refillPerSecond;
        b.tokens = capacity;
        b.lastRefill = uint64(block.timestamp);
        emit BucketConfigured(key, capacity, refillPerSecond);
    }

    /// @notice Consumes `amount` tokens from a key's bucket, refilling first.
    /// @dev Checks-effects-interactions: state is reconciled and updated before the
    ///      event is emitted; reverts if insufficient tokens are available.
    /// @param key Bucket identifier.
    /// @param amount Number of tokens to draw down.
    function consume(bytes32 key, uint256 amount) external onlyAuthorized {
        Bucket storage b = _buckets[key];
        uint256 current = _refilled(b);
        if (amount > current) revert RateLimitExceeded();
        uint256 remaining = current - amount;
        b.tokens = remaining;
        b.lastRefill = uint64(block.timestamp);
        emit Consumed(key, amount, remaining);
    }

    /// @notice Returns the tokens currently available for a key, accounting for refill.
    /// @param key Bucket identifier.
    /// @return Number of tokens available right now.
    function available(bytes32 key) external view returns (uint256) {
        return _refilled(_buckets[key]);
    }

    /// @notice Computes the bucket's token balance after applying linear refill.
    /// @dev Pure view over storage; does not mutate state.
    /// @param b Bucket to evaluate.
    /// @return Tokens available, clamped to `capacity`.
    function _refilled(Bucket storage b) internal view returns (uint256) {
        uint256 capacity = b.capacity;
        uint256 tokens = b.tokens;
        uint256 rate = b.refillPerSecond;
        if (rate == 0 || capacity == 0) {
            return tokens > capacity ? capacity : tokens;
        }
        uint256 elapsed = block.timestamp - uint256(b.lastRefill);
        if (elapsed == 0) {
            return tokens;
        }
        uint256 refilled = tokens + elapsed * rate;
        return refilled > capacity ? capacity : refilled;
    }
}
