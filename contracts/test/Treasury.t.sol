// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";
import {IERC20} from "../src/interfaces/IERC20.sol";
import {ITreasury} from "../src/interfaces/ITreasury.sol";
import {AccessController} from "../src/access/AccessController.sol";
import {CircuitBreaker} from "../src/access/CircuitBreaker.sol";
import {Treasury} from "../src/treasury/Treasury.sol";
import {FeeManager} from "../src/treasury/FeeManager.sol";
import {InsuranceFund} from "../src/treasury/InsuranceFund.sol";
import {RevenueSplitter} from "../src/treasury/RevenueSplitter.sol";
import {BuybackEngine} from "../src/treasury/BuybackEngine.sol";
import {PriceOracle} from "../src/oracle/PriceOracle.sol";
import {KeryxGovToken} from "../src/governance/KeryxGovToken.sol";

contract TreasuryTest is Test {
    MockUSDC usdc;
    AccessController acl;
    CircuitBreaker breaker;
    Treasury treasury;

    address alice = address(0xA11CE);
    address bob = address(0xB0B);

    function setUp() public {
        usdc = new MockUSDC();
        acl = new AccessController(address(this));
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(this));
        acl.bootstrap(acl.GUARDIAN_ROLE(), address(this));
        breaker = new CircuitBreaker(acl);
        treasury = new Treasury(acl, breaker);
        breaker.setAuthorized(address(treasury), true);
    }

    function _fundTreasury(uint256 amount) internal {
        usdc.mint(address(this), amount);
        usdc.approve(address(treasury), amount);
        treasury.deposit(address(usdc), amount);
    }

    function test_deposit_and_withdraw() public {
        _fundTreasury(1000);
        assertEq(treasury.balanceOf(address(usdc)), 1000);

        treasury.withdraw(address(usdc), alice, 400);
        assertEq(usdc.balanceOf(alice), 400);
        assertEq(treasury.balanceOf(address(usdc)), 600);
    }

    function test_withdraw_over_balance_reverts() public {
        _fundTreasury(100);
        vm.expectRevert(Treasury.InsufficientBalance.selector);
        treasury.withdraw(address(usdc), alice, 101);
    }

    function test_withdraw_unauthorized_reverts() public {
        _fundTreasury(100);
        vm.prank(alice);
        vm.expectRevert(Treasury.NotGovernor.selector);
        treasury.withdraw(address(usdc), alice, 50);
    }

    function test_circuit_breaker_blocks_over_cap_outflow() public {
        _fundTreasury(1000);
        // Cap outflow at 500 within a 1-day window.
        breaker.setLimit(address(usdc), 1 days, 500);

        treasury.withdraw(address(usdc), alice, 500); // exactly at cap, ok
        // Any further outflow in the window exceeds the cap and is blocked. (The
        // rolling-window accumulator is the enforcement; the `tripped` latch flag is
        // rolled back by this same revert, so it does not persist across calls.)
        vm.expectRevert(abi.encodeWithSelector(CircuitBreaker.BreakerTripped.selector, address(usdc)));
        treasury.withdraw(address(usdc), alice, 1);
        assertEq(usdc.balanceOf(alice), 500, "over-cap withdrawal was blocked");
    }

    function test_circuit_breaker_window_rolls() public {
        _fundTreasury(1000);
        breaker.setLimit(address(usdc), 1 days, 500);
        treasury.withdraw(address(usdc), alice, 500);

        // After the window elapses the allowance resets.
        vm.warp(block.timestamp + 1 days + 1);
        treasury.withdraw(address(usdc), alice, 500);
        assertEq(usdc.balanceOf(alice), 1000);
    }

    function test_fee_manager_skims_to_treasury() public {
        FeeManager fees = new FeeManager(acl, ITreasury(address(treasury)), address(this), 500); // 5%
        fees.setAuthorized(address(this), true);

        (uint256 qFee, uint256 qNet) = fees.quoteFee(1000);
        assertEq(qFee, 50);
        assertEq(qNet, 950);

        usdc.mint(alice, 1000);
        vm.prank(alice);
        usdc.approve(address(fees), 1000);

        (uint256 fee, uint256 net) = fees.collectFee(IERC20(address(usdc)), alice, 1000);
        assertEq(fee, 50);
        assertEq(net, 950);
        assertEq(treasury.balanceOf(address(usdc)), 50, "fee forwarded to treasury");
        assertEq(usdc.balanceOf(alice), 950, "only the fee leaves the payer here");
    }

    function test_insurance_fund_caps_cumulative_coverage() public {
        InsuranceFund fund = new InsuranceFund(acl, IERC20(address(usdc)), 500);
        fund.setAuthorized(address(this), true);

        usdc.mint(address(this), 1000);
        usdc.approve(address(fund), 1000);
        fund.deposit(1000);

        assertEq(fund.cover(alice, 300, "a"), 300);
        assertEq(fund.cover(alice, 300, "b"), 200, "clamped to remaining cap headroom");
        vm.expectRevert(InsuranceFund.CapExceeded.selector);
        fund.cover(alice, 1, "c");
        assertEq(usdc.balanceOf(alice), 500);
    }

    function test_revenue_splitter_distributes_by_bps() public {
        RevenueSplitter rev = new RevenueSplitter(acl);
        address[] memory accts = new address[](2);
        accts[0] = alice;
        accts[1] = bob;
        uint16[] memory shares = new uint16[](2);
        shares[0] = 6000;
        shares[1] = 4000;
        rev.setPayees(accts, shares);

        usdc.mint(address(rev), 1000);
        uint256 total = rev.distribute(IERC20(address(usdc)));
        assertEq(total, 1000);
        assertEq(usdc.balanceOf(alice), 600);
        assertEq(usdc.balanceOf(bob), 400);
    }

    function test_revenue_splitter_rejects_bad_bps_sum() public {
        RevenueSplitter rev = new RevenueSplitter(acl);
        address[] memory accts = new address[](2);
        accts[0] = alice;
        accts[1] = bob;
        uint16[] memory shares = new uint16[](2);
        shares[0] = 6000;
        shares[1] = 3000; // sums to 9000, not 10000
        vm.expectRevert(RevenueSplitter.BpsSumMismatch.selector);
        rev.setPayees(accts, shares);
    }

    function test_buyback_burns_krx_at_oracle_price() public {
        // Oracle price 1e18 => 1 KRX per 1 USDC unit.
        PriceOracle oracle = new PriceOracle(acl, 1 hours);
        acl.bootstrap(acl.ORACLE_ROLE(), address(this));
        oracle.pushPrice(1e18);

        KeryxGovToken krx = new KeryxGovToken(acl);
        BuybackEngine buyback =
            new BuybackEngine(acl, ITreasury(address(treasury)), IERC20(address(usdc)), krx, oracle, 1e30);
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(buyback)); // withdraw treasury + burn krx

        _fundTreasury(100e6); // treasury holds USDC to spend
        address seller = address(0x5E11E2);
        krx.mint(seller, 100e6); // seller supplies KRX to be burned

        uint256 supplyBefore = krx.totalSupply();
        uint256 bought = buyback.executeBuyback(100e6, seller);

        assertEq(bought, 100e6, "krxBought = usdc / price at 1e18");
        assertEq(usdc.balanceOf(seller), 100e6, "seller paid in USDC");
        assertEq(krx.totalSupply(), supplyBefore - 100e6, "KRX burned");
        assertEq(treasury.balanceOf(address(usdc)), 0);
    }
}
