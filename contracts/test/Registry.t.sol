// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {AccessController} from "../src/access/AccessController.sol";
import {IdentityRegistry} from "../src/IdentityRegistry.sol";
import {IIdentityRegistry} from "../src/interfaces/IIdentityRegistry.sol";
import {SourceRegistry} from "../src/registry/SourceRegistry.sol";
import {AgentKeyRegistry} from "../src/registry/AgentKeyRegistry.sol";
import {LicenseRegistry} from "../src/registry/LicenseRegistry.sol";
import {CategoryRegistry} from "../src/registry/CategoryRegistry.sol";
import {Allowlist} from "../src/registry/Allowlist.sol";
import {MetadataResolver} from "../src/registry/MetadataResolver.sol";

contract RegistryTest is Test {
    AccessController acl;
    IdentityRegistry identity;
    uint256 agentId;

    address alice = address(0xA11CE);
    address bob = address(0xB0B);
    address carol = address(0xCC);
    bytes32 constant SRC = keccak256("source-1");

    function setUp() public {
        acl = new AccessController(address(this));
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(this));
        identity = new IdentityRegistry(address(this));
        agentId = identity.registerFor(alice, "ipfs://alice"); // agentId 1
    }

    function test_source_registry_crud() public {
        SourceRegistry sources = new SourceRegistry(address(this), IIdentityRegistry(address(identity)));
        sources.registerSource(SRC, agentId, "ipfs://src", keccak256("content"));

        assertTrue(sources.isActive(SRC));
        assertEq(sources.getSource(SRC).ownerAgentId, agentId);

        sources.setActive(SRC, false);
        assertFalse(sources.isActive(SRC));
    }

    function test_source_registry_unknown_agent_reverts() public {
        SourceRegistry sources = new SourceRegistry(address(this), IIdentityRegistry(address(identity)));
        vm.expectRevert(SourceRegistry.UnknownAgent.selector);
        sources.registerSource(SRC, 999, "ipfs://x", bytes32(0));
    }

    function test_agent_key_registry_rotation() public {
        AgentKeyRegistry keys = new AgentKeyRegistry(address(this), IIdentityRegistry(address(identity)));
        address k1 = address(0xCAFE1);

        // Owner (this) may manage the agent's keys.
        keys.addKey(agentId, k1);
        assertTrue(keys.isActiveKey(agentId, k1));
        assertEq(keys.primaryKey(agentId), k1, "first key bootstraps primary");

        keys.revokeKey(agentId, k1);
        assertFalse(keys.isActiveKey(agentId, k1));
    }

    function test_agent_key_registry_authorization() public {
        AgentKeyRegistry keys = new AgentKeyRegistry(address(this), IIdentityRegistry(address(identity)));
        vm.prank(bob); // bob is neither the agent wallet (alice) nor owner
        vm.expectRevert(AgentKeyRegistry.NotAgentOwner.selector);
        keys.addKey(agentId, address(0xBEEF));
    }

    function test_license_registry_binds_to_source() public {
        SourceRegistry sources = new SourceRegistry(address(this), IIdentityRegistry(address(identity)));
        sources.registerSource(SRC, agentId, "ipfs://src", keccak256("c"));

        LicenseRegistry licenses = new LicenseRegistry(address(this), sources);
        licenses.setLicense(SRC, true, false, 1000, "ipfs://terms");
        assertEq(licenses.minToll(SRC), 1000);
        assertTrue(licenses.getLicense(SRC).commercialAllowed);
        assertFalse(licenses.getLicense(SRC).derivativesAllowed);
    }

    function test_license_registry_unknown_source_reverts() public {
        SourceRegistry sources = new SourceRegistry(address(this), IIdentityRegistry(address(identity)));
        LicenseRegistry licenses = new LicenseRegistry(address(this), sources);
        vm.expectRevert(LicenseRegistry.UnknownSource.selector);
        licenses.setLicense(SRC, true, true, 1, "x");
    }

    function test_category_registry_taxonomy() public {
        CategoryRegistry cats = new CategoryRegistry(address(this));
        bytes32 root = keccak256("tech");
        bytes32 child = keccak256("tech/ai");

        cats.createCategory(root, bytes32(0), "Tech");
        cats.createCategory(child, root, "AI");
        cats.assignCategory(SRC, child);
        assertEq(cats.categoryOfSource(SRC), child);

        // Unknown parent rejected.
        vm.expectRevert(CategoryRegistry.UnknownCategory.selector);
        cats.createCategory(keccak256("orphan"), keccak256("missing"), "Orphan");
    }

    function test_allowlist_explicit_and_deny_override() public {
        Allowlist al = new Allowlist(acl);
        al.setAllowed(alice, true);
        assertTrue(al.isAllowed(alice));

        al.setDenied(alice, true);
        assertFalse(al.isAllowed(alice), "deny overrides allow");
    }

    function test_allowlist_merkle_mode() public {
        Allowlist al = new Allowlist(acl);
        bytes32 leafBob = keccak256(abi.encodePacked(bob));
        bytes32 leafCarol = keccak256(abi.encodePacked(carol));
        bytes32 root = leafBob < leafCarol
            ? keccak256(abi.encodePacked(leafBob, leafCarol))
            : keccak256(abi.encodePacked(leafCarol, leafBob));
        al.setMerkleRoot(root, true);

        bytes32[] memory proof = new bytes32[](1);
        proof[0] = leafCarol;
        assertTrue(al.isAllowedWithProof(bob, proof));

        bytes32[] memory empty = new bytes32[](0);
        assertFalse(al.isAllowedWithProof(address(0xDEAD), empty), "no proof, not allowlisted");
    }

    function test_metadata_resolver() public {
        MetadataResolver mr = new MetadataResolver(address(this));
        bytes32 key = keccak256("agent:1:feed");
        mr.setRecord(key, "https://example.com/feed");
        assertEq(mr.resolve(key), "https://example.com/feed");

        vm.prank(bob);
        vm.expectRevert(MetadataResolver.NotAuthorized.selector);
        mr.setRecord(key, "evil");
    }
}
