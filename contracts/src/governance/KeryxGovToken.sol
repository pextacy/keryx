// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IVotes} from "../interfaces/IVotes.sol";
import {IERC20} from "../interfaces/IERC20.sol";
import {AccessController} from "../access/AccessController.sol";

/// @title KeryxGovToken
/// @notice ERC20 governance token (KRX) with delegation and historical vote checkpoints.
contract KeryxGovToken is IERC20, IVotes {
    /// @notice Role registry consulted for minter/governor authorization.
    AccessController public immutable acl;

    /// @notice ERC20 token name.
    string public constant name = "Keryx";
    /// @notice ERC20 token symbol.
    string public constant symbol = "KRX";
    /// @notice ERC20 token decimals.
    uint8 public constant decimals = 18;

    /// @notice Total amount of KRX in existence.
    uint256 public totalSupply;
    /// @notice Token balance of each account.
    mapping(address => uint256) public balanceOf;
    /// @notice Spending allowance from owner to spender.
    mapping(address => mapping(address => uint256)) public allowance;

    /// @dev Address each account currently delegates its voting power to.
    mapping(address => address) internal _delegates;

    /// @dev A snapshot of accumulated votes at a given block.
    struct Checkpoint {
        uint32 fromBlock;
        uint224 votes;
    }

    /// @dev Per-delegate ordered list of vote checkpoints.
    mapping(address => Checkpoint[]) internal _checkpoints;
    /// @dev Ordered list of total-supply checkpoints.
    Checkpoint[] internal _totalSupplyCheckpoints;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event DelegateChanged(address indexed delegator, address indexed from, address indexed to);
    event DelegateVotesChanged(address indexed delegate, uint256 previous, uint256 current);

    error NotMinter();
    error InsufficientBalance();
    error InsufficientAllowance();
    error FutureLookup();

    /// @notice Wires the token to the suite-wide access controller.
    /// @param acl_ Deployed AccessController used for authorization checks.
    constructor(AccessController acl_) {
        acl = acl_;
    }

    /// @dev Reverts unless the caller holds the GOVERNOR_ROLE (the suite's minter authority).
    modifier onlyMinter() {
        if (!acl.hasRole(acl.GOVERNOR_ROLE(), msg.sender)) revert NotMinter();
        _;
    }

    /// @notice Transfers `amount` tokens from the caller to `to`.
    function transfer(address to, uint256 amount) external returns (bool) {
        _transfer(msg.sender, to, amount);
        return true;
    }

    /// @notice Transfers `amount` tokens from `from` to `to` using the caller's allowance.
    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        uint256 allowed = allowance[from][msg.sender];
        if (allowed != type(uint256).max) {
            if (allowed < amount) revert InsufficientAllowance();
            unchecked {
                allowance[from][msg.sender] = allowed - amount;
            }
            emit Approval(from, msg.sender, allowed - amount);
        }
        _transfer(from, to, amount);
        return true;
    }

    /// @notice Sets the caller's allowance for `spender` to `amount`.
    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    /// @notice Mints `amount` new tokens to `to`. Restricted to the minter (GOVERNOR_ROLE).
    function mint(address to, uint256 amount) external onlyMinter {
        totalSupply += amount;
        unchecked {
            balanceOf[to] += amount;
        }
        _writeCheckpoint(_totalSupplyCheckpoints, _add, totalSupply - amount, amount);
        emit Transfer(address(0), to, amount);
        _moveVotingPower(address(0), _delegates[to], amount);
    }

    /// @notice Burns `amount` tokens from `from`. Restricted to the minter (GOVERNOR_ROLE).
    function burn(address from, uint256 amount) external onlyMinter {
        uint256 bal = balanceOf[from];
        if (bal < amount) revert InsufficientBalance();
        unchecked {
            balanceOf[from] = bal - amount;
            totalSupply -= amount;
        }
        _writeCheckpoint(_totalSupplyCheckpoints, _subtract, totalSupply + amount, amount);
        emit Transfer(from, address(0), amount);
        _moveVotingPower(_delegates[from], address(0), amount);
    }

    /// @notice Delegates the caller's voting power to `delegatee`.
    function delegate(address delegatee) external {
        _delegate(msg.sender, delegatee);
    }

    /// @notice Returns the account `account` currently delegates to.
    function delegates(address account) external view returns (address) {
        return _delegates[account];
    }

    /// @notice Returns the current voting power of `account`.
    function getVotes(address account) external view returns (uint256) {
        uint256 n = _checkpoints[account].length;
        return n == 0 ? 0 : _checkpoints[account][n - 1].votes;
    }

    /// @notice Returns the voting power of `account` at the end of `blockNumber`.
    function getPastVotes(address account, uint256 blockNumber) external view returns (uint256) {
        if (blockNumber >= block.number) revert FutureLookup();
        return _checkpointsLookup(_checkpoints[account], blockNumber);
    }

    /// @notice Returns the total supply at the end of `blockNumber`.
    function getPastTotalSupply(uint256 blockNumber) external view returns (uint256) {
        if (blockNumber >= block.number) revert FutureLookup();
        return _checkpointsLookup(_totalSupplyCheckpoints, blockNumber);
    }

    /// @dev Moves tokens between accounts, applying checks-effects and shifting voting power.
    function _transfer(address from, address to, uint256 amount) internal {
        uint256 bal = balanceOf[from];
        if (bal < amount) revert InsufficientBalance();
        unchecked {
            balanceOf[from] = bal - amount;
            balanceOf[to] += amount;
        }
        emit Transfer(from, to, amount);
        _moveVotingPower(_delegates[from], _delegates[to], amount);
    }

    /// @dev Repoints `delegator`'s delegation and migrates the associated voting power.
    function _delegate(address delegator, address delegatee) internal {
        address current = _delegates[delegator];
        _delegates[delegator] = delegatee;
        emit DelegateChanged(delegator, current, delegatee);
        _moveVotingPower(current, delegatee, balanceOf[delegator]);
    }

    /// @dev Decrements the source delegate and increments the destination delegate checkpoints.
    function _moveVotingPower(address from, address to, uint256 amount) internal {
        if (from == to || amount == 0) return;
        if (from != address(0)) {
            Checkpoint[] storage ckpts = _checkpoints[from];
            uint256 n = ckpts.length;
            uint256 old = n == 0 ? 0 : ckpts[n - 1].votes;
            uint256 newVotes = _writeCheckpoint(ckpts, _subtract, old, amount);
            emit DelegateVotesChanged(from, old, newVotes);
        }
        if (to != address(0)) {
            Checkpoint[] storage ckpts = _checkpoints[to];
            uint256 n = ckpts.length;
            uint256 old = n == 0 ? 0 : ckpts[n - 1].votes;
            uint256 newVotes = _writeCheckpoint(ckpts, _add, old, amount);
            emit DelegateVotesChanged(to, old, newVotes);
        }
    }

    /// @dev Appends or overwrites the latest checkpoint with `op(old, delta)`.
    function _writeCheckpoint(
        Checkpoint[] storage ckpts,
        function(uint256, uint256) view returns (uint256) op,
        uint256 oldValue,
        uint256 delta
    ) internal returns (uint256 newValue) {
        newValue = op(oldValue, delta);
        uint256 n = ckpts.length;
        if (n > 0 && ckpts[n - 1].fromBlock == uint32(block.number)) {
            ckpts[n - 1].votes = uint224(newValue);
        } else {
            ckpts.push(Checkpoint({fromBlock: uint32(block.number), votes: uint224(newValue)}));
        }
    }

    /// @dev Binary-searches `ckpts` for the value in force at the end of `blockNumber`.
    function _checkpointsLookup(Checkpoint[] storage ckpts, uint256 blockNumber)
        internal
        view
        returns (uint256)
    {
        uint256 high = ckpts.length;
        uint256 low = 0;
        while (low < high) {
            uint256 mid = (low + high) >> 1;
            if (ckpts[mid].fromBlock > blockNumber) {
                high = mid;
            } else {
                low = mid + 1;
            }
        }
        return high == 0 ? 0 : ckpts[high - 1].votes;
    }

    /// @dev Saturating-free addition helper for checkpoint math.
    function _add(uint256 a, uint256 b) internal pure returns (uint256) {
        return a + b;
    }

    /// @dev Subtraction helper for checkpoint math.
    function _subtract(uint256 a, uint256 b) internal pure returns (uint256) {
        return a - b;
    }
}
