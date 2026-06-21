"""Agent-tool manifest — expose Keryx's primitives as callable agent tools.

The Circle Agent Stack (circlefin/agent-stack-starter-kits) wires Arc capabilities into agent
frameworks (Claude Agent SDK, OpenAI Agents SDK, LangChain) as callable tools. This ports that
idea: a manifest that describes Keryx's settlement primitives in the standard tool-use shape
({name, description, input_schema}) plus the HTTP route each maps to — so another agent can
discover Keryx's capabilities and invoke them with JSON, no bespoke integration.

The schemas are hand-authored (not derived from FastAPI) so the descriptions read for an LLM
audience: when to use the tool, what each field means.
"""

from __future__ import annotations

from dataclasses import dataclass


def _wallet(desc: str) -> dict[str, object]:
    return {"type": "string", "description": desc, "pattern": "^0x[a-fA-F0-9]{40}$"}


def _usdc(desc: str) -> dict[str, object]:
    return {"type": "string", "description": f"{desc} (decimal USDC string, 6-dp)"}


@dataclass(frozen=True)
class AgentTool:
    """A primitive described as an agent tool: name, when-to-use, input schema, HTTP route."""

    name: str
    description: str
    method: str
    path: str
    properties: dict[str, object]
    required: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "route": {"method": self.method, "path": self.path},
            "input_schema": {
                "type": "object",
                "properties": self.properties,
                "required": list(self.required),
            },
        }


AGENT_TOOLS: tuple[AgentTool, ...] = (
    AgentTool(
        "ask",
        "Answer a research question with grounded, paid citations. Pays each cited source on "
        "the rail and returns a signed attestation. Use to research and cite the open web.",
        "POST",
        "/ask",
        {
            "query": {"type": "string", "description": "The research question"},
            "budget": _usdc("Optional max to spend on citations"),
        },
        ("query",),
    ),
    AgentTool(
        "send_payment",
        "Send USDC to a wallet with a provenance memo (kind/ref/note). Use to pay an author or "
        "settle an obligation while recording why it was paid.",
        "POST",
        "/send",
        {
            "to": _wallet("Recipient wallet"),
            "amount": _usdc("Amount to send"),
            "memo": {"type": "string", "description": "Why this was paid"},
            "kind": {
                "type": "string",
                "enum": ["citation", "invoice", "attestation", "job", "note", "other"],
            },
        },
        ("to", "amount"),
    ),
    AgentTool(
        "split_payout",
        "Split one payment across contributors in proportion to their weights (dust-free). Use "
        "to pay an attribution graph — every credited contributor gets their exact share.",
        "POST",
        "/payout",
        {
            "amount": _usdc("Total to split"),
            "contributors": {
                "type": "array",
                "description": "Each {wallet, share} — shares are relative weights",
                "items": {"type": "object"},
            },
        },
        ("amount", "contributors"),
    ),
    AgentTool(
        "swap_stablecoin",
        "Swap USDC<->EURC at the current rate less an app fee. Use to convert a payout between "
        "stablecoins before settling.",
        "POST",
        "/swap",
        {
            "token_in": {"type": "string", "enum": ["USDC", "EURC"]},
            "token_out": {"type": "string", "enum": ["USDC", "EURC"]},
            "amount_in": _usdc("Amount of token_in"),
            "to": _wallet("Optional recipient of token_out"),
        },
        ("token_in", "token_out", "amount_in"),
    ),
    AgentTool(
        "request_money",
        "Open a split-bill request: ask a set of payers to cover a total, split evenly. Use to "
        "collect a shared cost (each payer fulfils their share to the payee).",
        "POST",
        "/request",
        {
            "payee": _wallet("Who receives the collected funds"),
            "payers": {"type": "array", "items": _wallet("A payer wallet")},
            "total": _usdc("Total to split across payers"),
        },
        ("payee", "payers", "total"),
    ),
    AgentTool(
        "buy_credits",
        "Prepay USDC into a credit balance (optionally a discounted tier) to fund many later "
        "actions in one settlement. Use to batch micro-tolls.",
        "POST",
        "/credits/topup",
        {
            "wallet": _wallet("Wallet to credit"),
            "amount": _usdc("USDC to prepay (omit when using a tier)"),
            "tier": {"type": "string", "enum": ["starter", "plus", "pro", "scale"]},
        },
        ("wallet",),
    ),
    AgentTool(
        "open_escrow",
        "Open a milestone escrow: lock a total across tranches that release to the provider on "
        "approval. Use for staged delivery where payment follows accepted work.",
        "POST",
        "/escrow",
        {
            "client": _wallet("Funds the escrow"),
            "provider": _wallet("Receives released tranches"),
            "milestones": {
                "type": "array",
                "description": "Each {label, amount}",
                "items": {"type": "object"},
            },
        },
        ("client", "provider", "milestones"),
    ),
    AgentTool(
        "approve_workflow",
        "Approve a batch of settlement intents that then execute in order — nothing settles "
        "that wasn't approved. Use to plan and authorize a payment batch before executing it.",
        "POST",
        "/workflow/approve",
        {
            "intents": {
                "type": "array",
                "description": "Each {to, amount, kind} to approve",
                "items": {"type": "object"},
            }
        },
        ("intents",),
    ),
)


def manifest() -> dict[str, object]:
    """The full tool manifest plus a count — Keryx's primitives as agent tools."""
    return {"count": len(AGENT_TOOLS), "tools": [t.as_dict() for t in AGENT_TOOLS]}
