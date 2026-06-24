"""Network registry + Settings resolution — testnet preset, env override, and the
testnet-only guard. No network I/O."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.config import Settings
from shared.network import CHAIN_FIELDS, NETWORKS, resolve_chain_values


def test_testnet_is_the_default_and_fully_resolved() -> None:
    s = Settings()
    assert s.network == "testnet"
    assert s.arc_chain_id == 0x4CEF52
    assert s.usdc_address == "0x3600000000000000000000000000000000000000"
    assert s.gateway_wallet == "0x0077777d7EBA4688BDeF3E311b846F25870A19B9"
    assert s.caip2_network == "eip155:5042002"
    assert s.explorer_url == "https://testnet.arcscan.app"


def test_single_constant_can_be_overridden_without_changing_network() -> None:
    s = Settings(usdc_address="0xDEADBEEF00000000000000000000000000000000")
    assert s.usdc_address == "0xDEADBEEF00000000000000000000000000000000"
    assert s.network == "testnet"
    assert s.arc_chain_id == 0x4CEF52  # other constants still from the preset


def test_testnet_is_the_only_network() -> None:
    assert set(NETWORKS) == {"testnet"}


@pytest.mark.parametrize("name", ["mainnet", "devnet", "Arc"])
def test_unknown_network_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        Settings(network=name)


def test_resolve_rejects_unknown_network() -> None:
    with pytest.raises(ValueError):
        resolve_chain_values("mainnet", {})


def test_registry_presets_cover_all_chain_fields() -> None:
    for net, preset in NETWORKS.items():
        assert set(preset.keys()) == set(CHAIN_FIELDS), net
