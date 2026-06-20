// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";
import {IERC20} from "../src/interfaces/IERC20.sol";
import {AccessController} from "../src/access/AccessController.sol";
import {PaymentEscrow} from "../src/payments/PaymentEscrow.sol";
import {StreamPayments} from "../src/payments/StreamPayments.sol";
import {SubscriptionManager} from "../src/payments/SubscriptionManager.sol";
import {TokenVesting} from "../src/payments/TokenVesting.sol";
import {TollVault} from "../src/payments/TollVault.sol";

contract PaymentsTest is Test {
    MockUSDC usdc;
    AccessController acl;

    address payer = address(0xA11CE);
    address payee = address(0xB0B);

    function setUp() public {
        usdc = new MockUSDC();
        acl = new AccessController(address(this));
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(this));
        acl.bootstrap(acl.GUARDIAN_ROLE(), address(this));
    }

    // --- PaymentEscrow ---
    function test_escrow_fund_and_release() public {
        PaymentEscrow escrow = new PaymentEscrow(acl, IERC20(address(usdc)));
        usdc.mint(payer, 1000);
        vm.startPrank(payer);
        usdc.approve(address(escrow), 1000);
        uint256 id = escrow.fund(payee, 1000);
        escrow.release(id);
        vm.stopPrank();
        assertEq(usdc.balanceOf(payee), 1000);
    }

    function test_escrow_guardian_refund() public {
        PaymentEscrow escrow = new PaymentEscrow(acl, IERC20(address(usdc)));
        usdc.mint(payer, 1000);
        vm.startPrank(payer);
        usdc.approve(address(escrow), 1000);
        uint256 id = escrow.fund(payee, 1000);
        vm.stopPrank();

        escrow.refund(id); // this holds GUARDIAN (arbiter)
        assertEq(usdc.balanceOf(payer), 1000, "refunded to payer");
    }

    function test_escrow_release_only_payer() public {
        PaymentEscrow escrow = new PaymentEscrow(acl, IERC20(address(usdc)));
        usdc.mint(payer, 1000);
        vm.startPrank(payer);
        usdc.approve(address(escrow), 1000);
        uint256 id = escrow.fund(payee, 1000);
        vm.stopPrank();

        vm.prank(payee);
        vm.expectRevert(PaymentEscrow.NotPayer.selector);
        escrow.release(id);
    }

    // --- StreamPayments ---
    function test_stream_vests_linearly_and_cancels() public {
        StreamPayments streams = new StreamPayments(IERC20(address(usdc)));
        usdc.mint(payer, 1000);
        vm.startPrank(payer);
        usdc.approve(address(streams), 1000);
        uint64 start = uint64(block.timestamp);
        uint256 id = streams.createStream(payee, 1000, start, start + 1000);
        vm.stopPrank();

        vm.warp(block.timestamp + 500);
        assertEq(streams.balanceOfStream(id, payee), 500, "half vested");
        assertEq(streams.balanceOfStream(id, payer), 500, "half refundable");

        vm.prank(payee);
        streams.withdrawFromStream(id, 500);
        assertEq(usdc.balanceOf(payee), 500);

        // Cancel mid-stream: recipient keeps vested, sender refunded the rest.
        vm.prank(payer);
        streams.cancelStream(id);
        assertEq(usdc.balanceOf(payer), 500, "unvested refunded to sender");
    }

    function test_stream_bad_time_range_reverts() public {
        StreamPayments streams = new StreamPayments(IERC20(address(usdc)));
        usdc.mint(payer, 1000);
        vm.startPrank(payer);
        usdc.approve(address(streams), 1000);
        uint64 start = uint64(block.timestamp);
        vm.expectRevert(StreamPayments.BadTimeRange.selector);
        streams.createStream(payee, 1000, start, start); // stop == start
        vm.stopPrank();
    }

    // --- SubscriptionManager ---
    function test_subscription_lifecycle() public {
        SubscriptionManager subs = new SubscriptionManager(IERC20(address(usdc)));
        vm.prank(payee); // payee is the provider
        uint256 planId = subs.createPlan(100, 30 days);

        usdc.mint(payer, 1000);
        vm.prank(payer);
        usdc.approve(address(subs), 1000);
        vm.prank(payer);
        uint256 subId = subs.subscribe(planId);
        assertTrue(subs.isActive(subId));
        assertEq(usdc.balanceOf(payee), 100, "first period paid to provider");

        vm.warp(block.timestamp + 31 days);
        assertFalse(subs.isActive(subId), "lapsed after the paid period");

        subs.renew(subId); // pull-on-renew, anyone can trigger; funds from subscriber
        assertEq(usdc.balanceOf(payee), 200);
        assertTrue(subs.isActive(subId));
    }

    // --- TokenVesting ---
    function test_vesting_cliff_linear_release() public {
        MockUSDC krx = new MockUSDC();
        TokenVesting vesting = new TokenVesting(acl, IERC20(address(krx)));
        krx.mint(address(this), 1000);
        krx.approve(address(vesting), 1000);

        uint64 start = uint64(block.timestamp);
        uint256 id = vesting.createSchedule(payee, 1000, start, start, 1000, true);

        vm.warp(block.timestamp + 500);
        assertEq(vesting.vestedAmount(id), 500);

        vm.prank(payee);
        uint256 released = vesting.release(id);
        assertEq(released, 500);
        assertEq(krx.balanceOf(payee), 500);
    }

    function test_vesting_revoke_refunds_unvested() public {
        MockUSDC krx = new MockUSDC();
        TokenVesting vesting = new TokenVesting(acl, IERC20(address(krx)));
        krx.mint(address(this), 1000);
        krx.approve(address(vesting), 1000);
        uint64 start = uint64(block.timestamp);
        uint256 id = vesting.createSchedule(payee, 1000, start, start, 1000, true);

        vm.warp(block.timestamp + 400); // 400 vested, 600 unvested
        uint256 refund = vesting.revoke(id);
        assertEq(refund, 600, "unvested returned to governor");
        assertEq(krx.balanceOf(address(this)), 600);
    }

    // --- TollVault ---
    function test_tollvault_accrue_and_claim() public {
        TollVault tv = new TollVault(IERC20(address(usdc)), address(this));
        tv.setAuthorized(address(this), true);

        usdc.mint(payer, 300);
        vm.prank(payer);
        usdc.approve(address(tv), 300);

        tv.credit(payer, payee, 100);
        tv.credit(payer, payee, 50);
        assertEq(tv.claimable(payee), 150);

        vm.prank(payee);
        uint256 claimed = tv.claim();
        assertEq(claimed, 150);
        assertEq(usdc.balanceOf(payee), 150);
        assertEq(tv.claimable(payee), 0);
    }

    function test_tollvault_credit_unauthorized_reverts() public {
        TollVault tv = new TollVault(IERC20(address(usdc)), address(this));
        vm.prank(payer);
        vm.expectRevert(TollVault.NotAuthorized.selector);
        tv.credit(payer, payee, 100);
    }
}
