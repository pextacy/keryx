"""Network registry — the single source of truth for chain-specific constants.

Keryx is network-parametric: every chain constant (chain id, RPC, USDC token,
Gateway wallet, ERC-8004/8183 registries, CAIP-2 id, explorer) is resolved from a
named network rather than hardcoded. Select with ``KERYX_NETWORK`` (default
``testnet``). The same ``KERYX_*`` env vars override any individual constant on
either network, and the TypeScript rail reads the same env vars (see
``rail/m0_spike/network.ts``) so both sides stay in lock-step.

Safety: the hackathon is **testnet-only** (see docs/phases.md). The ``mainnet``
preset is intentionally empty — its constants are ``None`` — so selecting it
without supplying *verified* Circle/Arc mainnet addresses fails loud instead of
silently reusing a testnet address and risking real funds on the wrong contract.
"""

from __future__ import annotations

from typing import TypedDict


class NetworkConstants(TypedDict):
    """Chain-specific constants. ``None`` means "no verified preset — must be set
    via the matching ``KERYX_*`` env var before this network can be used."""

    arc_chain_id: int | None
    rpc_url: str | None
    usdc_address: str | None
    gateway_wallet: str | None
    caip2_network: str | None
    explorer_url: str | None
    erc8004_identity_registry: str | None
    erc8004_reputation_registry: str | None
    erc8004_validation_registry: str | None
    erc8183_contract: str | None


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
    # Arc Mainnet — DELIBERATELY EMPTY. Fill each value with a constant verified
    # against Circle/Arc's official mainnet docs (or supply via KERYX_* env vars).
    # Until then, KERYX_NETWORK=mainnet raises rather than running on placeholders.
    "mainnet": {
        "arc_chain_id": None,
        "rpc_url": None,
        "usdc_address": None,
        "gateway_wallet": None,
        "caip2_network": None,
        "explorer_url": None,
        "erc8004_identity_registry": None,
        "erc8004_reputation_registry": None,
        "erc8004_validation_registry": None,
        "erc8183_contract": None,
    },
}


def network_names() -> tuple[str, ...]:
    return tuple(NETWORKS.keys())


def resolve_chain_values(network: str, provided: dict[str, object]) -> dict[str, object]:
    """Return chain-field values for ``network``, honouring explicit ``provided``
    overrides (typically env vars already present on the Settings input).

    For each chain field not explicitly provided: use the network preset if it is
    non-``None``; otherwise raise — a network with no verified preset for a field
    must have that field supplied via its ``KERYX_*`` env var. This is what makes
    ``mainnet`` fail loud instead of silently inheriting testnet defaults.
    """
    key = network.lower()
    if key not in NETWORKS:
        raise ValueError(f"unknown KERYX_NETWORK={network!r}; expected one of {network_names()}")
    preset = NETWORKS[key]
    resolved: dict[str, object] = {}
    missing: list[str] = []
    for field in CHAIN_FIELDS:
        if field in provided and provided[field] not in (None, ""):
            resolved[field] = provided[field]
            continue
        preset_val = preset[field]  # type: ignore[literal-required]
        if preset_val is not None:
            resolved[field] = preset_val
        else:
            missing.append(field)
    if missing:
        env_names = ", ".join(f"KERYX_{f.upper()}" for f in missing)
        raise ValueError(
            f"network={key!r} has no verified preset for: {', '.join(missing)}. "
            f"Set these via env ({env_names}) with values verified against Circle/Arc "
            f"mainnet docs before selecting this network. The hackathon is testnet-only."
        )
    return resolved
