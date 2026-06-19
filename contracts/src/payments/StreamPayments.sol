// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "../interfaces/IERC20.sol";
import {SafeTransferLib} from "../util/SafeTransferLib.sol";
import {ReentrancyGuard} from "../util/ReentrancyGuard.sol";

/// @title StreamPayments
/// @notice Linear-by-time USDC payment streams from a payer (sender) to a
///         source author (recipient). The deposit unlocks to the recipient at a
///         constant rate across [start, stop); either party may cancel
///         mid-stream, paying the recipient what has vested and refunding the
///         remainder to the sender. The deposit is escrowed up front so payouts
///         and refunds are fully funded.
contract StreamPayments is ReentrancyGuard {
    using SafeTransferLib for IERC20;

    /// @notice The USDC token escrowed and paid out by every stream.
    IERC20 public immutable usdc;

    /// @notice A single linear-by-time payment stream.
    /// @dev `deposit` is the total escrowed amount; `withdrawn` tracks how much
    ///      the recipient has already pulled. `start`/`stop` bound the vesting
    ///      window. A stream with `deposit == 0` is treated as nonexistent.
    struct Stream {
        address sender;
        address recipient;
        uint256 deposit;
        uint256 withdrawn;
        uint64 start;
        uint64 stop;
    }

    /// @notice Monotonically increasing counter of streams ever created; also
    ///         the id assigned to the next stream.
    uint256 public totalStreams;

    /// @dev streamId => stream record.
    mapping(uint256 => Stream) internal _streams;

    /// @notice Emitted when a new stream is created and funded.
    event StreamCreated(
        uint256 indexed streamId,
        address indexed sender,
        address indexed recipient,
        uint256 deposit,
        uint64 start,
        uint64 stop
    );

    /// @notice Emitted when the recipient withdraws vested funds from a stream.
    event Withdrawn(uint256 indexed streamId, address indexed recipient, uint256 amount);

    /// @notice Emitted when a stream is cancelled and balances are settled.
    event StreamCancelled(uint256 indexed streamId, uint256 senderRefund, uint256 recipientPaid);

    /// @notice Thrown when `stop` is not strictly after `start`, or `start` is
    ///         in the past.
    error BadTimeRange();
    /// @notice Thrown when the deposit is zero.
    error ZeroDeposit();
    /// @notice Thrown when the caller is neither the sender nor the recipient.
    error NotParty();
    /// @notice Thrown when there is nothing available to withdraw.
    error NothingToWithdraw();
    /// @notice Thrown when the referenced stream does not exist.
    error UnknownStream();

    /// @param usdc_ The USDC token used for all streams.
    constructor(IERC20 usdc_) {
        usdc = usdc_;
    }

    /// @notice Creates and funds a new linear-by-time stream to `recipient`.
    /// @dev Pulls the full `deposit` from the caller up front (checks-effects-
    ///      interactions: state is written before the external pull). The
    ///      caller becomes the stream sender.
    /// @param recipient The author who accrues the stream over time.
    /// @param deposit The total USDC amount to stream.
    /// @param start The unix timestamp at which vesting begins.
    /// @param stop The unix timestamp at which vesting completes.
    /// @return streamId The id of the newly created stream.
    function createStream(address recipient, uint256 deposit, uint64 start, uint64 stop)
        external
        nonReentrant
        returns (uint256 streamId)
    {
        if (recipient == address(0) || recipient == msg.sender) revert NotParty();
        if (deposit == 0) revert ZeroDeposit();
        if (stop <= start || start < block.timestamp) revert BadTimeRange();

        streamId = totalStreams;
        unchecked {
            totalStreams = streamId + 1;
        }

        _streams[streamId] = Stream({
            sender: msg.sender,
            recipient: recipient,
            deposit: deposit,
            withdrawn: 0,
            start: start,
            stop: stop
        });

        emit StreamCreated(streamId, msg.sender, recipient, deposit, start, stop);

        usdc.safeTransferFrom(msg.sender, address(this), deposit);
    }

    /// @notice Returns the current claimable balance of a party for a stream.
    /// @dev For the recipient this is the vested-but-not-yet-withdrawn amount;
    ///      for the sender it is the not-yet-vested remainder. Any other address
    ///      returns zero.
    /// @param streamId The stream to query.
    /// @param who The party whose balance is requested.
    /// @return The claimable balance owed to `who`.
    function balanceOfStream(uint256 streamId, address who) external view returns (uint256) {
        Stream storage s = _streams[streamId];
        if (s.deposit == 0) revert UnknownStream();

        uint256 vested = _vestedAmount(s);

        if (who == s.recipient) {
            return vested - s.withdrawn;
        }
        if (who == s.sender) {
            return s.deposit - vested;
        }
        return 0;
    }

    /// @notice Withdraws up to the vested-but-unwithdrawn amount of a stream to
    ///         the recipient.
    /// @dev Only the recipient may withdraw. Follows checks-effects-interactions:
    ///      `withdrawn` is increased before the token transfer.
    /// @param streamId The stream to withdraw from.
    /// @param amount The amount to withdraw; must not exceed the available balance.
    function withdrawFromStream(uint256 streamId, uint256 amount) external nonReentrant {
        Stream storage s = _streams[streamId];
        if (s.deposit == 0) revert UnknownStream();
        if (msg.sender != s.recipient) revert NotParty();

        uint256 available = _vestedAmount(s) - s.withdrawn;
        if (amount == 0 || amount > available) revert NothingToWithdraw();

        s.withdrawn += amount;

        // If the stream is fully drained, clear it to free storage.
        if (s.withdrawn == s.deposit) {
            address recipient = s.recipient;
            delete _streams[streamId];
            emit Withdrawn(streamId, recipient, amount);
            usdc.safeTransfer(recipient, amount);
            return;
        }

        emit Withdrawn(streamId, s.recipient, amount);
        usdc.safeTransfer(s.recipient, amount);
    }

    /// @notice Cancels a stream, paying the recipient any vested-unwithdrawn
    ///         amount and refunding the unvested remainder to the sender.
    /// @dev Either the sender or the recipient may cancel. The stream is deleted
    ///      before any transfers (effects before interactions).
    /// @param streamId The stream to cancel.
    function cancelStream(uint256 streamId) external nonReentrant {
        Stream storage s = _streams[streamId];
        if (s.deposit == 0) revert UnknownStream();
        if (msg.sender != s.sender && msg.sender != s.recipient) revert NotParty();

        uint256 vested = _vestedAmount(s);
        uint256 recipientPaid = vested - s.withdrawn;
        uint256 senderRefund = s.deposit - vested;

        address sender = s.sender;
        address recipient = s.recipient;

        delete _streams[streamId];

        emit StreamCancelled(streamId, senderRefund, recipientPaid);

        if (recipientPaid != 0) {
            usdc.safeTransfer(recipient, recipientPaid);
        }
        if (senderRefund != 0) {
            usdc.safeTransfer(sender, senderRefund);
        }
    }

    /// @notice Returns the full record for a stream.
    /// @param streamId The stream to fetch.
    /// @return The stored Stream struct.
    function getStream(uint256 streamId) external view returns (Stream memory) {
        Stream memory s = _streams[streamId];
        if (s.deposit == 0) revert UnknownStream();
        return s;
    }

    /// @dev Computes the amount of a stream's deposit that has vested as of the
    ///      current block timestamp, prorated linearly across [start, stop).
    ///      Returns 0 before start and the full deposit at/after stop. The final
    ///      whole second is paid out as the remainder so that vesting at `stop`
    ///      exactly equals the deposit without rounding loss.
    /// @param s The stream to evaluate.
    /// @return The vested amount.
    function _vestedAmount(Stream storage s) internal view returns (uint256) {
        if (block.timestamp <= s.start) {
            return 0;
        }
        if (block.timestamp >= s.stop) {
            return s.deposit;
        }
        uint256 elapsed = block.timestamp - s.start;
        uint256 duration = uint256(s.stop) - s.start;
        return (s.deposit * elapsed) / duration;
    }
}
