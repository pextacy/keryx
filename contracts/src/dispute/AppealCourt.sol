// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {DisputeManager} from "./DisputeManager.sol";
import {IERC20} from "../interfaces/IERC20.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title AppealCourt
/// @notice Higher-bond appeal layer that can overturn an arbitration-panel verdict
///         before a dispute reaches final resolution. A party posts an appeal bond
///         that is strictly larger than the original challenge bond to escalate a
///         dispute into the appeal phase; a chief arbitrator then rules, either
///         upholding the panel verdict (forfeiting the bond to this contract) or
///         overturning it (flipping the recorded outcome and refunding the bond).
///         The court drives the underlying DisputeManager's appeal/resolution
///         lifecycle so the verdict and its escalation stay in lockstep.
contract AppealCourt is ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice Role registry consulted for governor and chief-arbitrator authorization.
    AccessController public immutable acl;

    /// @notice The dispute ledger this court escalates and resolves.
    DisputeManager public immutable disputes;

    /// @notice ERC-20 token in which appeal bonds are posted (and refunded).
    IERC20 public immutable bondToken;

    /// @notice Role permitted to rule on lodged appeals.
    /// @dev Anchored under the access controller's role hierarchy externally; this
    ///      court only reads membership, never mutates it.
    bytes32 public constant CHIEF_ARBITRATOR_ROLE = keccak256("CHIEF_ARBITRATOR_ROLE");

    /// @notice Bond an appellant must post to lodge an appeal.
    uint256 public appealBond;

    /// @notice Per-dispute appeal record.
    struct Appeal {
        address appellant;
        uint256 bond;
        bool ruledOverturn;
        bool finalized;
    }

    /// @dev Dispute id => appeal record. A zero `appellant` means no appeal lodged.
    mapping(uint256 => Appeal) internal _appeals;

    /// @notice Emitted when an appellant escalates a dispute into the appeal phase.
    event AppealLodged(uint256 indexed disputeId, address indexed appellant, uint256 bond);
    /// @notice Emitted when the chief arbitrator rules on a lodged appeal.
    event AppealRuled(uint256 indexed disputeId, bool overturned);
    /// @notice Emitted when the required appeal bond is updated.
    event AppealBondSet(uint256 amount);

    error NotGovernor();
    error NotChiefArbitrator();
    error AlreadyAppealed();
    error UnknownAppeal();

    /// @notice Restricts a call to holders of the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Restricts a call to holders of the CHIEF_ARBITRATOR_ROLE.
    modifier onlyChiefArbitrator() {
        if (!acl.hasRole(CHIEF_ARBITRATOR_ROLE, msg.sender)) revert NotChiefArbitrator();
        _;
    }

    /// @notice Wires the court to its dependencies and sets the initial appeal bond.
    /// @param acl_ The access controller used for authorization decisions.
    /// @param disputes_ The dispute manager whose verdicts may be appealed.
    /// @param bondToken_ The ERC-20 token bonds are posted and refunded in.
    /// @param appealBond_ The initial bond required to lodge an appeal.
    constructor(
        AccessController acl_,
        DisputeManager disputes_,
        IERC20 bondToken_,
        uint256 appealBond_
    ) {
        acl = acl_;
        disputes = disputes_;
        bondToken = bondToken_;
        appealBond = appealBond_;
        emit AppealBondSet(appealBond_);
    }

    /// @notice Updates the bond required to lodge future appeals.
    /// @dev Restricted to the governor. Does not affect appeals already lodged,
    ///      whose bonds are snapshotted at lodge time.
    /// @param amount The new appeal bond amount.
    function setAppealBond(uint256 amount) external onlyGovernor {
        appealBond = amount;
        emit AppealBondSet(amount);
    }

    /// @notice Escalates a dispute into the appeal phase by posting the appeal bond.
    /// @dev Any account may lodge an appeal exactly once per dispute. Pulls the bond
    ///      from the caller and advances the dispute via `openAppeal`, which itself
    ///      enforces that the dispute is in the correct (post-arbitration) phase.
    ///      Checks-effects-interactions: state is written before the bond transfer,
    ///      and the call is reentrancy-guarded.
    /// @param disputeId The dispute being appealed.
    function lodgeAppeal(uint256 disputeId) external nonReentrant {
        Appeal storage appeal = _appeals[disputeId];
        if (appeal.appellant != address(0)) revert AlreadyAppealed();

        uint256 bond = appealBond;

        // Effects: record the appeal before moving value or touching other contracts.
        appeal.appellant = msg.sender;
        appeal.bond = bond;

        // Interaction: advance the underlying dispute into its appeal phase. Reverts
        // if the dispute is unknown or not in a state that permits appeal.
        disputes.openAppeal(disputeId);

        // Interaction: pull the appeal bond from the appellant into the court's custody.
        if (bond != 0) {
            bondToken.safeTransferFrom(msg.sender, address(this), bond);
        }

        emit AppealLodged(disputeId, msg.sender, bond);
    }

    /// @notice Rules on a lodged appeal, optionally overturning the panel verdict.
    /// @dev Restricted to the chief arbitrator. When `overturn` is true the appeal
    ///      succeeds: the bond is refunded to the appellant and the dispute is
    ///      resolved with the verdict flipped. When false the verdict stands and the
    ///      bond is forfeited to the court. Resolution is delegated to the dispute
    ///      manager, which performs the final, irreversible state transition.
    ///      Checks-effects-interactions: the appeal is finalized before any transfer.
    /// @param disputeId The appealed dispute to rule on.
    /// @param overturn Whether to overturn (true) or uphold (false) the panel verdict.
    function ruleAppeal(uint256 disputeId, bool overturn) external nonReentrant onlyChiefArbitrator {
        Appeal storage appeal = _appeals[disputeId];
        address appellant = appeal.appellant;
        if (appellant == address(0) || appeal.finalized) revert UnknownAppeal();

        uint256 bond = appeal.bond;

        // Effects: freeze the appeal before any external interaction.
        appeal.ruledOverturn = overturn;
        appeal.finalized = true;

        // Determine the final outcome by reading the panel verdict and flipping it
        // when the appeal overturns the decision.
        DisputeManager.Dispute memory d = disputes.getDispute(disputeId);
        bool finalUpheld = overturn ? !d.upheld : d.upheld;

        // Interaction: commit the final verdict on the dispute ledger.
        disputes.resolve(disputeId, finalUpheld);

        // Interaction: a successful appeal refunds the bond; a failed appeal forfeits
        // it to the court for downstream governance disposition.
        if (overturn && bond != 0) {
            bondToken.safeTransfer(appellant, bond);
        }

        emit AppealRuled(disputeId, overturn);
    }

    /// @notice Reads the appeal record for a dispute.
    /// @param disputeId The dispute whose appeal record to read.
    /// @return The stored appeal (zero `appellant` if none was ever lodged).
    function getAppeal(uint256 disputeId) external view returns (Appeal memory) {
        return _appeals[disputeId];
    }
}
