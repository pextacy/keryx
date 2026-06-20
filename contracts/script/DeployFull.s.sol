// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Script, console2} from "forge-std/Script.sol";

// --- Existing Keryx core ---
import {KeryxToll} from "../src/KeryxToll.sol";
import {IdentityRegistry} from "../src/IdentityRegistry.sol";
import {ReputationRegistry} from "../src/ReputationRegistry.sol";
import {ValidationRegistry} from "../src/ValidationRegistry.sol";
import {CitationRegistry} from "../src/CitationRegistry.sol";
import {CitationSplitter} from "../src/CitationSplitter.sol";
import {KeryxSettlement} from "../src/KeryxSettlement.sol";

// --- Interfaces ---
import {IERC20} from "../src/interfaces/IERC20.sol";
import {IIdentityRegistry} from "../src/interfaces/IIdentityRegistry.sol";
import {IReputationRegistry} from "../src/interfaces/IReputationRegistry.sol";
import {IVotes} from "../src/interfaces/IVotes.sol";
import {ITreasury} from "../src/interfaces/ITreasury.sol";
import {IStakeView} from "../src/interfaces/IStakeView.sol";
import {IGroundingConsensus} from "../src/interfaces/IGroundingConsensus.sol";

// --- access ---
import {AccessController} from "../src/access/AccessController.sol";
import {CircuitBreaker} from "../src/access/CircuitBreaker.sol";
import {Guardian} from "../src/access/Guardian.sol";
import {GuardianPause} from "../src/access/GuardianPause.sol";
import {Timelock} from "../src/access/Timelock.sol";
import {MultiSigWallet} from "../src/access/MultiSigWallet.sol";

// --- governance ---
import {KeryxGovToken} from "../src/governance/KeryxGovToken.sol";
import {VoteEscrow} from "../src/governance/VoteEscrow.sol";
import {GovernanceParams} from "../src/governance/GovernanceParams.sol";
import {KeryxGovernor} from "../src/governance/KeryxGovernor.sol";
import {EmergencyVeto} from "../src/governance/EmergencyVeto.sol";

// --- oracle ---
import {PriceOracle} from "../src/oracle/PriceOracle.sol";
import {TWAPOracle} from "../src/oracle/TWAPOracle.sol";
import {GroundingAttestor} from "../src/oracle/GroundingAttestor.sol";
import {OracleAggregator} from "../src/oracle/OracleAggregator.sol";

// --- treasury ---
import {Treasury} from "../src/treasury/Treasury.sol";
import {FeeManager} from "../src/treasury/FeeManager.sol";
import {InsuranceFund} from "../src/treasury/InsuranceFund.sol";
import {RevenueSplitter} from "../src/treasury/RevenueSplitter.sol";
import {BuybackEngine} from "../src/treasury/BuybackEngine.sol";

// --- staking ---
import {StakingVault} from "../src/staking/StakingVault.sol";
import {SlashingController} from "../src/staking/SlashingController.sol";
import {SourceBond} from "../src/staking/SourceBond.sol";
import {RewardDistributor} from "../src/staking/RewardDistributor.sol";
import {ValidatorBondManager} from "../src/staking/ValidatorBondManager.sol";

// --- registry ---
import {SourceRegistry} from "../src/registry/SourceRegistry.sol";
import {LicenseRegistry} from "../src/registry/LicenseRegistry.sol";
import {CategoryRegistry} from "../src/registry/CategoryRegistry.sol";
import {AgentKeyRegistry} from "../src/registry/AgentKeyRegistry.sol";
import {Allowlist} from "../src/registry/Allowlist.sol";
import {MetadataResolver} from "../src/registry/MetadataResolver.sol";

// --- dispute ---
import {DisputeManager} from "../src/dispute/DisputeManager.sol";
import {EvidenceRegistry} from "../src/dispute/EvidenceRegistry.sol";
import {ArbitrationPanel} from "../src/dispute/ArbitrationPanel.sol";
import {AppealCourt} from "../src/dispute/AppealCourt.sol";
import {DisputeResolver} from "../src/dispute/DisputeResolver.sol";

