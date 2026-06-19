// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";

/// @title TollVault
/// @notice Per-author USDC accrual ledger. Authorized settlement contracts pull
///         toll payments into the vault and credit them to an author's claimable
///         balance, letting authors batch-claim their accumulated tolls in a
///         single withdrawal rather than receiving many tiny transfers.
contract TollVault is ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice The USDC token this vault accrues and pays out.
    IERC20 public immutable usdc;

    /// @notice Unclaimed toll balance accrued to each author.
    mapping(address => uint256) public claimable;

    /// @notice Callers permitted to credit tolls into the vault.
    mapping(address => bool) public authorized;

    /// @notice Administrator able to manage the authorized caller set.
    address public immutable admin;

    /// @notice Emitted when an author's claimable balance is increased.
    event Credited(address indexed author, uint256 amount);

    /// @notice Emitted when an author withdraws their accumulated tolls.
    event Claimed(address indexed author, uint256 amount);

    /// @notice Emitted when an address's authorization status changes.
    event AuthorizedSet(address indexed caller, bool allowed);

    /// @notice Thrown when a non-authorized address attempts to credit.
    error NotAuthorized();
    /// @notice Thrown when a non-admin attempts an admin-only action.
    error NotAdmin();
    /// @notice Thrown when an author with a zero balance attempts to claim.
    error NothingToClaim();

    /// @notice Restricts a function to the configured admin.
    modifier onlyAdmin() {
        if (msg.sender != admin) revert NotAdmin();
        _;
    }

    /// @notice Restricts a function to authorized crediting callers.
    modifier onlyAuthorized() {
        if (!authorized[msg.sender]) revert NotAuthorized();
        _;
    }

    /// @notice Wires the vault to its payout token and administrator.
    /// @param usdc_ The USDC token accrued and paid out by the vault.
    /// @param admin_ The administrator managing the authorized caller set.
    constructor(IERC20 usdc_, address admin_) {
        usdc = usdc_;
        admin = admin_;
    }

    /// @notice Grants or revokes a caller's permission to credit tolls.
    /// @param caller The address whose authorization is being updated.
    /// @param allowed Whether the caller may credit tolls.
    function setAuthorized(address caller, bool allowed) external onlyAdmin {
        authorized[caller] = allowed;
        emit AuthorizedSet(caller, allowed);
    }

    /// @notice Pulls `amount` USDC from `from` and credits it to `author`.
    /// @dev Only authorized callers may credit. The funds are pulled into the
    ///      vault immediately (effects before the external author can claim).
    /// @param from The address the toll payment is pulled from.
    /// @param author The author whose claimable balance is increased.
    /// @param amount The toll amount in USDC atomic units.
    function credit(address from, address author, uint256 amount) external onlyAuthorized nonReentrant {
        // Effects: record the accrual before moving funds in.
        claimable[author] += amount;
        emit Credited(author, amount);

        // Interaction: pull the toll into the vault.
        usdc.safeTransferFrom(from, address(this), amount);
    }

    /// @notice Withdraws the caller's full accumulated toll balance.
    /// @return amount The amount of USDC transferred to the caller.
    function claim() external nonReentrant returns (uint256 amount) {
        amount = claimable[msg.sender];
        if (amount == 0) revert NothingToClaim();

        // Effects: zero the balance before paying out.
        claimable[msg.sender] = 0;
        emit Claimed(msg.sender, amount);

        // Interaction: pay the author.
        usdc.safeTransfer(msg.sender, amount);
    }
}
