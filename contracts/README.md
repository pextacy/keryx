# Keryx on-chain layer (Foundry)

The optional on-chain layer for Keryx: a verifiable, ERC-8004-inspired attribution +
reputation stack that complements the Circle Gateway settlement path. Settlement of the
USDC itself still clears through **Circle Gateway** (a pre-deployed contract on Arc —
Keryx does not reimplement it). These contracts add the *attribution* layer the PRD calls
the moat, on-chain: who is a cited author, what answer cited them, how much they earned,
and the reputation that accrues from it.

> **Why a handful of contracts, not hundreds.** Every author/identity lives as a row in
> **one** `IdentityRegistry` (a mapping), the correct EVM pattern — `test_identity_scales_to_200_authors`
> proves 200 authors in a single contract. Deploying one contract per author/citation would
> be an anti-pattern (200× gas, no benefit). The suite is sized by *responsibility*, not count.

## Contracts (`src/`)

| Contract | Role |
| --- | --- |
| `KeryxToll` | On-chain settlement economics — owner-tunable mirror of `shared/config.py` (floor, $0.001–$0.01 band, T=0.5). Nothing hardcoded in logic. |
| `IdentityRegistry` | ERC-8004-inspired identity: each author/agent → one `agentId` + wallet + metadata. Self-sovereign `register()` + owner `registerFor()` seeding. |
| `ReputationRegistry` | ERC-8004-inspired reputation: settled citations accrue weighted feedback (`gBps`) to an author. Authorized-writer only. |
| `ValidationRegistry` | ERC-8004-inspired validation: request/respond soundness checks on a citation, completing the identity+reputation+validation triad. |
| `CitationRegistry` | Signed-attestation log — EIP-712 verify of the agent signature, replay-guarded by digest. The on-chain audit trail behind every payment. |
| `CitationSplitter` | Moves USDC to cited authors: per-citation `distribute` and weighted `splitWeighted` (the recursive/weighted-split innovation). |
| `KeryxSettlement` | Orchestrator: verify attestation → gate each citation on `g ≥ T` + registered author → pay the toll → accrue reputation, in one call. Enforces *pay-on-citation* (g < T reverts). |

Libraries: `GroundingMath` (g→amount, the gate, split weights), `AttestationLib` (EIP-712),
`CitationLib` (citation struct + commitment). Plus `auth/Owned`, `interfaces/`, and
`mocks/MockUSDC` (tests only).

## Build & test

```bash
cd contracts
forge install foundry-rs/forge-std --no-git   # one-time
forge build
forge test -vvv                               # 18 tests
```

## Deploy (Arc testnet)

```bash
PRIVATE_KEY=0x... forge script script/Deploy.s.sol --rpc-url "$RPC" --broadcast
# KERYX_USDC_ADDRESS defaults to Arc testnet USDC (0x3600…0000)
```

Our code is MIT. `lib/forge-std` is MIT (Foundry), pulled via `forge install` and gitignored.
