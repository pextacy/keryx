// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";
import {IERC20} from "../src/interfaces/IERC20.sol";
import {AccessController} from "../src/access/AccessController.sol";
import {RateLimiter} from "../src/util/RateLimiter.sol";
import {EpochClock} from "../src/util/EpochClock.sol";
import {NonceManager} from "../src/util/NonceManager.sol";
import {MerkleProofLib} from "../src/util/MerkleProofLib.sol";
import {SweepGuard} from "../src/util/SweepGuard.sol";

contract UtilTest is Test {
    AccessController acl;
    address alice = address(0xA11CE);

    function setUp() public {
        acl = new AccessController(address(this));
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(this));
    }

    function test_rate_limiter_token_bucket() public {
        RateLimiter rl = new RateLimiter(address(this));
        bytes32 key = keccak256("router");
        rl.configure(key, 100, 10); // capacity 100, +10/sec
        rl.setAuthorized(address(this), true);

        assertEq(rl.available(key), 100);
        rl.consume(key, 60);
        assertEq(rl.available(key), 40);

        vm.warp(block.timestamp + 2); // +20 refill -> 60
        assertEq(rl.available(key), 60);
        rl.consume(key, 60);

        vm.expectRevert(RateLimiter.RateLimitExceeded.selector);
        rl.consume(key, 1);
    }

    function test_rate_limiter_refill_caps_at_capacity() public {
        RateLimiter rl = new RateLimiter(address(this));
        bytes32 key = keccak256("k");
        rl.configure(key, 100, 10);
        rl.setAuthorized(address(this), true);
        rl.consume(key, 100);
        vm.warp(block.timestamp + 1000); // huge elapse
        assertEq(rl.available(key), 100, "refill clamps to capacity");
    }

    function test_rate_limiter_unauthorized_reverts() public {
        RateLimiter rl = new RateLimiter(address(this));
        bytes32 key = keccak256("k");
        rl.configure(key, 100, 10);
        vm.prank(alice);
        vm.expectRevert(RateLimiter.NotAuthorized.selector);
        rl.consume(key, 1);
    }

    function test_epoch_clock() public {
        uint256 genesis = block.timestamp;
        EpochClock clock = new EpochClock(acl, genesis, 100);

        assertEq(clock.epochAt(genesis), 0);
        assertEq(clock.epochAt(genesis + 150), 1);
        assertEq(clock.epochAt(genesis + 250), 2);
        assertEq(clock.epochStart(2), genesis + 200);

        vm.warp(genesis + 350);
        assertEq(clock.currentEpoch(), 3);

        vm.expectRevert(EpochClock.BeforeGenesis.selector);
        clock.epochAt(genesis - 1);
    }

    function test_nonce_manager_sequential_and_bitmap() public {
        NonceManager nm = new NonceManager(address(this));
        nm.setAuthorized(address(this), true);

        assertEq(nm.useSequential(alice), 0);
        assertEq(nm.useSequential(alice), 1);
        assertEq(nm.sequentialNonce(alice), 2);

        nm.useNonce(alice, 42);
        assertTrue(nm.isUsed(alice, 42));
        vm.expectRevert(NonceManager.NonceAlreadyUsed.selector);
        nm.useNonce(alice, 42);

        // Distinct nonce in the same word is independent.
        assertFalse(nm.isUsed(alice, 43));
        nm.useNonce(alice, 43);
        assertTrue(nm.isUsed(alice, 43));
    }

    function test_nonce_manager_unauthorized_reverts() public {
        NonceManager nm = new NonceManager(address(this));
        vm.prank(alice);
        vm.expectRevert(NonceManager.NotAuthorized.selector);
        nm.useSequential(alice);
    }

    function test_merkle_proof_verifies() public pure {
        bytes32 leafA = keccak256(abi.encodePacked("a"));
        bytes32 leafB = keccak256(abi.encodePacked("b"));
        bytes32 root = leafA < leafB
            ? keccak256(abi.encodePacked(leafA, leafB))
            : keccak256(abi.encodePacked(leafB, leafA));

        bytes32[] memory proof = new bytes32[](1);
        proof[0] = leafB;
        assertTrue(MerkleProofLib.verify(proof, root, leafA));

        // A wrong leaf does not verify against the same proof/root.
        assertFalse(MerkleProofLib.verify(proof, root, keccak256("z")));
    }

    function test_sweep_guard_recovers_unprotected_only() public {
        MockUSDC usdc = new MockUSDC();
        SweepGuard guard = new SweepGuard(acl);
        usdc.mint(address(guard), 1000);

        guard.sweep(IERC20(address(usdc)), alice, 1000);
        assertEq(usdc.balanceOf(alice), 1000);

        MockUSDC krx = new MockUSDC();
        krx.mint(address(guard), 500);
        guard.setProtected(address(krx), true);
        vm.expectRevert(SweepGuard.TokenProtected.selector);
        guard.sweep(IERC20(address(krx)), alice, 500);
    }
}
