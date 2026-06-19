// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title DisputeManager
/// @notice Files disputes against citations/attestations with a bonded challenge
///         and tracks each case through its phase lifecycle. The challenger posts
///         a configurable bond in `bondToken` at filing; the bond is forwarded to
///         the defendant when the dispute fails (challenge not upheld) and returned
///         to the challenger when it succeeds (challenge upheld). Phase transitions
///         are gated to governor (filing config) and arbitrator (adjudication) roles
///         queried from the shared AccessController.
contract DisputeManager is ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice Shared role registry consulted for governor/arbitrator authorization.
    AccessController public immutable acl;

    /// @notice ERC20 token in which challenge bonds are posted.
    IERC20 public immutable bondToken;

    /// @notice Role permitted to adjudicate disputes (advance arbitration, resolve, appeal).
    bytes32 public constant ARBITRATOR_ROLE = keccak256("ARBITRATOR_ROLE");

    /// @notice Bond amount, in `bondToken` atomic units, required to file a dispute.
    uint256 public bondAmount;

    /// @notice Lifecycle phases a dispute moves through.
    enum Phase {
        None,
        Open,
        Arbitration,
        Appeal,
        Resolved
    }

    /// @notice On-chain record of a single dispute.
    struct Dispute {
        address challenger;
        address defendant;
        bytes32 dataHash;
        uint256 bond;
        Phase phase;
        bool upheld;
        uint64 openedAt;
    }

    /// @notice Monotonic count of disputes ever filed; also the next dispute id.
    uint256 public totalDisputes;

    /// @notice disputeId => dispute record.
    mapping(uint256 => Dispute) internal _disputes;

    /// @notice Emitted when a new dispute is filed and its bond is escrowed.
    event DisputeFiled(
        uint256 indexed disputeId,
        address indexed challenger,
        address indexed defendant,
        bytes32 dataHash,
        uint256 bond
    );
    /// @notice Emitted on every phase transition of a dispute.
    event PhaseAdvanced(uint256 indexed disputeId, Phase phase);
    /// @notice Emitted when a dispute is resolved with its final outcome.
    event DisputeResolved(uint256 indexed disputeId, bool upheld);
    /// @notice Emitted when the governor updates the filing bond amount.
    event BondAmountSet(uint256 amount);

    /// @notice Thrown when a governor-only function is called by a non-governor.
    error NotGovernor();
    /// @notice Thrown when an arbitrator-only function is called by a non-arbitrator.
    error NotArbitrator();
    /// @notice Thrown when an action is attempted from an incompatible phase.
    error WrongPhase();
    /// @notice Thrown when referencing a dispute id that was never filed.
    error UnknownDispute();

    /// @notice Reverts unless the caller holds the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Reverts unless the caller holds the ARBITRATOR_ROLE.
    modifier onlyArbitrator() {
        if (!acl.hasRole(ARBITRATOR_ROLE, msg.sender)) revert NotArbitrator();
        _;
    }

    /// @notice Wires the dispute manager to its role registry and bond token.
    /// @param acl_ The shared AccessController role registry.
    /// @param bondToken_ The ERC20 token used for challenge bonds.
    /// @param bondAmount_ The initial bond required to file a dispute.
    constructor(AccessController acl_, IERC20 bondToken_, uint256 bondAmount_) {
        acl = acl_;
        bondToken = bondToken_;
        bondAmount = bondAmount_;
        emit BondAmountSet(bondAmount_);
    }

    /// @notice Updates the bond required to file new disputes.
    /// @dev Governor-only. Does not affect bonds already escrowed on open disputes.
    /// @param amount The new filing bond, in bond-token atomic units.
    function setBondAmount(uint256 amount) external onlyGovernor {
        bondAmount = amount;
        emit BondAmountSet(amount);
    }

    /// @notice Files a new dispute against `defendant` over `dataHash`, escrowing the bond.
    /// @dev Pulls `bondAmount` of `bondToken` from the caller. Follows checks-effects-
    ///      interactions: state is written before the external token transfer.
    /// @param defendant The party whose citation/attestation is being challenged.
    /// @param dataHash The identifier of the disputed citation/attestation data.
    /// @return disputeId The id assigned to the newly filed dispute.
    function fileDispute(address defendant, bytes32 dataHash)
        external
        nonReentrant
        returns (uint256 disputeId)
    {
        uint256 bond = bondAmount;

        disputeId = ++totalDisputes;
        _disputes[disputeId] = Dispute({
            challenger: msg.sender,
            defendant: defendant,
            dataHash: dataHash,
            bond: bond,
            phase: Phase.Open,
            upheld: false,
            openedAt: uint64(block.timestamp)
        });

        emit DisputeFiled(disputeId, msg.sender, defendant, dataHash, bond);
        emit PhaseAdvanced(disputeId, Phase.Open);

        if (bond != 0) {
            bondToken.safeTransferFrom(msg.sender, address(this), bond);
        }
    }

    /// @notice Advances an open dispute into the arbitration phase.
    /// @dev Arbitrator-only. Requires the dispute to currently be in `Open`.
    /// @param disputeId The dispute to advance.
    function moveToArbitration(uint256 disputeId) external onlyArbitrator {
        Dispute storage d = _disputes[disputeId];
        if (d.phase == Phase.None) revert UnknownDispute();
        if (d.phase != Phase.Open) revert WrongPhase();

        d.phase = Phase.Arbitration;
        emit PhaseAdvanced(disputeId, Phase.Arbitration);
    }

    /// @notice Resolves a dispute, settling the escrowed bond per the outcome.
    /// @dev Arbitrator-only. Permitted from the `Arbitration` or `Appeal` phase. When
    ///      `upheld` is true the challenge succeeds and the bond returns to the
    ///      challenger; otherwise the bond is forwarded to the defendant. State is
    ///      finalized before the token transfer (checks-effects-interactions).
    /// @param disputeId The dispute to resolve.
    /// @param upheld True if the challenge is upheld (citation/attestation invalid).
    function resolve(uint256 disputeId, bool upheld) external nonReentrant onlyArbitrator {
        Dispute storage d = _disputes[disputeId];
        if (d.phase == Phase.None) revert UnknownDispute();
        if (d.phase != Phase.Arbitration && d.phase != Phase.Appeal) revert WrongPhase();

        uint256 bond = d.bond;
        address bondRecipient = upheld ? d.challenger : d.defendant;

        d.upheld = upheld;
        d.bond = 0;
        d.phase = Phase.Resolved;

        emit PhaseAdvanced(disputeId, Phase.Resolved);
        emit DisputeResolved(disputeId, upheld);

        if (bond != 0) {
            bondToken.safeTransfer(bondRecipient, bond);
        }
    }

    /// @notice Opens an appeal on a dispute currently under arbitration.
    /// @dev Arbitrator-only. Moves the dispute from `Arbitration` to `Appeal` so a
    ///      higher-bond appeal layer can re-adjudicate before final resolution.
    /// @param disputeId The dispute to move into appeal.
    function openAppeal(uint256 disputeId) external onlyArbitrator {
        Dispute storage d = _disputes[disputeId];
        if (d.phase == Phase.None) revert UnknownDispute();
        if (d.phase != Phase.Arbitration) revert WrongPhase();

        d.phase = Phase.Appeal;
        emit PhaseAdvanced(disputeId, Phase.Appeal);
    }

    /// @notice Returns the full record for a dispute.
    /// @param disputeId The dispute to read.
    /// @return The stored Dispute struct.
    function getDispute(uint256 disputeId) external view returns (Dispute memory) {
        Dispute memory d = _disputes[disputeId];
        if (d.phase == Phase.None) revert UnknownDispute();
        return d;
    }
}
