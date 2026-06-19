// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Owned} from "./auth/Owned.sol";

/// @title ValidationRegistry
/// @notice ERC-8004-inspired validation layer. A requester asks an independent validator
///         to attest that a citation/attestation (`dataHash`) is sound; the validator
///         responds with a score in basis points. Completes the ERC-8004 triad
///         (identity + reputation + validation) for Keryx's attribution claims.
contract ValidationRegistry is Owned {
    enum Status {
        None,
        Pending,
        Responded
    }

    struct Request {
        uint256 agentId;
        bytes32 dataHash;
        address requester;
        address validator;
        Status status;
        uint16 responseBps;
    }

    uint256 public totalRequests;
    mapping(uint256 => Request) internal _requests;
    mapping(address => bool) public validators;

    event ValidatorSet(address indexed validator, bool allowed);
    event ValidationRequested(uint256 indexed requestId, uint256 indexed agentId, bytes32 dataHash, address validator);
    event ValidationResponded(uint256 indexed requestId, uint16 responseBps);

    error NotValidator();
    error BadRequest();
    error AlreadyResponded();

    constructor(address owner_) Owned(owner_) {}

    function setValidator(address validator, bool allowed) external onlyOwner {
        validators[validator] = allowed;
        emit ValidatorSet(validator, allowed);
    }

    /// @notice Request validation of `dataHash` for `agentId` by a chosen `validator`.
    function requestValidation(uint256 agentId, bytes32 dataHash, address validator) external returns (uint256 id) {
        if (!validators[validator]) revert NotValidator();
        id = ++totalRequests;
        _requests[id] = Request({
            agentId: agentId,
            dataHash: dataHash,
            requester: msg.sender,
            validator: validator,
            status: Status.Pending,
            responseBps: 0
        });
        emit ValidationRequested(id, agentId, dataHash, validator);
    }

    /// @notice The assigned validator responds with a soundness score (basis points).
    function respondValidation(uint256 requestId, uint16 responseBps) external {
        Request storage r = _requests[requestId];
        if (r.status != Status.Pending) revert BadRequest();
        if (msg.sender != r.validator) revert NotValidator();
        r.status = Status.Responded;
        r.responseBps = responseBps;
        emit ValidationResponded(requestId, responseBps);
    }

    function getRequest(uint256 requestId) external view returns (Request memory) {
        return _requests[requestId];
    }
}
