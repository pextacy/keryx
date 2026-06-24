"""Network registry — the single source of truth for chain-specific constants.

Keryx is **testnet-only** (Lepton hackathon runs on Arc Testnet). Every chain
constant (chain id, RPC, USDC token, Gateway wallet, ERC-8004/8183 registries,
CAIP-2 id, explorer) is resolved here rather than hardcoded across the codebase,
and the same ``KERYX_*`` env vars can override any individual constant. The
TypeScript rail reads the same env vars (see ``rail/m0_spike/network.ts``) so both
sides stay in lock-step.
"""

from __future__ import annotations

from typing import TypedDict


class NetworkConstants(TypedDict):
    """Chain-specific constants for a network preset."""

    arc_chain_id: int
    rpc_url: str
    usdc_address: str
    gateway_wallet: str
    caip2_network: str
    explorer_url: str
    erc8004_identity_registry: str
    erc8004_reputation_registry: str
    erc8004_validation_registry: str
    erc8183_contract: str


# The env-var-overridable chain fields, in the order the resolver fills them.
CHAIN_FIELDS: tuple[str, ...] = (
    "arc_chain_id",
    "rpc_url",
    "usdc_address",
    "gateway_wallet",
    "caip2_network",
    "explorer_url",
    "erc8004_identity_registry",
    "erc8004_reputation_registry",
    "erc8004_validation_registry",
    "erc8183_contract",
)


NETWORKS: dict[str, NetworkConstants] = {
    # Arc Testnet — constants verified vs arc-nanopayments source + live RPC
    # (see docs/VERIFIED-SIGNATURES.md). ERC-8004/8183 from docs.arc.io quickstarts.
    "testnet": {
        "arc_chain_id": 0x4CEF52,  # 5042002
        "rpc_url": "https://rpc.testnet.arc.network",
        "usdc_address": "0x3600000000000000000000000000000000000000",
        "gateway_wallet": "0x0077777d7EBA4688BDeF3E311b846F25870A19B9",
        "caip2_network": "eip155:5042002",
        "explorer_url": "https://testnet.arcscan.app",
        "erc8004_identity_registry": "0x8004A818BFB912233c491871b3d84c89A494BD9e",
        "erc8004_reputation_registry": "0x8004B663056A597Dffe9eCcC1965A193B7388713",
        "erc8004_validation_registry": "0x8004Cb1BF31DAf7788923b405b754f57acEB4272",
        "erc8183_contract": "0x0747EEf0706327138c69792bF28Cd525089e4583",
    },
}


def network_names() -> tuple[str, ...]:
    return tuple(NETWORKS.keys())


def resolve_chain_values(network: str, provided: dict[str, object]) -> dict[str, object]:
    """Return chain-field values for ``network``, honouring explicit ``provided``
    overrides (typically env vars already present on the Settings input).

    Arc Testnet is the only supported network; any other name raises.
    """
    key = network.lower()
    if key not in NETWORKS:
        raise ValueError(
            f"unknown KERYX_NETWORK={network!r}; expected one of {network_names()} "
            f"(Keryx is testnet-only)"
        )
    preset = NETWORKS[key]
    resolved: dict[str, object] = {}
    for field in CHAIN_FIELDS:
        if field in provided and provided[field] not in (None, ""):
            resolved[field] = provided[field]
        else:
            resolved[field] = preset[field]  # type: ignore[literal-required]
    return resolved
