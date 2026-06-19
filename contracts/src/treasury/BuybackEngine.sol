// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {ITreasury} from "../interfaces/ITreasury.sol";
import {KeryxGovToken} from "../governance/KeryxGovToken.sol";
import {PriceOracle} from "../oracle/PriceOracle.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title BuybackEngine
/// @notice Spends treasury USDC at the oracle price to buy back and burn KRX.
contract BuybackEngine is ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice Role registry consulted for governor authorization.
    AccessController public immutable acl;
    /// @notice Treasury that funds the buyback with USDC.
    ITreasury public immutable treasury;
    /// @notice USDC token spent on buybacks.
    IERC20 public immutable usdc;
    /// @notice KRX governance token bought back and burned.
    KeryxGovToken public immutable krx;
    /// @notice Oracle providing the KRX/USDC price (18 decimals).
    PriceOracle public oracle;
    /// @notice Maximum USDC that may be spent on buybacks within a single epoch window.
    uint256 public maxBuybackPerEpoch;

    /// @notice Tracks cumulative USDC spent during the current epoch window.
    uint256 public spentThisEpoch;
    /// @notice Timestamp at which the current epoch accounting window began.
    uint256 public epochStart;
    /// @notice Length of an epoch window, in seconds.
    uint256 public constant EPOCH_LENGTH = 7 days;

    event Buyback(uint256 usdcSpent, uint256 krxBurned, uint256 price);
    event OracleSet(address oracle);
    event MaxBuybackSet(uint256 maxPerEpoch);

    error NotGovernor();
    error ExceedsEpochLimit();
    error ZeroAmount();

    /// @notice Restricts a call to holders of the governor role.
    modifier onlyGovernor() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotGovernor();
        _;
    }

    /// @notice Wires the engine to its treasury, tokens, oracle and access controller.
    constructor(
        AccessController acl_,
        ITreasury treasury_,
        IERC20 usdc_,
        KeryxGovToken krx_,
        PriceOracle oracle_,
        uint256 maxBuybackPerEpoch_
    ) {
        acl = acl_;
        treasury = treasury_;
        usdc = usdc_;
        krx = krx_;
        oracle = oracle_;
        maxBuybackPerEpoch = maxBuybackPerEpoch_;
        epochStart = block.timestamp;
        emit OracleSet(address(oracle_));
        emit MaxBuybackSet(maxBuybackPerEpoch_);
    }

    /// @notice Updates the price oracle. Governor only.
    function setOracle(PriceOracle oracle_) external onlyGovernor {
        oracle = oracle_;
        emit OracleSet(address(oracle_));
    }

    /// @notice Updates the per-epoch USDC spend cap. Governor only.
    function setMaxBuyback(uint256 maxPerEpoch) external onlyGovernor {
        maxBuybackPerEpoch = maxPerEpoch;
        emit MaxBuybackSet(maxPerEpoch);
    }

    /// @notice Withdraws USDC from the treasury, buys KRX from a seller at the oracle price and burns it.
    /// @param usdcAmount Amount of USDC to spend on the buyback.
    /// @param krxSeller Address that supplies KRX and receives the USDC.
    /// @return krxBought Amount of KRX bought from the seller and burned.
    function executeBuyback(uint256 usdcAmount, address krxSeller)
        external
        nonReentrant
        onlyGovernor
        returns (uint256 krxBought)
    {
        if (usdcAmount == 0) revert ZeroAmount();

        // Checks: roll the epoch window forward and enforce the spend cap.
        if (block.timestamp >= epochStart + EPOCH_LENGTH) {
            epochStart = block.timestamp;
            spentThisEpoch = 0;
        }
        uint256 newSpent = spentThisEpoch + usdcAmount;
        if (newSpent > maxBuybackPerEpoch) revert ExceedsEpochLimit();

        // Read the oracle price (KRX per-token cost in USDC, 18 decimals).
        uint256 price = oracle.getPrice();
        if (price == 0) revert ZeroAmount();

        // krxBought = usdcAmount / price, scaled by KRX price decimals.
        krxBought = (usdcAmount * (10 ** oracle.PRICE_DECIMALS())) / price;
        if (krxBought == 0) revert ZeroAmount();

        // Effects: record the spend before moving any value.
        spentThisEpoch = newSpent;

        // Interactions: pull USDC from treasury, pay the seller, pull and burn KRX.
        treasury.withdraw(address(usdc), address(this), usdcAmount);
        usdc.safeTransfer(krxSeller, usdcAmount);

        krx.burn(krxSeller, krxBought);

        emit Buyback(usdcAmount, krxBought, price);
    }
}
