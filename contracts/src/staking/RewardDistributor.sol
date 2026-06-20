// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {IStakeView} from "../interfaces/IStakeView.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title RewardDistributor
/// @notice Accumulator-based pro-rata staking reward streaming using reward-per-token accounting.
///         Governor funds a reward over a duration; stakers accrue rewards proportional to their
///         stake (read from an external IStakeView) and claim the streamed reward token.
contract RewardDistributor is ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice Token distributed as staking rewards.
    IERC20 public immutable rewardToken;

    /// @notice Read-only source of per-account and total stake.
    IStakeView public immutable stakeView;

    /// @notice Role registry consulted for governor authorization.
    AccessController public immutable acl;

    /// @notice Accumulated reward-per-token, scaled by 1e18, snapshotted at lastUpdate.
    uint256 public rewardPerTokenStored;

    /// @notice Timestamp at which rewardPerTokenStored was last brought current.
    uint256 public lastUpdate;

    /// @notice Reward token emitted per second during the active period.
    uint256 public rewardRate;

    /// @notice Timestamp at which the current reward period ends.
    uint256 public periodFinish;

    /// @notice Reward-per-token already accounted to each user at their last checkpoint.
    mapping(address => uint256) public userRewardPerTokenPaid;

    /// @notice Reward token owed to each user, accrued up to their last checkpoint.
    mapping(address => uint256) public rewards;

    /// @dev Fixed-point scale for reward-per-token accounting.
    uint256 private constant PRECISION = 1e18;

    event RewardAdded(uint256 amount, uint256 duration);
    event RewardPaid(address indexed user, uint256 amount);
    event Checkpointed(address indexed user, uint256 earned);

    error NotGovernor();
    error NothingToClaim();
    error RewardTooHigh();

    /// @notice Wires the reward token, stake view, and access controller.
    constructor(IERC20 rewardToken_, IStakeView stakeView_, AccessController acl_) {
        rewardToken = rewardToken_;
        stakeView = stakeView_;
        acl = acl_;
        // lastUpdate stays 0 until the first reward period opens. Seeding it to
        // block.timestamp here would underflow `_rewardPerToken` (elapsed =
        // lastTimeRewardApplicable(0, no period yet) - lastUpdate) the moment anyone
        // stakes before the first notifyReward — the normal stake-then-fund order.
    }

    /// @dev Reverts unless the caller holds the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @dev The last timestamp at which rewards are applicable (now, capped at periodFinish).
    function _lastTimeRewardApplicable() internal view returns (uint256) {
        return block.timestamp < periodFinish ? block.timestamp : periodFinish;
    }

    /// @dev Current global reward-per-token, including unaccrued emissions since lastUpdate.
    function _rewardPerToken() internal view returns (uint256) {
        uint256 totalStaked = stakeView.totalStaked();
        if (totalStaked == 0) {
            return rewardPerTokenStored;
        }
        uint256 elapsed = _lastTimeRewardApplicable() - lastUpdate;
        return rewardPerTokenStored + (elapsed * rewardRate * PRECISION) / totalStaked;
    }

    /// @dev Earned-but-unclaimed reward for a user given a reward-per-token value.
    function _earned(address user, uint256 rewardPerToken_) internal view returns (uint256) {
        uint256 stake = stakeView.stakeOf(user);
        uint256 delta = rewardPerToken_ - userRewardPerTokenPaid[user];
        return rewards[user] + (stake * delta) / PRECISION;
    }

    /// @dev Brings global accounting current and, if a user is given, snapshots their accrual.
    function _updateReward(address user) internal {
        uint256 currentRewardPerToken = _rewardPerToken();
        rewardPerTokenStored = currentRewardPerToken;
        lastUpdate = _lastTimeRewardApplicable();
        if (user != address(0)) {
            rewards[user] = _earned(user, currentRewardPerToken);
            userRewardPerTokenPaid[user] = currentRewardPerToken;
        }
    }

    /// @notice Funds a new reward stream of `amount` over `duration` seconds, pulling tokens
    ///         from the caller. Any undistributed reward from an ongoing period is rolled in.
    function notifyReward(uint256 amount, uint256 duration) external onlyGovernor nonReentrant {
        if (duration == 0) revert RewardTooHigh();
        _updateReward(address(0));

        uint256 newRate;
        if (block.timestamp >= periodFinish) {
            newRate = amount / duration;
        } else {
            uint256 remaining = periodFinish - block.timestamp;
            uint256 leftover = remaining * rewardRate;
            newRate = (amount + leftover) / duration;
        }
        if (newRate == 0) revert RewardTooHigh();

        rewardToken.safeTransferFrom(msg.sender, address(this), amount);

        // Guard against a rate that the contract balance cannot sustain for the duration.
        uint256 balance = rewardToken.balanceOf(address(this));
        if (newRate > balance / duration) revert RewardTooHigh();

        rewardRate = newRate;
        lastUpdate = block.timestamp;
        periodFinish = block.timestamp + duration;

        emit RewardAdded(amount, duration);
    }

    /// @notice Brings a user's reward accrual current without claiming.
    function checkpoint(address user) external nonReentrant {
        _updateReward(user);
        emit Checkpointed(user, rewards[user]);
    }

    /// @notice Returns the reward token currently earned and unclaimed by `user`.
    function earned(address user) external view returns (uint256) {
        return _earned(user, _rewardPerToken());
    }

    /// @notice Claims all earned reward token for the caller.
    function claim() external nonReentrant returns (uint256 amount) {
        _updateReward(msg.sender);
        amount = rewards[msg.sender];
        if (amount == 0) revert NothingToClaim();
        rewards[msg.sender] = 0;
        rewardToken.safeTransfer(msg.sender, amount);
        emit RewardPaid(msg.sender, amount);
    }

    /// @notice Returns the current global reward-per-token, scaled by 1e18.
    function rewardPerToken() external view returns (uint256) {
        return _rewardPerToken();
    }
}
