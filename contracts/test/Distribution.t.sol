// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";
import {IERC20} from "../src/interfaces/IERC20.sol";
import {IVotes} from "../src/interfaces/IVotes.sol";
import {IReputationRegistry} from "../src/interfaces/IReputationRegistry.sol";
import {IIdentityRegistry} from "../src/interfaces/IIdentityRegistry.sol";
import {AccessController} from "../src/access/AccessController.sol";
import {IdentityRegistry} from "../src/IdentityRegistry.sol";
import {ReputationRegistry} from "../src/ReputationRegistry.sol";
import {KeryxGovToken} from "../src/governance/KeryxGovToken.sol";
import {Airdrop} from "../src/distribution/Airdrop.sol";
import {MerkleDistributor} from "../src/distribution/MerkleDistributor.sol";
import {RewardClaimGate} from "../src/distribution/RewardClaimGate.sol";
import {SourceGauge} from "../src/distribution/SourceGauge.sol";

contract DistributionTest is Test {
    AccessController acl;
    MockUSDC krx;
    address alice = address(0xA11CE);
    address bob = address(0xB0B);

    function setUp() public {
        acl = new AccessController(address(this));
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(this));
        krx = new MockUSDC();
    }

    function test_airdrop_fans_out_batch() public {
        Airdrop airdrop = new Airdrop(acl, IERC20(address(krx)));
        krx.mint(address(this), 300);
        krx.approve(address(airdrop), 300);

        address[] memory recipients = new address[](2);
        recipients[0] = alice;
        recipients[1] = bob;
        uint256[] memory amounts = new uint256[](2);
        amounts[0] = 100;
        amounts[1] = 200;

        uint256 total = airdrop.drop(recipients, amounts);
        assertEq(total, 300);
        assertEq(krx.balanceOf(alice), 100);
        assertEq(krx.balanceOf(bob), 200);
    }

    function test_merkle_distributor_one_shot_claim() public {
        MerkleDistributor dist = new MerkleDistributor(acl, IERC20(address(krx)));

        bytes32 leaf0 = keccak256(abi.encodePacked(uint256(0), alice, uint256(100)));
        bytes32 leaf1 = keccak256(abi.encodePacked(uint256(1), bob, uint256(200)));
        bytes32 root = leaf0 < leaf1
            ? keccak256(abi.encodePacked(leaf0, leaf1))
            : keccak256(abi.encodePacked(leaf1, leaf0));
        dist.setMerkleRoot(root);
        krx.mint(address(dist), 300);

        bytes32[] memory proof = new bytes32[](1);
        proof[0] = leaf1;
        dist.claim(0, alice, 100, proof);
        assertEq(krx.balanceOf(alice), 100);
        assertTrue(dist.isClaimed(0));

        // Double-claim is rejected.
        vm.expectRevert(MerkleDistributor.AlreadyClaimed.selector);
        dist.claim(0, alice, 100, proof);
    }

    function test_merkle_distributor_bad_proof_reverts() public {
        MerkleDistributor dist = new MerkleDistributor(acl, IERC20(address(krx)));
        bytes32 leaf0 = keccak256(abi.encodePacked(uint256(0), alice, uint256(100)));
        bytes32 leaf1 = keccak256(abi.encodePacked(uint256(1), bob, uint256(200)));
        bytes32 root = leaf0 < leaf1
            ? keccak256(abi.encodePacked(leaf0, leaf1))
            : keccak256(abi.encodePacked(leaf1, leaf0));
        dist.setMerkleRoot(root);
        krx.mint(address(dist), 300);

        bytes32[] memory proof = new bytes32[](1);
        proof[0] = leaf1;
        vm.expectRevert(MerkleDistributor.InvalidProof.selector);
        dist.claim(0, alice, 999, proof); // wrong amount -> leaf mismatch
    }

    function test_reward_claim_gate_thresholds() public {
        IdentityRegistry identity = new IdentityRegistry(address(this));
        uint256 agentId = identity.registerFor(alice, "uri");
        ReputationRegistry reputation = new ReputationRegistry(address(this), IIdentityRegistry(address(identity)));
        reputation.setAuthorized(address(this), true);
        reputation.accrue(agentId, 6000); // avg 6000, 1 citation

        RewardClaimGate gate = new RewardClaimGate(
            IReputationRegistry(address(reputation)), IIdentityRegistry(address(identity)), acl, 5000, 1
        );
        assertTrue(gate.checkEligible(alice), "meets avg & citation thresholds");

        RewardClaimGate strict = new RewardClaimGate(
            IReputationRegistry(address(reputation)), IIdentityRegistry(address(identity)), acl, 7000, 1
        );
        assertFalse(strict.checkEligible(alice), "below the stricter avg threshold");
        vm.expectRevert(RewardClaimGate.GateNotMet.selector);
        strict.requireEligible(alice);
    }

    function test_source_gauge_allocates_weight() public {
        KeryxGovToken gov = new KeryxGovToken(acl);
        gov.mint(alice, 1000);
        vm.prank(alice);
        gov.delegate(alice);

        SourceGauge gauge = new SourceGauge(IVotes(address(gov)), acl);
        bytes32 srcA = keccak256("A");
        bytes32 srcB = keccak256("B");

        vm.prank(alice);
        gauge.vote(srcA, 600);
        vm.prank(alice);
        gauge.vote(srcB, 400);

        assertEq(gauge.relativeWeight(srcA), 6000, "600/1000 in bps");
        assertEq(gauge.relativeWeight(srcB), 4000);

        // Over-allocating beyond voting power reverts.
        vm.prank(alice);
        vm.expectRevert(SourceGauge.InsufficientVotingPower.selector);
        gauge.vote(keccak256("C"), 1);

        // Resetting frees the power.
        vm.prank(alice);
        gauge.resetVote(srcB);
        assertEq(gauge.relativeWeight(srcA), 10000, "srcA now the only weight");
    }
}
