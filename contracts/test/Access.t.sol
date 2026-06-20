// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {AccessController} from "../src/access/AccessController.sol";
import {Roles} from "../src/access/Roles.sol";
import {Guardian} from "../src/access/Guardian.sol";
import {GuardianPause} from "../src/access/GuardianPause.sol";
import {Timelock} from "../src/access/Timelock.sol";
import {MultiSigWallet} from "../src/access/MultiSigWallet.sol";

/// @dev Minimal call target for Timelock/MultiSig execution tests.
contract Target {
    uint256 public value;

    function setValue(uint256 v) external {
        value = v;
    }
}

contract AccessTest is Test {
    AccessController acl;
    address alice = address(0xA11CE);
    address bob = address(0xB0B);
    address carol = address(0xCC);

    function setUp() public {
        acl = new AccessController(address(this));
    }

    // --- Roles ---
    function test_role_grant_revoke_renounce() public {
        bytes32 gov = acl.GOVERNOR_ROLE();
        acl.grantRole(gov, alice); // this is admin (DEFAULT_ADMIN_ROLE)
        assertTrue(acl.hasRole(gov, alice));

        acl.revokeRole(gov, alice);
        assertFalse(acl.hasRole(gov, alice));

        acl.grantRole(gov, alice);
        vm.prank(alice);
        acl.renounceRole(gov);
        assertFalse(acl.hasRole(gov, alice));
    }

    function test_role_grant_requires_admin() public {
        bytes32 gov = acl.GOVERNOR_ROLE();
        bytes32 adminRole = acl.DEFAULT_ADMIN_ROLE();
        vm.prank(alice); // alice is not admin of GOVERNOR_ROLE
        vm.expectRevert(abi.encodeWithSelector(Roles.MissingRole.selector, adminRole, alice));
        acl.grantRole(gov, bob);
    }

    // --- Timelock ---
    function _timelock() internal returns (Timelock tl, Guardian g, Target t) {
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(this));
        g = new Guardian(acl);
        tl = new Timelock(acl, g, 2 days);
        t = new Target();
    }

    function test_timelock_queue_delay_execute() public {
        (Timelock tl, , Target t) = _timelock();
        bytes memory data = abi.encodeWithSelector(Target.setValue.selector, 42);
        tl.queue(address(t), 0, data, bytes32("s"));

        // Before the delay elapses, execution is not ready.
        vm.expectRevert(Timelock.NotReady.selector);
        tl.execute(address(t), 0, data, bytes32("s"));

        vm.warp(block.timestamp + 2 days);
        tl.execute(address(t), 0, data, bytes32("s"));
        assertEq(t.value(), 42);
    }

    function test_timelock_guardian_veto_blocks_execution() public {
        (Timelock tl, Guardian g, Target t) = _timelock();
        acl.bootstrap(acl.GUARDIAN_ROLE(), address(this));
        bytes memory data = abi.encodeWithSelector(Target.setValue.selector, 7);
        bytes32 id = tl.queue(address(t), 0, data, bytes32("s"));

        g.veto(id);
        vm.warp(block.timestamp + 2 days);
        vm.expectRevert(Timelock.OpVetoed.selector);
        tl.execute(address(t), 0, data, bytes32("s"));
    }

    function test_timelock_cancel() public {
        (Timelock tl, , Target t) = _timelock();
        bytes memory data = abi.encodeWithSelector(Target.setValue.selector, 1);
        bytes32 id = tl.queue(address(t), 0, data, bytes32("s"));
        tl.cancel(id);
        vm.warp(block.timestamp + 2 days);
        vm.expectRevert(Timelock.NotReady.selector);
        tl.execute(address(t), 0, data, bytes32("s"));
    }

    // --- MultiSigWallet ---
    function test_multisig_m_of_n_execution() public {
        address[] memory owners = new address[](3);
        owners[0] = address(this);
        owners[1] = bob;
        owners[2] = carol;
        MultiSigWallet wallet = new MultiSigWallet(owners, 2);

        Target t = new Target();
        bytes memory data = abi.encodeWithSelector(Target.setValue.selector, 99);

        uint256 txId = wallet.submit(address(t), 0, data); // submitter auto-confirms (1)

        // One confirmation is below threshold.
        vm.expectRevert(MultiSigWallet.NotEnoughConfirmations.selector);
        wallet.execute(txId);

        vm.prank(bob);
        wallet.confirm(txId); // 2 confirmations
        wallet.execute(txId);
        assertEq(t.value(), 99);
    }

    function test_multisig_non_owner_cannot_submit() public {
        address[] memory owners = new address[](2);
        owners[0] = address(this);
        owners[1] = bob;
        MultiSigWallet wallet = new MultiSigWallet(owners, 2);
        vm.prank(alice);
        vm.expectRevert(MultiSigWallet.NotOwner.selector);
        wallet.submit(address(0), 0, "");
    }

    // --- Guardian + GuardianPause ---
    function test_guardian_veto_flag() public {
        Guardian g = new Guardian(acl);
        acl.bootstrap(acl.GUARDIAN_ROLE(), address(this));
        bytes32 op = keccak256("op");
        assertFalse(g.isVetoed(op));
        g.veto(op);
        assertTrue(g.isVetoed(op));
    }

    function test_guardian_pause_toggle() public {
        GuardianPause gp = new GuardianPause(acl);
        acl.bootstrap(acl.GUARDIAN_ROLE(), address(this));
        assertFalse(gp.paused());
        gp.pause();
        assertTrue(gp.paused());
        gp.unpause();
        assertFalse(gp.paused());
    }

    function test_guardian_pause_only_guardian() public {
        GuardianPause gp = new GuardianPause(acl);
        vm.prank(alice);
        vm.expectRevert(GuardianPause.NotGuardian.selector);
        gp.pause();
    }
}
