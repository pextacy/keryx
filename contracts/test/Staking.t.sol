// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";
import {IERC20} from "../src/interfaces/IERC20.sol";
import {IStakeView} from "../src/interfaces/IStakeView.sol";
import {AccessController} from "../src/access/AccessController.sol";
import {StakingVault} from "../src/staking/StakingVault.sol";
import {RewardDistributor} from "../src/staking/RewardDistributor.sol";
import {SlashingController} from "../src/staking/SlashingController.sol";
import {SourceBond} from "../src/staking/SourceBond.sol";
import {ValidatorBondManager} from "../src/staking/ValidatorBondManager.sol";

contract StakingTest is Test {
    MockUSDC krx;
    AccessController acl;
    StakingVault vault;

    address staker = address(0x5742);
    address other = address(0x07E4);
    address insurance = address(0x1453);

    function setUp() public {
        krx = new MockUSDC();
        acl = new AccessController(address(this));
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(this));
        vault = new StakingVault(IERC20(address(krx)), acl, 7 days);
    }

    function _fundAndStake(address who, uint256 amount) internal {
        krx.mint(who, amount);
        vm.startPrank(who);
        krx.approve(address(vault), amount);
        vault.stake(amount);
        vm.stopPrank();
    }

    function test_stake_increases_active_and_total() public {
        _fundAndStake(staker, 1000);
        assertEq(vault.stakeOf(staker), 1000);
        assertEq(vault.totalStaked(), 1000);
        assertEq(krx.balanceOf(address(vault)), 1000);
    }

    function test_unstake_respects_unbonding_then_withdraws() public {
        _fundAndStake(staker, 1000);

        vm.prank(staker);
        vault.requestUnstake(400);
        assertEq(vault.stakeOf(staker), 600);
        assertEq(vault.totalStaked(), 600, "pending unstake leaves total");

        // Cannot withdraw before the unbonding period elapses.
        vm.prank(staker);
        vm.expectRevert(StakingVault.StillBonding.selector);
        vault.withdraw();

        vm.warp(block.timestamp + 7 days);
        vm.prank(staker);
        vault.withdraw();
        assertEq(krx.balanceOf(staker), 400, "unbonded stake returned");
        assertEq(vault.stakeOf(staker), 600);
    }

    function test_request_unstake_over_active_reverts() public {
        _fundAndStake(staker, 100);
        vm.prank(staker);
        vm.expectRevert(StakingVault.InsufficientStake.selector);
        vault.requestUnstake(101);
    }

    function test_vault_slash_drains_active_then_pending() public {
        _fundAndStake(staker, 1000);
        vm.prank(staker);
        vault.requestUnstake(300); // 700 active, 300 pending

        // vault.slash drains active first, then dips into pending unstake.
        acl.bootstrap(acl.SLASHER_ROLE(), address(this));
        uint256 slashed = vault.slash(staker, 800, insurance);
        assertEq(slashed, 800);
        assertEq(vault.stakeOf(staker), 0, "active drained first");
        assertEq(krx.balanceOf(insurance), 800, "seized stake routed to insurance");
    }

    function test_slashing_controller_capped_by_active_stake() public {
        _fundAndStake(staker, 1000);
        vm.prank(staker);
        vault.requestUnstake(300); // 700 active, 300 pending

        // Controller bounds the slash to maxSlashBps of *active* stake (700), so a
        // request for 800 is clamped to 700; pending unstake is not reachable here.
        SlashingController slasher = new SlashingController(vault, acl, insurance, 10_000);
        acl.bootstrap(acl.SLASHER_ROLE(), address(slasher)); // controller -> vault.slash
        acl.bootstrap(acl.SLASHER_ROLE(), address(this)); // this -> controller.slash

        uint256 slashed = slasher.slash(staker, 800, keccak256("case"));
        assertEq(slashed, 700, "clamped to active stake");
        assertEq(vault.stakeOf(staker), 0);
        assertEq(krx.balanceOf(insurance), 700);
    }

    function test_slash_clamped_by_bps() public {
        _fundAndStake(staker, 1000);
        // Cap at 25% of stake.
        SlashingController slasher = new SlashingController(vault, acl, insurance, 2_500);
        acl.bootstrap(acl.SLASHER_ROLE(), address(slasher));
        acl.bootstrap(acl.SLASHER_ROLE(), address(this));

        uint256 slashed = slasher.slash(staker, 1000, keccak256("case"));
        assertEq(slashed, 250, "slash clamped to 25% of stake");
        assertEq(vault.stakeOf(staker), 750);
    }

    function test_slash_unauthorized_reverts() public {
        _fundAndStake(staker, 1000);
        vm.prank(other);
        vm.expectRevert(StakingVault.NotSlasher.selector);
        vault.slash(staker, 100, insurance);
    }

    function test_reward_distributor_streams_pro_rata() public {
        _fundAndStake(staker, 1000);

        RewardDistributor rewards = new RewardDistributor(IERC20(address(krx)), IStakeView(address(vault)), acl);

        // Fund a 700-token reward over 700 seconds => 1 token/sec.
        krx.mint(address(this), 700);
        krx.approve(address(rewards), 700);
        rewards.notifyReward(700, 700);

        vm.warp(block.timestamp + 100);
        assertEq(rewards.earned(staker), 100, "1 token/sec for the sole staker");

        vm.prank(staker);
        uint256 claimed = rewards.claim();
        assertEq(claimed, 100);
        assertEq(krx.balanceOf(staker), 100);
    }

    function test_reward_distributor_splits_between_stakers() public {
        _fundAndStake(staker, 1000);
        _fundAndStake(other, 1000); // equal stake

        RewardDistributor rewards = new RewardDistributor(IERC20(address(krx)), IStakeView(address(vault)), acl);
        krx.mint(address(this), 1000);
        krx.approve(address(rewards), 1000);
        rewards.notifyReward(1000, 1000); // 1 token/sec total

        vm.warp(block.timestamp + 100);
        // 100 tokens emitted, split 50/50 across equal stake.
        assertEq(rewards.earned(staker), 50);
        assertEq(rewards.earned(other), 50);
    }

    function test_reward_notify_unauthorized_reverts() public {
        RewardDistributor rewards = new RewardDistributor(IERC20(address(krx)), IStakeView(address(vault)), acl);
        vm.prank(other);
        vm.expectRevert(RewardDistributor.NotGovernor.selector);
        rewards.notifyReward(100, 100);
    }

    function test_sourcebond_bond_then_unbond_roundtrip() public {
        // Curve: base only (slope 0) so the round-trip is exact and easy to assert.
        SourceBond bond = new SourceBond(IERC20(address(krx)), acl, 0, 1e15);
        bytes32 sourceId = keccak256("src");

        uint256 quote = bond.quoteBond(10);
        krx.mint(staker, quote);
        vm.startPrank(staker);
        krx.approve(address(bond), quote);
        uint256 cost = bond.bond(sourceId, 10);
        assertEq(cost, quote);
        assertEq(bond.totalBonded(), 10);

        uint256 refund = bond.unbond(sourceId, 10);
        vm.stopPrank();
        assertEq(refund, cost, "flat-curve round-trip is value-preserving");
        assertEq(bond.totalBonded(), 0);
        assertEq(bond.bondHolder(sourceId), address(0), "fully unbonded clears holder");
    }

    function test_sourcebond_double_bond_reverts() public {
        SourceBond bond = new SourceBond(IERC20(address(krx)), acl, 0, 1e15);
        bytes32 sourceId = keccak256("src");
        uint256 quote = bond.quoteBond(10);
        krx.mint(staker, quote);
        vm.startPrank(staker);
        krx.approve(address(bond), quote);
        bond.bond(sourceId, 10);
        vm.expectRevert(SourceBond.AlreadyBonded.selector);
        bond.bond(sourceId, 1);
        vm.stopPrank();
    }

    function test_validator_eligibility_tracks_bond() public {
        ValidatorBondManager mgr = new ValidatorBondManager(vault, acl, 500);

        // Below the min bond -> cannot register.
        _fundAndStake(staker, 100);
        vm.prank(staker);
        vm.expectRevert(ValidatorBondManager.InsufficientBond.selector);
        mgr.register();

        // Top up over the threshold and register.
        _fundAndStake(staker, 500); // now 600 staked
        vm.prank(staker);
        mgr.register();
        assertTrue(mgr.isEligibleValidator(staker));

        // Drop below min via unstake request -> no longer eligible (even if registered).
        vm.prank(staker);
        vault.requestUnstake(200); // 400 active < 500
        assertFalse(mgr.isEligibleValidator(staker));
    }
}
