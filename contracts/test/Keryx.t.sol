// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";
import {KeryxToll} from "../src/KeryxToll.sol";
import {IdentityRegistry} from "../src/IdentityRegistry.sol";
import {ReputationRegistry} from "../src/ReputationRegistry.sol";
import {ValidationRegistry} from "../src/ValidationRegistry.sol";
import {CitationRegistry} from "../src/CitationRegistry.sol";
import {CitationSplitter} from "../src/CitationSplitter.sol";
import {KeryxSettlement} from "../src/KeryxSettlement.sol";
import {IIdentityRegistry} from "../src/interfaces/IIdentityRegistry.sol";
import {IReputationRegistry} from "../src/interfaces/IReputationRegistry.sol";
import {IERC20} from "../src/interfaces/IERC20.sol";
import {AttestationLib} from "../src/libraries/AttestationLib.sol";
import {CitationLib} from "../src/libraries/CitationLib.sol";
import {GroundingMath} from "../src/libraries/GroundingMath.sol";

/// Full coverage of the Keryx on-chain suite: economics, ERC-8004 triad, signed
/// attestations, weighted splits, and the end-to-end pay-on-citation settlement.
contract KeryxTest is Test {
    address owner = address(this);
    uint256 agentPk = 0xA11CE;
    address agent;

    MockUSDC usdc;
    KeryxToll toll;
    IdentityRegistry identity;
    ReputationRegistry reputation;
    ValidationRegistry validation;
    CitationRegistry citations;
    CitationSplitter splitter;
    KeryxSettlement settlement;

    // Mirrors shared/config.py: floor $0.000001, band $0.001–$0.01, T=0.5 (USDC 6dp).
    uint256 constant FLOOR = 1;
    uint256 constant TOLL_MIN = 1_000;
    uint256 constant TOLL_MAX = 10_000;
    uint16 constant T_BPS = 5_000;

    function setUp() public {
        agent = vm.addr(agentPk);
        usdc = new MockUSDC();
        toll = new KeryxToll(owner, FLOOR, TOLL_MIN, TOLL_MAX, T_BPS);
        identity = new IdentityRegistry(owner);
        reputation = new ReputationRegistry(owner, IIdentityRegistry(address(identity)));
        validation = new ValidationRegistry(owner);
        citations = new CitationRegistry(owner);
        splitter = new CitationSplitter(owner);
        settlement = new KeryxSettlement(
            owner,
            IERC20(address(usdc)),
            citations,
            IIdentityRegistry(address(identity)),
            IReputationRegistry(address(reputation)),
            splitter,
            toll
        );
        // Wire authorizations: only the settlement orchestrator writes the registries.
        reputation.setAuthorized(address(settlement), true);
        citations.setAuthorized(address(settlement), true);
        splitter.setAuthorized(address(settlement), true);
    }

    // --- Economics (KeryxToll / GroundingMath) ---

    function test_toll_scales_with_g_within_band() public view {
        assertEq(toll.amountFor(0), TOLL_MIN); // g=0 -> min (clamped above floor)
        assertEq(toll.amountFor(10_000), TOLL_MAX); // g=1 -> max
        uint256 mid = toll.amountFor(5_000);
        assertGt(mid, TOLL_MIN);
        assertLt(mid, TOLL_MAX);
    }

    function test_toll_gate() public view {
        assertFalse(toll.isCited(4_999));
        assertTrue(toll.isCited(5_000));
    }

    function test_toll_owner_only() public {
        vm.prank(address(0xBEEF));
        vm.expectRevert();
        toll.setToll(FLOOR, TOLL_MIN, TOLL_MAX, T_BPS);
    }

    // --- Identity (ERC-8004) ---

    function test_identity_register_and_resolve() public {
        uint256 id = identity.registerFor(address(0xA1), "ipfs://a1");
        assertEq(id, 1);
        assertEq(identity.agentIdOf(address(0xA1)), 1);
        assertEq(identity.walletOf(1), address(0xA1));
        assertTrue(identity.isRegistered(address(0xA1)));
        assertEq(identity.totalAgents(), 1);
    }

    function test_identity_no_double_register() public {
        identity.registerFor(address(0xA1), "x");
        vm.expectRevert(IdentityRegistry.AlreadyRegistered.selector);
        identity.registerFor(address(0xA1), "y");
    }

    /// The "200 authors" intent done correctly: ONE registry holding many identities.
    function test_identity_scales_to_200_authors() public {
        for (uint256 i = 1; i <= 200; i++) {
            identity.registerFor(address(uint160(0x1000 + i)), "");
        }
        assertEq(identity.totalAgents(), 200);
        assertEq(identity.agentIdOf(address(uint160(0x1000 + 200))), 200);
    }

    // --- Reputation (ERC-8004) ---

    function test_reputation_accrues_only_when_authorized() public {
        identity.registerFor(address(0xA1), "");
        reputation.setAuthorized(owner, true);
        reputation.accrue(1, 8_000);
        reputation.accrue(1, 6_000);
        (uint256 score, uint256 n, uint256 avg) = reputation.reputationOf(1);
        assertEq(score, 14_000);
        assertEq(n, 2);
        assertEq(avg, 7_000);
    }

    function test_reputation_unauthorized_reverts() public {
        identity.registerFor(address(0xA1), "");
        vm.prank(address(0xBEEF));
        vm.expectRevert(ReputationRegistry.NotAuthorized.selector);
        reputation.accrue(1, 5_000);
    }

    // --- Validation (ERC-8004) ---

    function test_validation_request_respond() public {
        address validator = address(0x7A11);
        validation.setValidator(validator, true);
        uint256 reqId = validation.requestValidation(1, keccak256("data"), validator);
        vm.prank(validator);
        validation.respondValidation(reqId, 9_000);
        ValidationRegistry.Request memory r = validation.getRequest(reqId);
        assertEq(uint8(r.status), uint8(ValidationRegistry.Status.Responded));
        assertEq(r.responseBps, 9_000);
    }

    // --- Attestation signing / registry ---

    function _attest(bytes32 root, uint256 nonce) internal view returns (AttestationLib.Attestation memory a) {
        a = AttestationLib.Attestation({
            queryHash: keccak256("q"),
            answerHash: keccak256("a"),
            citationsRoot: root,
            agent: agent,
            ts: uint64(block.timestamp),
            nonce: nonce
        });
    }

    function _sign(AttestationLib.Attestation memory a) internal view returns (bytes memory) {
        bytes32 sep = citations.DOMAIN_SEPARATOR();
        bytes32 digest = AttestationLib.digest(a, sep);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(agentPk, digest);
        return abi.encodePacked(r, s, v);
    }

    function test_citation_registry_records_valid_signature() public {
        citations.setAuthorized(owner, true);
        AttestationLib.Attestation memory a = _attest(keccak256("cites"), 1);
        uint256 id = citations.recordAttestation(a, _sign(a));
        assertEq(id, 1);
        assertEq(citations.recover(a, _sign(a)), agent);
    }

    function test_citation_registry_rejects_replay() public {
        citations.setAuthorized(owner, true);
        AttestationLib.Attestation memory a = _attest(keccak256("cites"), 1);
        bytes memory sig = _sign(a);
        citations.recordAttestation(a, sig);
        vm.expectRevert(CitationRegistry.AlreadyRecorded.selector);
        citations.recordAttestation(a, sig);
    }

    function test_citation_registry_rejects_wrong_signer() public {
        citations.setAuthorized(owner, true);
        AttestationLib.Attestation memory a = _attest(keccak256("cites"), 1);
        // Sign with a different key -> recovered signer != att.agent.
        bytes32 digest = AttestationLib.digest(a, citations.DOMAIN_SEPARATOR());
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(0xB0B, digest);
        vm.expectRevert(CitationRegistry.BadSignature.selector);
        citations.recordAttestation(a, abi.encodePacked(r, s, v));
    }

    // --- Splitter ---

    function test_split_weighted_distributes_full_pot() public {
        address[] memory authors = new address[](3);
        uint16[] memory g = new uint16[](3);
        authors[0] = address(0xA1);
        authors[1] = address(0xA2);
        authors[2] = address(0xA3);
        g[0] = 6_000;
        g[1] = 3_000;
        g[2] = 1_000;
        address payer = address(0xCA11);
        usdc.mint(payer, 1_000_000);
        vm.prank(payer);
        usdc.approve(address(splitter), type(uint256).max);
        splitter.setAuthorized(owner, true);
        uint256 distributed = splitter.splitWeighted(IERC20(address(usdc)), payer, 100_000, authors, g);
        assertEq(distributed, 100_000); // full pot, no dust left
        assertEq(usdc.balanceOf(address(0xA1)), 60_000);
        assertEq(usdc.balanceOf(address(0xA2)), 30_000);
        assertEq(usdc.balanceOf(address(0xA3)), 10_000); // remainder absorbed by last
    }

    function test_split_unauthorized_reverts() public {
        address[] memory authors = new address[](1);
        uint256[] memory amounts = new uint256[](1);
        authors[0] = address(0xA1);
        amounts[0] = 1;
        vm.prank(address(0xBEEF));
        vm.expectRevert(CitationSplitter.NotAuthorized.selector);
        splitter.distribute(IERC20(address(usdc)), address(this), authors, amounts);
    }

    // --- End-to-end settlement ---

    function _twoCitations() internal pure returns (CitationLib.Citation[] memory cites) {
        cites = new CitationLib.Citation[](2);
        cites[0] = CitationLib.Citation({
            sourceId: keccak256("s1"),
            author: address(0xA1),
            gBps: 9_000,
            amount: 9_100 // within [floor, max]; ~ amountFor(9000)
        });
        cites[1] = CitationLib.Citation({sourceId: keccak256("s2"), author: address(0xA2), gBps: 6_000, amount: 6_400});
    }

    function test_settle_end_to_end_pays_and_accrues() public {
        identity.registerFor(address(0xA1), "");
        identity.registerFor(address(0xA2), "");
        CitationLib.Citation[] memory cites = _twoCitations();
        AttestationLib.Attestation memory a = _attest(CitationLib.hash(cites), 1);
        bytes memory sig = _sign(a);

        address payer = address(0xCAFE);
        usdc.mint(payer, 1_000_000);
        vm.prank(payer);
        usdc.approve(address(splitter), type(uint256).max);

        vm.prank(payer);
        (uint256 attId, uint256 totalPaid) = settlement.settle(a, cites, sig);

        assertEq(attId, 1);
        assertEq(totalPaid, 9_100 + 6_400);
        assertEq(usdc.balanceOf(address(0xA1)), 9_100);
        assertEq(usdc.balanceOf(address(0xA2)), 6_400);

        (uint256 s1,,) = reputation.reputationOf(identity.agentIdOf(address(0xA1)));
        assertEq(s1, 9_000);
        (uint256 s2,,) = reputation.reputationOf(identity.agentIdOf(address(0xA2)));
        assertEq(s2, 6_000);
        assertEq(citations.totalAttestations(), 1);
    }

    /// Pay-on-citation: a citation below T is rejected at settlement, never paid.
    function test_settle_rejects_below_threshold() public {
        identity.registerFor(address(0xA1), "");
        CitationLib.Citation[] memory cites = new CitationLib.Citation[](1);
        cites[0] = CitationLib.Citation({
            sourceId: keccak256("s1"),
            author: address(0xA1),
            gBps: 4_000, // below T=5000
            amount: 5_000
        });
        AttestationLib.Attestation memory a = _attest(CitationLib.hash(cites), 1);
        bytes memory sig = _sign(a);
        usdc.mint(address(0xCAFE), 1_000_000);
        vm.startPrank(address(0xCAFE));
        usdc.approve(address(splitter), type(uint256).max);
        vm.expectRevert(abi.encodeWithSelector(KeryxSettlement.NotGrounded.selector, keccak256("s1")));
        settlement.settle(a, cites, sig);
        vm.stopPrank();
    }

    function test_settle_rejects_unregistered_author() public {
        CitationLib.Citation[] memory cites = new CitationLib.Citation[](1);
        cites[0] =
            CitationLib.Citation({sourceId: keccak256("s1"), author: address(0xDEAD), gBps: 9_000, amount: 9_000});
        AttestationLib.Attestation memory a = _attest(CitationLib.hash(cites), 1);
        bytes memory sig = _sign(a);
        usdc.mint(address(0xCAFE), 1_000_000);
        vm.startPrank(address(0xCAFE));
        usdc.approve(address(splitter), type(uint256).max);
        vm.expectRevert(abi.encodeWithSelector(KeryxSettlement.AuthorNotRegistered.selector, address(0xDEAD)));
        settlement.settle(a, cites, sig);
        vm.stopPrank();
    }

    function test_settle_rejects_tampered_citations_root() public {
        identity.registerFor(address(0xA1), "");
        CitationLib.Citation[] memory cites = _twoCitations();
        // Attestation commits to a different root than the citations passed.
        AttestationLib.Attestation memory a = _attest(keccak256("wrong-root"), 1);
        bytes memory sig = _sign(a);
        usdc.mint(address(0xCAFE), 1_000_000);
        vm.startPrank(address(0xCAFE));
        usdc.approve(address(splitter), type(uint256).max);
        vm.expectRevert(KeryxSettlement.CitationsRootMismatch.selector);
        settlement.settle(a, cites, sig);
        vm.stopPrank();
    }
}
