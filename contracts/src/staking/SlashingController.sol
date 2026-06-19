// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {StakingVault} from "./StakingVault.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title SlashingController
/// @notice Translates resolved disputes into bounded slashing calls against the
///         StakingVault. A SLASHER_ROLE caller (typically the DisputeResolver)
///         requests a slash amount; this controller clamps it to a governed
///         basis-points fraction of the offender's current stake before
///         forwarding the call to the vault and routing the seized stake to the
///         insurance fund.
contract SlashingController {
    /// @notice Maximum representable basis points (100%).
    uint16 internal constant MAX_BPS = 10_000;

    /// @notice The staking vault whose balances are slashed.
    StakingVault public immutable vault;
    /// @notice Role registry consulted for slasher and governor authorization.
    AccessController public immutable acl;

    /// @notice Beneficiary that receives slashed stake (the insurance fund).
    address public insuranceFund;
    /// @notice Upper bound, in basis points of the offender's stake, on any single slash.
    uint16 public maxSlashBps;

    /// @notice Emitted when a slash is executed against an offender.
    /// @param offender The account whose stake was slashed.
    /// @param amount The actual amount of stake seized.
    /// @param caseId The dispute/case identifier that justified the slash.
    event SlashExecuted(address indexed offender, uint256 amount, bytes32 indexed caseId);
    /// @notice Emitted when the maximum slash fraction is updated.
    event MaxSlashBpsSet(uint16 bps);
    /// @notice Emitted when the insurance fund beneficiary is updated.
    event InsuranceFundSet(address fund);

    /// @notice Thrown when the caller lacks the SLASHER_ROLE.
    error NotSlasher();
    /// @notice Thrown when the caller lacks the GOVERNOR_ROLE.
    error NotGovernor();
    /// @notice Thrown when a configured bound exceeds 100% (10_000 bps).
    error SlashTooLarge();

    /// @notice Restricts a function to holders of the SLASHER_ROLE.
    modifier onlySlasher() {
        if (!acl.hasRole(acl.SLASHER_ROLE(), msg.sender)) revert NotSlasher();
        _;
    }

    /// @notice Restricts a function to holders of the GOVERNOR_ROLE.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the controller to its vault, ACL, insurance fund and slash cap.
    /// @param vault_ The staking vault to slash against.
    /// @param acl_ The access controller used for authorization.
    /// @param insuranceFund_ The beneficiary receiving slashed stake.
    /// @param maxSlashBps_ The maximum slash as basis points of current stake.
    constructor(
        StakingVault vault_,
        AccessController acl_,
        address insuranceFund_,
        uint16 maxSlashBps_
    ) {
        if (maxSlashBps_ > MAX_BPS) revert SlashTooLarge();

        vault = vault_;
        acl = acl_;
        insuranceFund = insuranceFund_;
        maxSlashBps = maxSlashBps_;

        emit InsuranceFundSet(insuranceFund_);
        emit MaxSlashBpsSet(maxSlashBps_);
    }

    /// @notice Updates the maximum slash fraction, in basis points.
    /// @dev Governor-only. Reverts if the new bound exceeds 100%.
    /// @param bps The new maximum slash fraction (<= 10_000).
    function setMaxSlashBps(uint16 bps) external onlyGovernor {
        if (bps > MAX_BPS) revert SlashTooLarge();
        maxSlashBps = bps;
        emit MaxSlashBpsSet(bps);
    }

    /// @notice Updates the insurance fund that receives slashed stake.
    /// @dev Governor-only.
    /// @param fund The new beneficiary address.
    function setInsuranceFund(address fund) external onlyGovernor {
        insuranceFund = fund;
        emit InsuranceFundSet(fund);
    }

    /// @notice Slashes an offender's stake, bounded by the governed bps cap.
    /// @dev Slasher-only. The requested amount is clamped to
    ///      `stake * maxSlashBps / 10_000` before being forwarded to the vault,
    ///      which itself clamps to the available stake and returns the actual
    ///      amount seized. Follows checks-effects-interactions: all local reads
    ///      precede the single external call, and the event is emitted with the
    ///      vault-reported result.
    /// @param offender The account to slash.
    /// @param amount The requested slash amount in KRX atomic units.
    /// @param caseId The dispute/case identifier justifying the slash.
    /// @return slashed The actual amount of stake seized by the vault.
    function slash(
        address offender,
        uint256 amount,
        bytes32 caseId
    ) external onlySlasher returns (uint256 slashed) {
        // Compute the bounded cap as a fraction of the offender's current stake.
        uint256 stake = vault.stakeOf(offender);
        uint256 cap = (stake * maxSlashBps) / MAX_BPS;

        uint256 toSlash = amount > cap ? cap : amount;

        // Interaction: the vault clamps to available stake and reports the
        // actual amount transferred to the insurance fund beneficiary.
        slashed = vault.slash(offender, toSlash, insuranceFund);

        emit SlashExecuted(offender, slashed, caseId);
    }
}
