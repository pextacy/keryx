// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {ITreasury} from "../interfaces/ITreasury.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title FeeManager
/// @notice Skims a protocol fee in basis points off settled tolls and forwards
///         it to the treasury, returning the net amount due to the source author.
contract FeeManager {
    using SafeTransferLib for IERC20;

    /// @notice Role registry consulted for governor authorization decisions.
    AccessController public immutable acl;

    /// @notice Treasury that receives skimmed protocol fees.
    ITreasury public immutable treasury;

    /// @notice Recipient address recorded for off-chain accounting of fees.
    address public feeRecipient;

    /// @notice Protocol fee charged on gross tolls, expressed in basis points.
    uint16 public protocolFeeBps;

    /// @notice Basis-point denominator (100% == 10000 bps).
    uint16 public constant MAX_BPS = 10000;

    /// @notice Contracts allowed to invoke fee collection (e.g. settlement router).
    mapping(address => bool) public authorized;

    event FeeBpsSet(uint16 bps);
    event FeeRecipientSet(address recipient);
    event FeeCollected(address indexed token, uint256 grossAmount, uint256 feeAmount);
    event AuthorizedSet(address indexed caller, bool allowed);

    error NotGovernor();
    error NotAuthorized();
    error FeeTooHigh();

    /// @notice Restricts a call to accounts holding the governor role.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Restricts a call to authorized fee-collection callers.
    modifier onlyAuthorized() {
        if (!authorized[msg.sender]) revert NotAuthorized();
        _;
    }

    /// @notice Wires the access controller, treasury, fee recipient, and initial fee.
    /// @param acl_ The deployed AccessController instance.
    /// @param treasury_ The treasury that receives skimmed fees.
    /// @param feeRecipient_ The recorded fee recipient address.
    /// @param protocolFeeBps_ The initial protocol fee in basis points.
    constructor(
        AccessController acl_,
        ITreasury treasury_,
        address feeRecipient_,
        uint16 protocolFeeBps_
    ) {
        if (protocolFeeBps_ > MAX_BPS) revert FeeTooHigh();

        acl = acl_;
        treasury = treasury_;
        feeRecipient = feeRecipient_;
        protocolFeeBps = protocolFeeBps_;

        emit FeeRecipientSet(feeRecipient_);
        emit FeeBpsSet(protocolFeeBps_);
    }

    /// @notice Updates the protocol fee charged on gross tolls.
    /// @param bps The new fee in basis points; must not exceed MAX_BPS.
    function setProtocolFeeBps(uint16 bps) external onlyGovernor {
        if (bps > MAX_BPS) revert FeeTooHigh();
        protocolFeeBps = bps;
        emit FeeBpsSet(bps);
    }

    /// @notice Updates the recorded fee recipient address.
    /// @param recipient The new fee recipient.
    function setFeeRecipient(address recipient) external onlyGovernor {
        feeRecipient = recipient;
        emit FeeRecipientSet(recipient);
    }

    /// @notice Grants or revokes the right to invoke fee collection.
    /// @param caller The contract or account whose authorization is being set.
    /// @param allowed Whether the caller may collect fees.
    function setAuthorized(address caller, bool allowed) external onlyGovernor {
        authorized[caller] = allowed;
        emit AuthorizedSet(caller, allowed);
    }

    /// @notice Computes the fee and net split for a gross toll without moving funds.
    /// @param gross The gross toll amount.
    /// @return fee The protocol fee skimmed from `gross`.
    /// @return net The remainder payable to the source author.
    function quoteFee(uint256 gross) external view returns (uint256 fee, uint256 net) {
        fee = (gross * protocolFeeBps) / MAX_BPS;
        net = gross - fee;
    }

    /// @notice Pulls the fee portion of a gross toll from `from` and forwards it to
    ///         the treasury, returning the computed fee and net amounts.
    /// @dev Follows checks-effects-interactions: state-free computation, then an
    ///      external pull into this contract, then a forward into the treasury.
    ///      The caller is responsible for routing the `net` remainder to the author.
    /// @param token The ERC-20 token the toll is denominated in.
    /// @param from The account the fee is pulled from.
    /// @param gross The gross toll amount used to derive the fee.
    /// @return fee The protocol fee collected and forwarded to the treasury.
    /// @return net The remainder of `gross` left for the source author.
    function collectFee(IERC20 token, address from, uint256 gross)
        external
        onlyAuthorized
        returns (uint256 fee, uint256 net)
    {
        fee = (gross * protocolFeeBps) / MAX_BPS;
        net = gross - fee;

        if (fee > 0) {
            // Pull the fee into this contract, approve the treasury, and deposit.
            token.safeTransferFrom(from, address(this), fee);
            token.safeApprove(address(treasury), fee);
            treasury.deposit(address(token), fee);
        }

        emit FeeCollected(address(token), gross, fee);
    }
}
