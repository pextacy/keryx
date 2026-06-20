// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {AccessController} from "../src/access/AccessController.sol";
import {ERC1967Proxy} from "../src/proxy/ERC1967Proxy.sol";
import {UUPSUpgradeable} from "../src/proxy/UUPSUpgradeable.sol";
import {BeaconProxy} from "../src/proxy/BeaconProxy.sol";
import {UpgradeableBeacon} from "../src/proxy/UpgradeableBeacon.sol";
import {ProxyAdmin} from "../src/proxy/ProxyAdmin.sol";

contract LogicV1 {
    uint256 public x;

    function setX(uint256 v) external {
        x = v;
    }

    function version() external pure returns (uint256) {
        return 1;
    }
}

contract LogicV2 {
    uint256 public x;

    function setX(uint256 v) external {
        x = v;
    }

    function version() external pure returns (uint256) {
        return 2;
    }
}

interface ILogic {
    function setX(uint256 v) external;
    function x() external view returns (uint256);
    function version() external view returns (uint256);
}

contract UUPSLogic is UUPSUpgradeable {
    address public owner;
    bool private _initialized;

    function init(address owner_) external {
        require(!_initialized, "init");
        _initialized = true;
        owner = owner_;
    }

    function _authorizeUpgrade(address) internal view override {
        if (msg.sender != owner) revert UpgradeUnauthorized();
    }
}

contract ProxyTest is Test {
    AccessController acl;
    address alice = address(0xA11CE);

    function setUp() public {
        acl = new AccessController(address(this));
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(this));
    }

    function test_erc1967_delegates_and_preserves_storage_on_upgrade() public {
        LogicV1 v1 = new LogicV1();
        ERC1967Proxy proxy = new ERC1967Proxy(address(v1), address(this), "");
        ILogic p = ILogic(address(proxy));

        p.setX(5);
        assertEq(p.x(), 5);
        assertEq(p.version(), 1);

        LogicV2 v2 = new LogicV2();
        proxy.upgradeTo(address(v2)); // admin == this
        assertEq(p.version(), 2, "now running V2");
        assertEq(p.x(), 5, "proxy storage preserved across upgrade");
    }

    function test_erc1967_upgrade_only_admin() public {
        LogicV1 v1 = new LogicV1();
        ERC1967Proxy proxy = new ERC1967Proxy(address(v1), address(this), "");
        LogicV2 v2 = new LogicV2();
        vm.prank(alice);
        vm.expectRevert(ERC1967Proxy.NotAdmin.selector);
        proxy.upgradeTo(address(v2));
    }

    function test_beacon_upgrades_all_proxies_at_once() public {
        LogicV1 v1 = new LogicV1();
        UpgradeableBeacon beacon = new UpgradeableBeacon(acl, address(v1));
        BeaconProxy bp = new BeaconProxy(address(beacon), "");
        ILogic p = ILogic(address(bp));

        p.setX(7);
        assertEq(p.version(), 1);

        LogicV2 v2 = new LogicV2();
        beacon.upgradeTo(address(v2)); // governor
        assertEq(p.version(), 2, "beacon proxy follows the beacon");
        assertEq(p.x(), 7, "storage preserved");
    }

    function test_beacon_upgrade_only_governor() public {
        LogicV1 v1 = new LogicV1();
        UpgradeableBeacon beacon = new UpgradeableBeacon(acl, address(v1));
        LogicV2 v2 = new LogicV2();
        vm.prank(alice);
        vm.expectRevert(UpgradeableBeacon.NotGovernor.selector);
        beacon.upgradeTo(address(v2));
    }

    function test_proxy_admin_upgrades_proxy() public {
        ProxyAdmin pa = new ProxyAdmin(acl);
        LogicV1 v1 = new LogicV1();
        ERC1967Proxy proxy = new ERC1967Proxy(address(v1), address(pa), "");
        LogicV2 v2 = new LogicV2();

        pa.upgrade(proxy, address(v2)); // governor -> proxy admin == pa
        assertEq(ILogic(address(proxy)).version(), 2);
        assertEq(pa.getProxyImplementation(proxy), address(v2));
    }

    function test_uups_authorize_and_proxiable() public {
        UUPSLogic logic = new UUPSLogic();
        logic.init(address(this));
        LogicV2 v2 = new LogicV2();

        // Non-owner cannot upgrade.
        vm.prank(alice);
        vm.expectRevert(UUPSUpgradeable.UpgradeUnauthorized.selector);
        logic.upgradeTo(address(v2));

        // Owner can; and the EIP-1822 proxiable slot is exposed.
        logic.upgradeTo(address(v2));
        assertEq(
            logic.proxiableUUID(),
            0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc
        );
    }
}
