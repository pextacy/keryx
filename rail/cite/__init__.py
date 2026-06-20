"""rail/cite/ — the citation-toll endpoint (ORIGINAL WORK).

The x402 + Circle Gateway SDK is TypeScript-only (DECISIONS.md), so the *live* ``/cite``
flow — ``402`` with payment requirements -> retry with EIP-3009 auth -> verify -> record ->
Gateway batch -> Receipt — is implemented in ``rail/m0_spike/seller.ts``, and the Python
agent settles through ``shared.rail.HttpRail`` -> ``rail/m0_spike/payer.ts``.

This Python package is the contract anchor on the rail side, not a second implementation:
``rail/main.py`` exposes health/config only, so the repo map + frozen ``shared/`` contract
have a home without duplicating the TS seller.
"""
