// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";

/// @title SubscriptionManager
/// @notice Recurring period-based USDC subscriptions where an agent (subscriber)
///         pays a publisher (provider) one period's price up front and then on
///         each renewal. Each renewal pulls exactly one period of USDC from the
///         subscriber and extends the paid-through timestamp by the plan period,
///         enabling a pull-on-renew billing model. Subscribers retain the
///         remainder of an already-paid period after cancelling; no pro-rata
///         refunds are issued.
contract SubscriptionManager is ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice The USDC token used for all subscription payments.
    IERC20 public immutable usdc;

    /// @notice A subscription plan offered by a provider.
    /// @param provider The publisher that receives subscription payments.
    /// @param pricePerPeriod The USDC amount charged for each period.
    /// @param period The length of one billing period in seconds.
    /// @param active Whether the plan accepts new subscriptions and renewals.
    struct Plan {
        address provider;
        uint256 pricePerPeriod;
        uint64 period;
        bool active;
    }

    /// @notice An individual subscription tied to a plan.
    /// @param planId The plan this subscription pays into.
    /// @param subscriber The agent paying for the subscription.
    /// @param paidUntil The timestamp through which the subscription is paid.
    /// @param active Whether the subscription is still live (not cancelled).
    struct Sub {
        uint256 planId;
        address subscriber;
        uint64 paidUntil;
        bool active;
    }

    /// @notice Number of plans created; doubles as the next plan id.
    uint256 public totalPlans;

    /// @notice Number of subscriptions created; doubles as the next sub id.
    uint256 public totalSubs;

    /// @dev planId => plan record.
    mapping(uint256 => Plan) internal _plans;

    /// @dev subId => subscription record.
    mapping(uint256 => Sub) internal _subs;

    /// @notice Emitted when a provider creates a new plan.
    event PlanCreated(uint256 indexed planId, address indexed provider, uint256 pricePerPeriod, uint64 period);

    /// @notice Emitted when an agent subscribes to a plan (first period paid).
    event Subscribed(uint256 indexed subId, uint256 indexed planId, address indexed subscriber, uint64 paidUntil);

    /// @notice Emitted when a subscription is renewed for another period.
    event Renewed(uint256 indexed subId, uint64 paidUntil);

    /// @notice Emitted when a subscriber cancels their subscription.
    event Cancelled(uint256 indexed subId);

    /// @notice Thrown when referencing a plan id that does not exist.
    error UnknownPlan();
    /// @notice Thrown when subscribing to or renewing an inactive plan.
    error PlanInactive();
    /// @notice Thrown when a caller is not the subscription's subscriber.
    error NotSubscriber();
    /// @notice Thrown when cancelling a subscription that is already cancelled.
    error AlreadyCancelled();

    /// @notice Wires the manager to its settlement token.
    /// @param usdc_ The USDC token used for subscription payments.
    constructor(IERC20 usdc_) {
        usdc = usdc_;
    }

    /// @notice Creates a new subscription plan owned by the caller.
    /// @param pricePerPeriod The USDC charged per billing period.
    /// @param period The billing period length in seconds (must be non-zero).
    /// @return planId The id of the newly created plan.
    function createPlan(uint256 pricePerPeriod, uint64 period) external returns (uint256 planId) {
        if (period == 0) revert PlanInactive();

        planId = totalPlans++;
        _plans[planId] = Plan({
            provider: msg.sender,
            pricePerPeriod: pricePerPeriod,
            period: period,
            active: true
        });

        emit PlanCreated(planId, msg.sender, pricePerPeriod, period);
    }

    /// @notice Subscribes the caller to a plan, pulling the first period's price.
    /// @dev Checks-effects-interactions: state is written before the token pull.
    /// @param planId The plan to subscribe to.
    /// @return subId The id of the newly created subscription.
    function subscribe(uint256 planId) external nonReentrant returns (uint256 subId) {
        Plan storage plan = _plans[planId];
        if (plan.provider == address(0)) revert UnknownPlan();
        if (!plan.active) revert PlanInactive();

        uint64 paidUntil = uint64(block.timestamp) + plan.period;

        subId = totalSubs++;
        _subs[subId] = Sub({
            planId: planId,
            subscriber: msg.sender,
            paidUntil: paidUntil,
            active: true
        });

        emit Subscribed(subId, planId, msg.sender, paidUntil);

        if (plan.pricePerPeriod != 0) {
            usdc.safeTransferFrom(msg.sender, plan.provider, plan.pricePerPeriod);
        }
    }

    /// @notice Renews a subscription for one more period, pulling another payment.
    /// @dev Anyone may trigger the renewal (pull-on-renew), but funds are always
    ///      pulled from the recorded subscriber. The paid-through timestamp is
    ///      extended from the later of now or the current paid-until, so a lapsed
    ///      subscription resumes from the present without granting back-coverage.
    /// @param subId The subscription to renew.
    function renew(uint256 subId) external nonReentrant {
        Sub storage sub = _subs[subId];
        if (sub.subscriber == address(0)) revert NotSubscriber();
        if (!sub.active) revert AlreadyCancelled();

        Plan storage plan = _plans[sub.planId];
        if (!plan.active) revert PlanInactive();

        uint64 base = sub.paidUntil > block.timestamp ? sub.paidUntil : uint64(block.timestamp);
        uint64 paidUntil = base + plan.period;
        sub.paidUntil = paidUntil;

        emit Renewed(subId, paidUntil);

        if (plan.pricePerPeriod != 0) {
            usdc.safeTransferFrom(sub.subscriber, plan.provider, plan.pricePerPeriod);
        }
    }

    /// @notice Cancels a subscription, stopping future renewals.
    /// @dev Only the subscriber may cancel. Already-paid coverage is retained
    ///      until paidUntil; no refund is issued.
    /// @param subId The subscription to cancel.
    function cancel(uint256 subId) external {
        Sub storage sub = _subs[subId];
        if (sub.subscriber != msg.sender) revert NotSubscriber();
        if (!sub.active) revert AlreadyCancelled();

        sub.active = false;

        emit Cancelled(subId);
    }

    /// @notice Reports whether a subscription is live and still within paid coverage.
    /// @param subId The subscription to query.
    /// @return Whether the subscription is active and paid through the current time.
    function isActive(uint256 subId) external view returns (bool) {
        Sub storage sub = _subs[subId];
        return sub.active && sub.paidUntil >= block.timestamp;
    }

    /// @notice Returns the full subscription record.
    /// @param subId The subscription to query.
    /// @return The stored subscription struct.
    function getSub(uint256 subId) external view returns (Sub memory) {
        return _subs[subId];
    }
}
