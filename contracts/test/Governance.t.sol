// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";
import {IERC20} from "../src/interfaces/IERC20.sol";
import {AccessController} from "../src/access/AccessController.sol";
import {KeryxGovToken} from "../src/governance/KeryxGovToken.sol";
import {VoteEscrow} from "../src/governance/VoteEscrow.sol";
import {GovernanceParams} from "../src/governance/GovernanceParams.sol";

contract GovernanceTest is Test {
    AccessController acl;
    address alice = address(0xA11CE);
    address bob = address(0xB0B);

    function setUp() public {
        acl = new AccessController(address(this));
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(this)); // minter authority
    }

    // --- KeryxGovToken ---
    function test_govtoken_mint_transfer_delegate_votes() public {
        KeryxGovToken krx = new KeryxGovToken(acl);
        krx.mint(alice, 100);
        assertEq(krx.balanceOf(alice), 100);
        assertEq(krx.totalSupply(), 100);

        // Votes only count once delegated.
        assertEq(krx.getVotes(alice), 0);
        vm.prank(alice);
        krx.delegate(alice);
        assertEq(krx.getVotes(alice), 100);

        vm.prank(alice);
        krx.transfer(bob, 40);
        vm.prank(bob);
        krx.delegate(bob);
        assertEq(krx.getVotes(alice), 60);
        assertEq(krx.getVotes(bob), 40);
    }

    function test_govtoken_burn_reduces_votes() public {
        KeryxGovToken krx = new KeryxGovToken(acl);
        krx.mint(alice, 100);
        vm.prank(alice);
        krx.delegate(alice);

        krx.burn(alice, 30); // onlyMinter (this)
        assertEq(krx.balanceOf(alice), 70);
        assertEq(krx.getVotes(alice), 70);
        assertEq(krx.totalSupply(), 70);
    }

    function test_govtoken_past_votes_snapshot() public {
        KeryxGovToken krx = new KeryxGovToken(acl);
        krx.mint(alice, 100);
        vm.prank(alice);
        krx.delegate(alice);
        vm.roll(block.number + 1);
        uint256 snap = block.number - 1;

        // Move tokens now; the historical snapshot is unchanged.
        vm.prank(alice);
        krx.transfer(bob, 100);
        assertEq(krx.getPastVotes(alice, snap), 100, "historical votes preserved");
        assertEq(krx.getVotes(alice), 0, "current votes reflect the transfer");
    }

    function test_govtoken_mint_only_minter() public {
        KeryxGovToken krx = new KeryxGovToken(acl);
        vm.prank(alice);
        vm.expectRevert(KeryxGovToken.NotMinter.selector);
        krx.mint(alice, 1);
    }

    // --- VoteEscrow ---
    function test_voteescrow_power_decays_linearly() public {
        MockUSDC krx = new MockUSDC();
        VoteEscrow ve = new VoteEscrow(IERC20(address(krx)));
        uint256 maxLock = ve.MAX_LOCK();

        krx.mint(alice, 1000);
        vm.startPrank(alice);
        krx.approve(address(ve), 1000);
        ve.createLock(1000, maxLock); // full-length lock -> ~1:1 power
        vm.stopPrank();

        assertEq(ve.balanceOfLock(alice), 1000, "max-length lock mints full power");

        vm.warp(block.timestamp + maxLock / 2);
        assertEq(ve.balanceOfLock(alice), 500, "decays to half at the midpoint");

        vm.warp(block.timestamp + maxLock); // past the end
        assertEq(ve.balanceOfLock(alice), 0);

        vm.prank(alice);
        ve.withdraw();
        assertEq(krx.balanceOf(alice), 1000, "principal recovered after expiry");
    }

    // --- GovernanceParams ---
    function test_governance_params_store() public {
        GovernanceParams gp = new GovernanceParams(acl);
        bytes32 key = keccak256("minStake");
        gp.setUint(key, 42);
        assertEq(gp.getUint(key), 42);

        gp.setAddress(keccak256("treasury"), bob);
        assertEq(gp.getAddress(keccak256("treasury")), bob);
    }

    function test_governance_params_only_governor() public {
        GovernanceParams gp = new GovernanceParams(acl);
        vm.prank(alice);
        vm.expectRevert(GovernanceParams.NotGovernor.selector);
        gp.setUint(keccak256("k"), 1);
    }
}
