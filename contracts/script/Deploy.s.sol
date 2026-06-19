// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Script, console2} from "forge-std/Script.sol";
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

/// @notice Deploys the full Keryx on-chain layer to Arc testnet and wires authorizations.
/// Run: forge script script/Deploy.s.sol --rpc-url $RPC --broadcast
/// Env: PRIVATE_KEY (deployer), KERYX_USDC_ADDRESS (defaults to Arc testnet USDC).
contract Deploy is Script {
    // Arc testnet USDC (6 decimals) — see docs/VERIFIED-SIGNATURES.md.
    address constant ARC_TESTNET_USDC = 0x3600000000000000000000000000000000000000;

    // Economics mirror shared/config.py (USDC atomic units / basis points).
    uint256 constant FLOOR = 1; // $0.000001
    uint256 constant TOLL_MIN = 1_000; // $0.001
    uint256 constant TOLL_MAX = 10_000; // $0.01
    uint16 constant T_BPS = 5_000; // g >= 0.5

    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        address owner = vm.addr(pk);
        address usdc = vm.envOr("KERYX_USDC_ADDRESS", ARC_TESTNET_USDC);

        vm.startBroadcast(pk);

        KeryxToll toll = new KeryxToll(owner, FLOOR, TOLL_MIN, TOLL_MAX, T_BPS);
        IdentityRegistry identity = new IdentityRegistry(owner);
        ReputationRegistry reputation = new ReputationRegistry(owner, IIdentityRegistry(address(identity)));
        ValidationRegistry validation = new ValidationRegistry(owner);
        CitationRegistry citations = new CitationRegistry(owner);
        CitationSplitter splitter = new CitationSplitter(owner);
        KeryxSettlement settlement = new KeryxSettlement(
            owner,
            IERC20(usdc),
            citations,
            IIdentityRegistry(address(identity)),
            IReputationRegistry(address(reputation)),
            splitter,
            toll
        );

        // Only the orchestrator may write the registries / move funds.
        reputation.setAuthorized(address(settlement), true);
        citations.setAuthorized(address(settlement), true);
        splitter.setAuthorized(address(settlement), true);

        vm.stopBroadcast();

        console2.log("KeryxToll          ", address(toll));
        console2.log("IdentityRegistry   ", address(identity));
        console2.log("ReputationRegistry ", address(reputation));
        console2.log("ValidationRegistry ", address(validation));
        console2.log("CitationRegistry   ", address(citations));
        console2.log("CitationSplitter   ", address(splitter));
        console2.log("KeryxSettlement    ", address(settlement));
        console2.log("USDC               ", usdc);
    }
}
