// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";

import {MockUSDC} from "../src/mocks/MockUSDC.sol";
import {IERC20} from "../src/interfaces/IERC20.sol";
import {IVotes} from "../src/interfaces/IVotes.sol";

import {AccessController} from "../src/access/AccessController.sol";
import {Guardian} from "../src/access/Guardian.sol";
import {Timelock} from "../src/access/Timelock.sol";

import {KeryxGovToken} from "../src/governance/KeryxGovToken.sol";
import {VoteEscrow} from "../src/governance/VoteEscrow.sol";
import {KeryxGovernor} from "../src/governance/KeryxGovernor.sol";
import {EmergencyVeto} from "../src/governance/EmergencyVeto.sol";

import {EmissionSchedule} from "../src/distribution/EmissionSchedule.sol";

import {DisputeManager} from "../src/dispute/DisputeManager.sol";
import {ArbitrationPanel} from "../src/dispute/ArbitrationPanel.sol";

/// @notice Regression tests for three real bugs fixed in the suite plus the DeployFull
///         cross-contract wiring that makes the governance/emission/dispute paths actually
///         run. Each test fails against the pre-fix code and passes after it.
contract KeryxWiringTest is Test {
    // --- Bug 1: VoteEscrow.createLock must fold an un-withdrawn expired principal in,
    //            never silently overwrite (orphan) it. ---
    function test_voteescrow_relock_folds_expired_principal() public {
        MockUSDC krx = new MockUSDC();
        VoteEscrow ve = new VoteEscrow(IERC20(address(krx)));
        address user = address(0xBEEF);

        krx.mint(user, 150);
        vm.startPrank(user);
        krx.approve(address(ve), 150);
        ve.createLock(100, 1 days);
        vm.warp(block.timestamp + 2 days); // let the lock expire, unwithdrawn
        ve.createLock(50, 1 days); // must fold the leftover 100 in, not overwrite
        vm.stopPrank();

        (uint256 amount,) = ve.lockOf(user);
        assertEq(amount, 150, "expired principal must be folded in, not orphaned");
        assertEq(krx.balanceOf(address(ve)), 150, "all deposited tokens stay accounted");
    }

    function test_voteescrow_active_lock_reverts() public {
        MockUSDC krx = new MockUSDC();
        VoteEscrow ve = new VoteEscrow(IERC20(address(krx)));
        address user = address(0xBEEF);

        krx.mint(user, 150);
        vm.startPrank(user);
        krx.approve(address(ve), 150);
        ve.createLock(100, 30 days);
        vm.expectRevert(VoteEscrow.LockStillActive.selector);
        ve.createLock(50, 30 days);
        vm.stopPrank();
    }

    // --- Bug 2: KeryxGovernor.castVote must weight votes by a snapshot at startBlock so the
    //            same stake cannot vote twice by being transferred between wallets mid-vote. ---
    function test_governor_snapshot_prevents_double_vote_by_transfer() public {
        AccessController acl = new AccessController(address(this));
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(this)); // mint authority
        KeryxGovToken krx = new KeryxGovToken(acl);
        Guardian guardian = new Guardian(acl);
        Timelock timelock = new Timelock(acl, guardian, 1 days);
        KeryxGovernor gov = new KeryxGovernor(IVotes(address(krx)), timelock, 1, 100, 0, 0);

        address a = address(0xA);
        address b = address(0xB);
        krx.mint(a, 1000e18);
        vm.prank(a);
        krx.delegate(a);
        vm.roll(block.number + 1);

        vm.prank(a);
        uint256 id = gov.propose(address(0xCAFE), 0, "", "desc"); // startBlock = now + 1
        vm.roll(block.number + 2); // strictly past startBlock -> voting open

        vm.prank(a);
        gov.castVote(id, 1);

        // Move the exact same stake to a fresh wallet and try to vote again.
        vm.prank(a);
        krx.transfer(b, 1000e18);
        vm.prank(b);
        krx.delegate(b);
        vm.prank(b);
        gov.castVote(id, 1);

        KeryxGovernor.Proposal memory p = gov.getProposal(id);
        assertEq(p.forVotes, 1000e18, "the same stake must not be counted twice");
    }

    // --- Bug 3: EmergencyVeto.vetoProposal must actually cancel a governor proposal
    //            (guardian path), not revert. Requires the cancel-by-guardian fix + the
    //            DeployFull wiring that grants the veto contract GUARDIAN_ROLE. ---
    function test_emergency_veto_cancels_proposal() public {
        AccessController acl = new AccessController(address(this));
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(this));
        KeryxGovToken krx = new KeryxGovToken(acl);
        Guardian guardian = new Guardian(acl);
        Timelock timelock = new Timelock(acl, guardian, 1 days);
        KeryxGovernor gov = new KeryxGovernor(IVotes(address(krx)), timelock, 1, 100, 0, 0);
        EmergencyVeto veto = new EmergencyVeto(acl, gov);

        acl.bootstrap(acl.GUARDIAN_ROLE(), address(this)); // guardian triggers the veto
        acl.bootstrap(acl.GUARDIAN_ROLE(), address(veto)); // veto -> governor.cancel

        address a = address(0xA);
        krx.mint(a, 1000e18);
        vm.prank(a);
        krx.delegate(a);
        vm.roll(block.number + 1);
        vm.prank(a);
        uint256 id = gov.propose(address(0xCAFE), 0, "", "desc");

        veto.vetoProposal(id);

        assertEq(
            uint256(gov.state(id)),
            uint256(KeryxGovernor.ProposalState.Cancelled),
            "guardian emergency veto must cancel the proposal"
        );
    }

    // --- Wiring: EmissionSchedule must hold GOVERNOR_ROLE so its mint call succeeds. ---
    function test_emission_mints_when_governor_wired() public {
        AccessController acl = new AccessController(address(this));
        KeryxGovToken krx = new KeryxGovToken(acl);
        address target = address(0xD00D);
        EmissionSchedule em = new EmissionSchedule(acl, krx, target, 7 days, 10_000e18, 9_900);
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(em)); // the DeployFull wiring fix

        vm.warp(block.timestamp + 7 days);
        uint256 minted = em.emitEpoch();

        assertEq(minted, 10_000e18);
        assertEq(krx.balanceOf(target), 10_000e18, "emission must mint to the target");
    }

    // --- Wiring: ArbitrationPanel must hold ARBITRATOR_ROLE so its resolve call succeeds. ---
    function test_dispute_resolves_via_panel_when_wired() public {
        AccessController acl = new AccessController(address(this));
        MockUSDC bond = new MockUSDC();
        DisputeManager dm = new DisputeManager(acl, IERC20(address(bond)), 100e18);
        ArbitrationPanel panel = new ArbitrationPanel(acl, dm, 1);

        bytes32 arb = dm.ARBITRATOR_ROLE();
        acl.bootstrap(arb, address(panel)); // panel -> dm.resolve
        acl.bootstrap(arb, address(this)); // arbitrator EOA: moveToArbitration + vote

        address challenger = address(0xC);
        address defendant = address(0xD);
        bond.mint(challenger, 100e18);
        vm.startPrank(challenger);
        bond.approve(address(dm), 100e18);
        uint256 did = dm.fileDispute(defendant, keccak256("data"));
        vm.stopPrank();

        dm.moveToArbitration(did);
        panel.vote(did, true); // threshold 1 -> panel resolves the dispute upheld

        DisputeManager.Dispute memory d = dm.getDispute(did);
        assertEq(uint256(d.phase), uint256(DisputeManager.Phase.Resolved), "dispute must resolve");
        assertTrue(d.upheld, "verdict must be upheld");
        assertEq(bond.balanceOf(challenger), 100e18, "upheld challenge refunds the bond");
    }
}
