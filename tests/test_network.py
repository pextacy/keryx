"""Network registry + Settings resolution — testnet preset, env override, and the
mainnet fail-loud guard. No network I/O."""

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


def test_mainnet_without_verified_constants_fails_loud() -> None:
    with pytest.raises(ValidationError):
        Settings(network="mainnet")


def test_mainnet_with_supplied_constants_constructs() -> None:
    supplied = {f: ("0x" + f[:2]) for f in CHAIN_FIELDS}
    supplied["arc_chain_id"] = 12345  # type: ignore[assignment]
    supplied["caip2_network"] = "eip155:12345"
    s = Settings(network="mainnet", **supplied)  # type: ignore[arg-type]
    assert s.network == "mainnet"
    assert s.arc_chain_id == 12345
    assert s.caip2_network == "eip155:12345"


def test_unknown_network_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(network="devnet")


def test_resolve_lists_every_missing_field_for_an_empty_preset() -> None:
    with pytest.raises(ValueError) as exc:
        resolve_chain_values("mainnet", {})
    msg = str(exc.value)
    # every mainnet preset value is None, so all chain fields must be reported missing
    assert all(field in msg for field in CHAIN_FIELDS)


def test_registry_presets_cover_all_chain_fields() -> None:
    for net, preset in NETWORKS.items():
        assert set(preset.keys()) == set(CHAIN_FIELDS), net
