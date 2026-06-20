// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {AccessController} from "../src/access/AccessController.sol";
import {PriceOracle} from "../src/oracle/PriceOracle.sol";
import {TWAPOracle} from "../src/oracle/TWAPOracle.sol";
import {OracleAggregator} from "../src/oracle/OracleAggregator.sol";
import {GroundingAttestor} from "../src/oracle/GroundingAttestor.sol";

contract OracleTest is Test {
    AccessController acl;

    address r1 = address(0x1111);
    address r2 = address(0x2222);
    address r3 = address(0x3333);

    function setUp() public {
        acl = new AccessController(address(this));
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(this));
        acl.bootstrap(acl.ORACLE_ROLE(), address(this));
    }

    function test_price_oracle_push_and_staleness() public {
        PriceOracle oracle = new PriceOracle(acl, 1 hours);
        oracle.pushPrice(1e18);
        assertEq(oracle.getPrice(), 1e18);
        assertFalse(oracle.isStale());

        vm.warp(block.timestamp + 2 hours);
        assertTrue(oracle.isStale());
        vm.expectRevert(PriceOracle.StalePrice.selector);
        oracle.getPrice();
    }

    function test_price_oracle_only_oracle_pushes() public {
        PriceOracle oracle = new PriceOracle(acl, 1 hours);
        vm.prank(r2);
        vm.expectRevert(PriceOracle.NotOracle.selector);
        oracle.pushPrice(1e18);
    }

    function test_twap_constant_price() public {
        PriceOracle spot = new PriceOracle(acl, 1 days);
        spot.pushPrice(100);
        TWAPOracle twap = new TWAPOracle(acl, spot);

        vm.warp(block.timestamp + 100);
        twap.update(); // accrues the prior price (100) over 100s
        assertEq(twap.consult(100), 100, "constant price -> TWAP equals it");
    }

    function test_twap_tracks_price_change() public {
        PriceOracle spot = new PriceOracle(acl, 1 days);
        spot.pushPrice(100);
        TWAPOracle twap = new TWAPOracle(acl, spot);

        vm.warp(block.timestamp + 100);
        spot.pushPrice(200);
        twap.update(); // accrues old price 100 over the first 100s

        vm.warp(block.timestamp + 100);
        // Over the trailing 100s the price was 200.
        assertEq(twap.consult(100), 200);
    }

    function test_aggregator_median_with_quorum() public {
        acl.bootstrap(acl.ORACLE_ROLE(), r1);
        acl.bootstrap(acl.ORACLE_ROLE(), r2);
        acl.bootstrap(acl.ORACLE_ROLE(), r3);
        OracleAggregator agg = new OracleAggregator(acl, 3);
        bytes32 feed = keccak256("KRX/USDC");

        vm.prank(r1);
        agg.submit(feed, 10);
        vm.prank(r2);
        agg.submit(feed, 30);

        // Below quorum -> not readable.
        vm.expectRevert(OracleAggregator.TooFewReporters.selector);
        agg.medianOf(feed);

        vm.prank(r3);
        agg.submit(feed, 20);
        assertEq(agg.medianOf(feed), 20, "median of {10,20,30}");
    }

    function test_aggregator_resubmit_overwrites_not_duplicates() public {
        acl.bootstrap(acl.ORACLE_ROLE(), r1);
        acl.bootstrap(acl.ORACLE_ROLE(), r2);
        OracleAggregator agg = new OracleAggregator(acl, 1);
        bytes32 feed = keccak256("f");

        vm.prank(r1);
        agg.submit(feed, 10);
        vm.prank(r1);
        agg.submit(feed, 50); // same reporter updates, no new slot
        vm.prank(r2);
        agg.submit(feed, 30);

        assertEq(agg.reporterCount(feed), 2, "each reporter counted once");
        assertEq(agg.medianOf(feed), 40, "median of {30,50}");
    }

    function test_grounding_attestor_consensus_mean() public {
        acl.bootstrap(acl.ORACLE_ROLE(), r1);
        acl.bootstrap(acl.ORACLE_ROLE(), r2);
        GroundingAttestor attestor = new GroundingAttestor(acl, 2);
        bytes32 dataHash = keccak256("answer");

        vm.prank(r1);
        attestor.submitScore(dataHash, 4000);
        vm.prank(r2);
        attestor.submitScore(dataHash, 6000);

        uint16 consensus = attestor.finalize(dataHash);
        assertEq(consensus, 5000, "arithmetic mean of submitted bps");

        (uint16 gBps, bool finalized) = attestor.consensusOf(dataHash);
        assertEq(gBps, 5000);
        assertTrue(finalized);
    }

    function test_grounding_attestor_quorum_enforced() public {
        acl.bootstrap(acl.ORACLE_ROLE(), r1);
        GroundingAttestor attestor = new GroundingAttestor(acl, 2);
        bytes32 dataHash = keccak256("answer");
        vm.prank(r1);
        attestor.submitScore(dataHash, 5000);

        vm.expectRevert(GroundingAttestor.QuorumNotMet.selector);
        attestor.finalize(dataHash);
    }
}
