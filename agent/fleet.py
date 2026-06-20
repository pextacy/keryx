"""Agent fleet runner — generate genuine settlement volume (Phase 5 / M4).

Issues a set of queries to the running agent's /ask, accumulating citations and
settlement. Agents are the users (prd.md §2), so self-generated volume is legitimate;
external volume (``--external``) is what we lead with. Run:

    python -m agent.fleet --n 50 --url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import sys

import httpx

QUERIES = [
    "How do Gateway nanopayments settle sub-cent USDC on Arc?",
    "What makes Arc different from other layer-1 blockchains?",
    "How does the x402 payment flow work between a buyer and seller?",
    "Why was a per-citation micropayment never economical before Arc?",
    "How does an agent prove a source actually grounded its answer?",
    "What is EIP-3009 and how is it used in gasless settlement?",
    "How are many small USDC payments batched and settled in bulk?",
]


def run(url: str, n: int, external: bool, agents: int) -> int:
    settled = 0
    cites = 0
    agents = max(1, min(agents, n))
    with httpx.Client(timeout=120) as client:
        for i in range(n):
            q = QUERIES[i % len(QUERIES)]
            # Cycle through `agents` distinct payer wallets so /metrics reflects real
            # distinct-session volume rather than a single agent.
            wallet = f"0x{(i % agents) + 1:040x}"
            try:
                r = client.post(
                    f"{url}/ask",
                    json={"query": q, "external": external, "agent_wallet": wallet},
                )
                r.raise_for_status()
                data = r.json()
            except Exception as exc:  # noqa: BLE001 - report and continue the run
                print(f"#{i + 1} FAILED: {exc}")
                continue
            c = data["counts"]["cited"]
            cites += c
            print(f"#{i + 1} cited={c} settled={data['total_settled']} USDC")
    print(f"\nfleet done: {n} queries, {cites} citations")
    try:
        m = httpx.get(f"{url}/metrics", timeout=30).json()
        print(f"ledger: {m}")
    except Exception:  # noqa: BLE001
        pass
    return 0 if cites or settled == 0 else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Keryx agent fleet runner")
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--external", action="store_true", help="label volume as external")
    p.add_argument(
        "--agents", type=int, default=3, help="distinct payer wallets to spread volume across"
    )
    args = p.parse_args(argv)
    return run(args.url, args.n, args.external, args.agents)


if __name__ == "__main__":
    sys.exit(main())
