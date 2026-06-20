// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";
import {IERC20} from "../src/interfaces/IERC20.sol";
import {IGroundingConsensus} from "../src/interfaces/IGroundingConsensus.sol";
import {AccessController} from "../src/access/AccessController.sol";
import {StakingVault} from "../src/staking/StakingVault.sol";
import {SlashingController} from "../src/staking/SlashingController.sol";
import {GroundingAttestor} from "../src/oracle/GroundingAttestor.sol";
import {DisputeManager} from "../src/dispute/DisputeManager.sol";
import {DisputeResolver} from "../src/dispute/DisputeResolver.sol";
import {EvidenceRegistry} from "../src/dispute/EvidenceRegistry.sol";
import {AppealCourt} from "../src/dispute/AppealCourt.sol";

contract DisputeTest is Test {
    MockUSDC bondToken;
    AccessController acl;
    DisputeManager dm;
    bytes32 arb;

    address challenger = address(0xC4A);
    address defendant = address(0xDEF);

    function setUp() public {
        bondToken = new MockUSDC();
        acl = new AccessController(address(this));
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(this));
        dm = new DisputeManager(acl, IERC20(address(bondToken)), 100);
        arb = dm.ARBITRATOR_ROLE();
        acl.bootstrap(arb, address(this)); // this is the arbitrator EOA
    }

    function _file() internal returns (uint256 id) {
        bondToken.mint(challenger, 100);
        vm.startPrank(challenger);
        bondToken.approve(address(dm), 100);
        id = dm.fileDispute(defendant, keccak256("data"));
        vm.stopPrank();
    }

    function test_dispute_upheld_refunds_challenger() public {
        uint256 id = _file();
        assertEq(bondToken.balanceOf(address(dm)), 100, "bond escrowed");

        dm.moveToArbitration(id);
        dm.resolve(id, true); // upheld -> challenger wins, bond returned
        assertEq(bondToken.balanceOf(challenger), 100);
        assertEq(uint256(dm.getDispute(id).phase), uint256(DisputeManager.Phase.Resolved));
    }

    function test_dispute_rejected_forwards_bond_to_defendant() public {
        uint256 id = _file();
        dm.moveToArbitration(id);
        dm.resolve(id, false); // not upheld -> bond to defendant
        assertEq(bondToken.balanceOf(defendant), 100);
    }

    function test_dispute_resolve_wrong_phase_reverts() public {
        uint256 id = _file();
        // Still Open (not moved to arbitration).
        vm.expectRevert(DisputeManager.WrongPhase.selector);
        dm.resolve(id, true);
    }

    function test_evidence_registry_appends() public {
        uint256 id = _file();
        EvidenceRegistry ev = new EvidenceRegistry(dm);
        ev.submitEvidence(id, keccak256("e1"), "ipfs://e1");
        vm.prank(defendant);
        ev.submitEvidence(id, keccak256("e2"), "ipfs://e2");
        assertEq(ev.evidenceCount(id), 2);
        assertEq(ev.evidenceAt(id, 1).submitter, defendant);
    }

    function test_dispute_resolver_slashes_on_upheld() public {
        // Build the slashing stack.
        MockUSDC krx = new MockUSDC();
        StakingVault vault = new StakingVault(IERC20(address(krx)), acl, 7 days);
        SlashingController slasher = new SlashingController(vault, acl, address(0x1452), 10_000);
        GroundingAttestor attestor = new GroundingAttestor(acl, 1);
        DisputeResolver resolver =
            new DisputeResolver(acl, dm, slasher, IGroundingConsensus(address(attestor)), 500);
        acl.bootstrap(acl.SLASHER_ROLE(), address(slasher)); // controller -> vault.slash
        acl.bootstrap(acl.SLASHER_ROLE(), address(resolver)); // resolver -> controller.slash

        // Offender stakes, so there is something to slash.
        krx.mint(defendant, 1000);
        vm.startPrank(defendant);
        krx.approve(address(vault), 1000);
        vault.stake(1000);
        vm.stopPrank();

        // File + resolve a dispute as upheld, then settle it into a slash.
        uint256 id = _file();
        dm.moveToArbitration(id);
        dm.resolve(id, true);

        uint256 slashed = resolver.settleDispute(id, defendant);
        assertEq(slashed, 500, "fixed slash amount applied");
        assertEq(vault.stakeOf(defendant), 500);
        assertEq(krx.balanceOf(address(0x1452)), 500, "seized stake to insurance fund");
    }

    function test_appeal_court_overturns_and_refunds() public {
        AppealCourt appeals = new AppealCourt(acl, dm, IERC20(address(bondToken)), 200);
        acl.bootstrap(arb, address(appeals)); // appeals -> dm.openAppeal/resolve
        acl.bootstrap(appeals.CHIEF_ARBITRATOR_ROLE(), address(this));

        uint256 id = _file();
        dm.moveToArbitration(id);

        // Appellant lodges an appeal with the higher bond.
        bondToken.mint(defendant, 200);
        vm.startPrank(defendant);
        bondToken.approve(address(appeals), 200);
        appeals.lodgeAppeal(id);
        vm.stopPrank();
        assertEq(uint256(dm.getDispute(id).phase), uint256(DisputeManager.Phase.Appeal));

        // Chief arbitrator overturns -> appellant bond refunded, dispute resolved.
        appeals.ruleAppeal(id, true);
        assertEq(bondToken.balanceOf(defendant), 200, "overturn refunds the appeal bond");
        assertEq(uint256(dm.getDispute(id).phase), uint256(DisputeManager.Phase.Resolved));
    }
}