// --- distribution ---
import {Airdrop} from "../src/distribution/Airdrop.sol";
import {MerkleDistributor} from "../src/distribution/MerkleDistributor.sol";
import {EmissionSchedule} from "../src/distribution/EmissionSchedule.sol";
import {RewardClaimGate} from "../src/distribution/RewardClaimGate.sol";
import {SourceGauge} from "../src/distribution/SourceGauge.sol";

// --- payments ---
import {PaymentEscrow} from "../src/payments/PaymentEscrow.sol";
import {StreamPayments} from "../src/payments/StreamPayments.sol";
import {SubscriptionManager} from "../src/payments/SubscriptionManager.sol";
import {TokenVesting} from "../src/payments/TokenVesting.sol";
import {TollVault} from "../src/payments/TollVault.sol";
import {SettlementRouter} from "../src/payments/SettlementRouter.sol";

// --- proxy & util ---
import {ProxyAdmin} from "../src/proxy/ProxyAdmin.sol";
import {EpochClock} from "../src/util/EpochClock.sol";
import {NonceManager} from "../src/util/NonceManager.sol";
import {RateLimiter} from "../src/util/RateLimiter.sol";
import {SweepGuard} from "../src/util/SweepGuard.sol";

/// @notice Deploys the FULL Keryx on-chain protocol — the original citation-settlement
///         core plus the governance, staking, treasury, oracle, registry, dispute,
///         distribution and payments modules — in dependency order, then bootstraps the
///         cross-contract roles so the system is wired and operable on a fresh chain.
/// @dev    Deployed instances are held in storage (not stack locals) to stay within the
///         EVM stack limit, and `run()` is split into ordered phases. Abstract bases
///         (Pausable/Roles/Initializable/UUPSUpgradeable/Multicall/ReentrancyGuard) and
///         pure libraries (BondingCurve/MedianLib/AddressSetLib/MerkleProofLib/
///         SafeTransferLib) are inlined, not deployed. The generic proxy wrappers
///         (ERC1967Proxy/BeaconProxy/UpgradeableBeacon) are per-target upgrade
///         infrastructure instantiated against a specific implementation, so they are not
///         part of this singleton wiring; only the standalone ProxyAdmin is deployed.
///
/// Run: PRIVATE_KEY=0x... forge script script/DeployFull.s.sol --rpc-url $RPC --broadcast
contract DeployFull is Script {
    // Arc testnet USDC (6 decimals).
    address constant ARC_TESTNET_USDC = 0x3600000000000000000000000000000000000000;

    // --- Economics mirror shared/config.py (USDC atomic units / basis points). ---
    uint256 constant FLOOR = 1; // $0.000001
    uint256 constant TOLL_MIN = 1_000; // $0.001
    uint256 constant TOLL_MAX = 10_000; // $0.01
    uint16 constant T_BPS = 5_000; // g >= 0.5

    // --- Module parameters (sane testnet defaults; tune via governance post-deploy). ---
    uint256 constant TIMELOCK_MIN_DELAY = 2 days;
    uint256 constant VOTING_DELAY = 1;
    uint256 constant VOTING_PERIOD = 50_400; // ~1 week at 12s blocks
    uint256 constant PROPOSAL_THRESHOLD = 0;
    uint256 constant QUORUM_VOTES = 1_000e18;
    uint256 constant PRICE_MAX_STALENESS = 1 hours;
    uint256 constant PRICE_SEED = 1e8; // nominal KRX/USDC seed price for TWAP bootstrap
    uint256 constant GROUNDING_QUORUM = 1;
    uint256 constant ORACLE_MIN_REPORTERS = 1;
    uint16 constant PROTOCOL_FEE_BPS = 500; // 5%
    uint256 constant INSURANCE_CAP = type(uint256).max;
    uint256 constant UNBONDING_PERIOD = 7 days;
    uint16 constant MAX_SLASH_BPS = 5_000; // 50%
    uint256 constant BOND_SLOPE = 1e12;
    uint256 constant BOND_BASE = 1e15;
    uint256 constant MIN_VALIDATOR_BOND = 1_000e18;
    uint256 constant DISPUTE_BOND = 100e18;
    uint256 constant ARBITRATION_THRESHOLD = 3;
    uint256 constant APPEAL_BOND = 200e18;
    uint256 constant DISPUTE_SLASH = 500e18;
    uint256 constant EPOCH_LENGTH = 7 days;
    uint256 constant EMISSION_PER_EPOCH = 10_000e18;
    uint16 constant EMISSION_DECAY_BPS = 9_900; // 1% decay/epoch
    uint256 constant CLAIM_MIN_AVG_BPS = 5_000;
    uint256 constant CLAIM_MIN_CITATIONS = 1;

    // --- Deployment context ---
    address internal deployer;
    address internal usdc;

    // --- Core ---
    AccessController public acl;
    KeryxToll public toll;
    IdentityRegistry public identity;
    ReputationRegistry public reputation;
    ValidationRegistry public validation;
    CitationRegistry public citations;
    CitationSplitter public splitter;
    KeryxSettlement public settlement;

    // --- access ---
    CircuitBreaker public breaker;
    Guardian public guardian;
    GuardianPause public guardianPause;
    Timelock public timelock;
    MultiSigWallet public multisig;

    // --- governance ---
    KeryxGovToken public krx;
    VoteEscrow public ve;
    GovernanceParams public govParams;
    KeryxGovernor public governor;
    EmergencyVeto public veto;

    // --- oracle ---
    PriceOracle public priceOracle;
    TWAPOracle public twap;
    GroundingAttestor public attestor;
    OracleAggregator public aggregator;

    // --- treasury ---
    Treasury public treasury;
    FeeManager public feeManager;
    InsuranceFund public insurance;
    RevenueSplitter public revenue;
    BuybackEngine public buyback;

    // --- staking ---
    StakingVault public vault;
    SlashingController public slasher;
    SourceBond public sourceBond;
    RewardDistributor public rewards;
    ValidatorBondManager public validators;

    // --- registry ---
    SourceRegistry public sources;
    LicenseRegistry public licenses;
    CategoryRegistry public categories;
    AgentKeyRegistry public agentKeys;
    Allowlist public allowlist;
    MetadataResolver public metadata;

    // --- dispute ---
    DisputeManager public disputes;
    EvidenceRegistry public evidence;
    ArbitrationPanel public panel;
    AppealCourt public appeals;
    DisputeResolver public resolver;

    // --- distribution ---
    Airdrop public airdrop;
    MerkleDistributor public merkle;
    EmissionSchedule public emissions;
    RewardClaimGate public claimGate;
    SourceGauge public gauge;

    // --- payments ---
    PaymentEscrow public escrow;
    StreamPayments public streams;
    SubscriptionManager public subs;
    TokenVesting public vesting;
    TollVault public tollVault;
    SettlementRouter public router;

    // --- proxy & util ---
    ProxyAdmin public proxyAdmin;
    EpochClock public clock;
    NonceManager public nonces;
    RateLimiter public limiter;
    SweepGuard public sweep;

    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        deployer = vm.addr(pk);
        usdc = vm.envOr("KERYX_USDC_ADDRESS", ARC_TESTNET_USDC);

        vm.startBroadcast(pk);
        _deployCore();
        _deployAccessAndGovernance();
        _deployOracleAndTreasury();
        _deployStakingAndRegistry();
        _deployDisputeAndDistribution();
        _deployPaymentsAndUtil();
        _wireRoles();
        vm.stopBroadcast();

        _log();
    }

    function _deployCore() internal {
        acl = new AccessController(deployer);
        toll = new KeryxToll(deployer, FLOOR, TOLL_MIN, TOLL_MAX, T_BPS);
        identity = new IdentityRegistry(deployer);
        reputation = new ReputationRegistry(deployer, IIdentityRegistry(address(identity)));
        validation = new ValidationRegistry(deployer);
        citations = new CitationRegistry(deployer);
        splitter = new CitationSplitter(deployer);
        settlement = new KeryxSettlement(
            deployer,
            IERC20(usdc),
            citations,
            IIdentityRegistry(address(identity)),
            IReputationRegistry(address(reputation)),
            splitter,
            toll
        );
        reputation.setAuthorized(address(settlement), true);
        citations.setAuthorized(address(settlement), true);
        splitter.setAuthorized(address(settlement), true);
    }

    function _deployAccessAndGovernance() internal {
        breaker = new CircuitBreaker(acl);
        guardian = new Guardian(acl);
        guardianPause = new GuardianPause(acl);
        timelock = new Timelock(acl, guardian, TIMELOCK_MIN_DELAY);
        address[] memory signers = new address[](1);
        signers[0] = deployer;
        multisig = new MultiSigWallet(signers, 1);

        krx = new KeryxGovToken(acl);
        ve = new VoteEscrow(IERC20(address(krx)));
        govParams = new GovernanceParams(acl);
        governor = new KeryxGovernor(
            IVotes(address(ve)), timelock, VOTING_DELAY, VOTING_PERIOD, PROPOSAL_THRESHOLD, QUORUM_VOTES
        );
        veto = new EmergencyVeto(acl, governor);
    }

    function _deployOracleAndTreasury() internal {
        priceOracle = new PriceOracle(acl, PRICE_MAX_STALENESS);
        // TWAPOracle reads spot.getPrice() in its constructor, so the spot oracle must
        // already hold a fresh price. Grant the deployer ORACLE_ROLE and seed one.
        acl.bootstrap(acl.ORACLE_ROLE(), deployer);
        priceOracle.pushPrice(PRICE_SEED);
        twap = new TWAPOracle(acl, priceOracle);
        attestor = new GroundingAttestor(acl, GROUNDING_QUORUM);
        aggregator = new OracleAggregator(acl, ORACLE_MIN_REPORTERS);

        treasury = new Treasury(acl, breaker);
        feeManager = new FeeManager(acl, ITreasury(address(treasury)), address(treasury), PROTOCOL_FEE_BPS);
        insurance = new InsuranceFund(acl, IERC20(usdc), INSURANCE_CAP);
        revenue = new RevenueSplitter(acl);
        buyback = new BuybackEngine(acl, ITreasury(address(treasury)), IERC20(usdc), krx, priceOracle, EMISSION_PER_EPOCH);
    }

    function _deployStakingAndRegistry() internal {
        vault = new StakingVault(IERC20(address(krx)), acl, UNBONDING_PERIOD);
        slasher = new SlashingController(vault, acl, address(insurance), MAX_SLASH_BPS);
        sourceBond = new SourceBond(IERC20(address(krx)), acl, BOND_SLOPE, BOND_BASE);
        rewards = new RewardDistributor(IERC20(address(krx)), IStakeView(address(vault)), acl);
        validators = new ValidatorBondManager(vault, acl, MIN_VALIDATOR_BOND);

        sources = new SourceRegistry(deployer, IIdentityRegistry(address(identity)));
        licenses = new LicenseRegistry(deployer, sources);
        categories = new CategoryRegistry(deployer);
        agentKeys = new AgentKeyRegistry(deployer, IIdentityRegistry(address(identity)));
        allowlist = new Allowlist(acl);
        metadata = new MetadataResolver(deployer);
    }

    function _deployDisputeAndDistribution() internal {
        disputes = new DisputeManager(acl, IERC20(address(krx)), DISPUTE_BOND);
        evidence = new EvidenceRegistry(disputes);
        panel = new ArbitrationPanel(acl, disputes, ARBITRATION_THRESHOLD);
        appeals = new AppealCourt(acl, disputes, IERC20(address(krx)), APPEAL_BOND);
        resolver = new DisputeResolver(acl, disputes, slasher, IGroundingConsensus(address(attestor)), DISPUTE_SLASH);

        airdrop = new Airdrop(acl, IERC20(address(krx)));
        merkle = new MerkleDistributor(acl, IERC20(address(krx)));
        emissions = new EmissionSchedule(acl, krx, address(rewards), EPOCH_LENGTH, EMISSION_PER_EPOCH, EMISSION_DECAY_BPS);
        claimGate = new RewardClaimGate(
            IReputationRegistry(address(reputation)),
            IIdentityRegistry(address(identity)),
            acl,
            CLAIM_MIN_AVG_BPS,
            CLAIM_MIN_CITATIONS
        );
        gauge = new SourceGauge(IVotes(address(ve)), acl);
    }

    function _deployPaymentsAndUtil() internal {
        escrow = new PaymentEscrow(acl, IERC20(usdc));
        streams = new StreamPayments(IERC20(usdc));
        subs = new SubscriptionManager(IERC20(usdc));
        vesting = new TokenVesting(acl, IERC20(address(krx)));
        tollVault = new TollVault(IERC20(usdc), deployer);
        router = new SettlementRouter(acl, settlement, feeManager, breaker, usdc);

        proxyAdmin = new ProxyAdmin(acl);
        clock = new EpochClock(acl, block.timestamp, EPOCH_LENGTH);
        nonces = new NonceManager(deployer);
        limiter = new RateLimiter(deployer);
        sweep = new SweepGuard(acl);
    }

    /// @dev Deployer retains DEFAULT_ADMIN_ROLE (from the AccessController ctor) and may
    ///      re-administer any of these grants. Roles below reflect the intended operating
    ///      wiring of the suite.
    function _wireRoles() internal {
        acl.bootstrap(acl.GOVERNOR_ROLE(), deployer); // deploy-time config + ops
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(timelock)); // on-chain governance executor
        acl.bootstrap(acl.GUARDIAN_ROLE(), deployer);
        acl.bootstrap(acl.GUARDIAN_ROLE(), address(guardian));
        acl.bootstrap(acl.GUARDIAN_ROLE(), address(veto)); // emergency veto -> governor.cancel
        acl.bootstrap(acl.ORACLE_ROLE(), deployer); // price + grounding reporter
        acl.bootstrap(acl.SETTLER_ROLE(), address(router)); // batch settlement router
        acl.bootstrap(acl.SLASHER_ROLE(), address(slasher)); // slasher -> vault.slash
        acl.bootstrap(acl.SLASHER_ROLE(), address(resolver)); // resolver -> slasher

        // --- Cross-contract operational authorizations ---
        // Without these the router/treasury/emissions/buyback/dispute paths revert at
        // runtime even though every contract is deployed; grant them so the suite runs.

        // Router + Treasury register their USDC outflow against the circuit breaker.
        // (setAuthorized is guardian-gated; deployer holds GUARDIAN_ROLE from above.)
        breaker.setAuthorized(address(router), true);
        breaker.setAuthorized(address(treasury), true);
        // The router skims the protocol fee through the FeeManager (governor-gated).
        feeManager.setAuthorized(address(router), true);

        // Emission schedule mints KRX; buyback engine burns KRX and pulls treasury USDC.
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(emissions));
        acl.bootstrap(acl.GOVERNOR_ROLE(), address(buyback));

        // Dispute resolution: the panel and appeal court drive DisputeManager.resolve/
        // openAppeal (arbitrator-gated), and the deployer acts as the human arbitrator/
        // chief arbitrator that advances and finalizes the lifecycle on a fresh chain.
        bytes32 arbitratorRole = disputes.ARBITRATOR_ROLE();
        acl.bootstrap(arbitratorRole, address(panel));
        acl.bootstrap(arbitratorRole, address(appeals));
        acl.bootstrap(arbitratorRole, deployer);
        acl.bootstrap(appeals.CHIEF_ARBITRATOR_ROLE(), deployer);
    }

    function _log() internal view {
        console2.log("AccessController   ", address(acl));
        console2.log("KeryxSettlement    ", address(settlement));
        console2.log("Timelock           ", address(timelock));
        console2.log("KeryxGovernor      ", address(governor));
        console2.log("KeryxGovToken      ", address(krx));
        console2.log("VoteEscrow         ", address(ve));
        console2.log("Treasury           ", address(treasury));
        console2.log("StakingVault       ", address(vault));
        console2.log("SlashingController ", address(slasher));
        console2.log("DisputeManager     ", address(disputes));
        console2.log("DisputeResolver    ", address(resolver));
        console2.log("GroundingAttestor  ", address(attestor));
        console2.log("SettlementRouter   ", address(router));
        console2.log("EmissionSchedule   ", address(emissions));
        console2.log("USDC               ", usdc);
    }
}
