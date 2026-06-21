"""Approved-action workflows — Keryx runs Circle's OOAK WorkflowManager *directly*.

Unlike Keryx's other Circle capabilities (offline analogues that re-model an upstream), this
module wires the actual ``circlefin/circle-ooak`` library in-process. OOAK is vendored at
``apps/circle-ooak`` and installed as the ``circle-ooak`` package; its real
``WorkflowManager`` is the engine that owns the approve → ordered-execute state machine.

This adapter is a thin translation layer: it maps Keryx's settlement intents to OOAK's JSON
intent shape (``{function, arguments}``) and renders the views the agent API returns. The
approved-order guard is asserted here as well — OOAK's per-intent match is advisory — so the
guarantee holds: nothing settles that wasn't approved, in the approved order.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from circle_ooak.workflow_manager import WorkflowManager as _OoakManager


class WorkflowError(Exception):
    """An execution that doesn't match the approved workflow (wrong call, order, or id)."""


def _ooak_intent(function: str, args: dict[str, object]) -> str:
    """Serialize a settlement intent in OOAK's canonical JSON shape (``{function, arguments}``).

    Keys are sorted and separators tight so the approve-time and execute-time strings match
    regardless of dict ordering — OOAK compares the parsed JSON, but a stable string keeps our
    own order guard exact too.
    """
    return json.dumps(
        {"function": function, "arguments": args}, sort_keys=True, separators=(",", ":")
    )


@dataclass(frozen=True)
class _Status:
    """Status wrapper exposing ``.value`` so views match the agent API's render contract."""

    value: str


@dataclass
class ActionView:
    intent: str
    status: _Status
    result: str | None


@dataclass
class WorkflowView:
    id: str
    status: _Status
    cursor: int
    actions: list[ActionView]

    def remaining(self) -> int:
        return sum(1 for a in self.actions if a.status.value == "not_started")


def _view(wfid: str, wf: Any) -> WorkflowView:
    """Render an OOAK Workflow into the view the agent API serializes."""
    actions = [
        ActionView(intent=a.intent, status=_Status(a.status), result=a.result) for a in wf.actions
    ]
    return WorkflowView(
        id=wfid, status=_Status(wf.status), cursor=wf.current_action, actions=actions
    )


class WorkflowManager:
    """Keryx-facing manager backed by Circle's OOAK ``WorkflowManager`` (used directly).

    Exposes the same surface the agent already calls (``create_intent``/``approve``/``check``/
    ``complete``/``get``/``summary``/``reject``) while delegating the state machine to OOAK.
    """

    def __init__(self) -> None:
        self._ooak = _OoakManager()

    def create_intent(self, function: str, args: dict[str, object]) -> dict[str, object]:
        """Phase 1: describe a call without running it (returns the OOAK intent string too)."""
        return {"function": function, "args": args, "intent": _ooak_intent(function, args)}

    def approve(self, intents: list[dict[str, object]]) -> str:
        """Phase 2: approve a batch via OOAK; returns the OOAK-issued workflow id."""
        if not intents:
            raise WorkflowError("cannot approve an empty workflow")
        ooak_intents: list[str] = []
        for i in intents:
            raw = i.get("args", {})
            args = raw if isinstance(raw, dict) else {}
            ooak_intents.append(_ooak_intent(str(i["function"]), args))
        resp = self._ooak.approve(ooak_intents)
        if not resp.approved:
            raise WorkflowError(resp.msg or "workflow not approved")
        return str(resp.msg)  # OOAK returns the new wfid in the response message

    def get(self, wfid: str) -> WorkflowView | None:
        wf = self._ooak.workflows.get(wfid)
        return None if wf is None else _view(wfid, wf)

    def summary(self) -> dict[str, object]:
        """Counts for the dashboard, tagged with the engine so reviewers see it's the real lib."""
        wfs = self._ooak.workflows
        completed = sum(1 for w in wfs.values() if w.status == "completed")
        return {"total": len(wfs), "active": len(wfs) - completed, "engine": "circle-ooak"}

    def check(self, wfid: str, function: str, args: dict[str, object]) -> str:
        """Phase 3 guard: the next unexecuted action must match this call. Raises otherwise.

        Returns the intent string, which is the handle passed back to ``complete``.
        """
        wf = self._ooak.workflows.get(wfid)
        if wf is None:
            raise WorkflowError(f"unknown workflow {wfid!r}")
        if wf.status == "rejected":
            raise WorkflowError(f"workflow {wfid!r} was rejected")
        if wf.current_action >= len(wf.actions):
            raise WorkflowError(f"workflow {wfid!r} has no remaining actions")
        intent = _ooak_intent(function, args)
        expected = wf.actions[wf.current_action].intent
        if expected != intent:
            raise WorkflowError(
                f"call does not match the approved next action in {wfid!r} "
                f"(expected {expected}, got {intent})"
            )
        resp = self._ooak.start(wfid, intent)
        if not resp.approved:
            raise WorkflowError(resp.msg or "OOAK rejected the action start")
        return intent

    def complete(self, wfid: str, action: str, result: str, *, ok: bool = True) -> None:
        """Mark the in-progress action done via OOAK and advance to the next approved action."""
        wf = self._ooak.workflows.get(wfid)
        if wf is None:
            raise WorkflowError(f"unknown workflow {wfid!r}")
        if ok:
            resp = self._ooak.complete(wfid, action, result)
            if not resp.approved:
                raise WorkflowError(resp.msg or "OOAK rejected the action completion")
            return
        # OOAK's complete only records success; record the failure and advance for parity so a
        # failed settlement doesn't wedge the batch.
        idx = wf.current_action
        if idx < len(wf.actions):
            wf.actions[idx].status = "failed"
            wf.actions[idx].result = result
            wf.current_action += 1
            if wf.current_action >= len(wf.actions):
                wf.status = "failed"

    def reject(self, wfid: str) -> None:
        wf = self._ooak.workflows.get(wfid)
        if wf is not None:
            wf.status = "rejected"
