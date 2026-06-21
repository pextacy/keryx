"""Approved-action workflows — gate settlements behind an intent/approve/execute flow.

Ports the security model of circlefin/circle-ooak (secure_tool + WorkflowManager): an agent
action runs in three phases —

1. **Intent**  — describe the call (function + args) without running it.
2. **Approve** — a list of intents is approved together, yielding a workflow id.
3. **Execute** — each call must match an approved intent, in order, before it runs.

OOAK wires this into the OpenAI Agents SDK; Keryx ports the pure state machine (no SDK
dependency) so an autonomous paying agent can plan a batch of settlements, get the batch
approved once, then execute only the approved set — nothing settles that wasn't approved.

Intents are compared by canonical JSON (function + sorted args), so formatting differences
don't cause spurious mismatches.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field


class ActionStatus(enum.Enum):
    NOT_STARTED = "not_started"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowStatus(enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"


class WorkflowError(Exception):
    """An execution that doesn't match the approved workflow (wrong call, order, or id)."""


def canonical_intent(function: str, args: dict[str, object]) -> str:
    """Canonical JSON for an intent — stable key for matching approve-time vs execute-time."""
    return json.dumps({"function": function, "args": args}, sort_keys=True, separators=(",", ":"))


@dataclass
class Action:
    """One approved call: its canonical intent, a status, and (once run) a result."""

    intent: str
    status: ActionStatus = ActionStatus.NOT_STARTED
    result: str | None = None


@dataclass
class Workflow:
    """An ordered batch of approved actions; execution must follow the approved order."""

    id: str
    actions: list[Action]
    status: WorkflowStatus = WorkflowStatus.APPROVED
    cursor: int = 0  # index of the next action expected to execute

    def remaining(self) -> int:
        return sum(1 for a in self.actions if a.status is ActionStatus.NOT_STARTED)


@dataclass
class WorkflowManager:
    """Holds approved workflows and enforces that executions match the approved intents.

    Deterministic ids (``wf-1``, ``wf-2``, …) so the offline flow is reproducible — no clock
    or randomness (the agent's settlement is meant to be auditable end to end).
    """

    _workflows: dict[str, Workflow] = field(default_factory=dict)
    _counter: int = 0

    def create_intent(self, function: str, args: dict[str, object]) -> dict[str, object]:
        """Phase 1: describe a call without running it."""
        return {"function": function, "args": args, "intent": canonical_intent(function, args)}

    def approve(self, intents: list[dict[str, object]]) -> str:
        """Phase 2: approve a batch of intents together; returns a workflow id."""
        if not intents:
            raise WorkflowError("cannot approve an empty workflow")
        actions: list[Action] = []
        for i in intents:
            raw_args = i.get("args", {})
            args = raw_args if isinstance(raw_args, dict) else {}
            actions.append(Action(intent=canonical_intent(str(i["function"]), args)))
        self._counter += 1
        wfid = f"wf-{self._counter}"
        self._workflows[wfid] = Workflow(id=wfid, actions=actions)
        return wfid

    def get(self, wfid: str) -> Workflow | None:
        return self._workflows.get(wfid)

    def summary(self) -> dict[str, object]:
        """Counts for the dashboard: total approved workflows and how many are still active."""
        total = len(self._workflows)
        completed = sum(1 for w in self._workflows.values() if w.status is WorkflowStatus.COMPLETED)
        return {"total": total, "active": total - completed}

    def check(self, wfid: str, function: str, args: dict[str, object]) -> Action:
        """Phase 3 guard: the next unexecuted action must match this call. Raises otherwise."""
        wf = self._workflows.get(wfid)
        if wf is None:
            raise WorkflowError(f"unknown workflow {wfid!r}")
        if wf.status is WorkflowStatus.REJECTED:
            raise WorkflowError(f"workflow {wfid!r} was rejected")
        if wf.cursor >= len(wf.actions):
            raise WorkflowError(f"workflow {wfid!r} has no remaining actions")
        action = wf.actions[wf.cursor]
        want = canonical_intent(function, args)
        if action.intent != want:
            raise WorkflowError(
                f"call does not match the approved next action in {wfid!r} "
                f"(expected {action.intent}, got {want})"
            )
        return action

    def complete(self, wfid: str, action: Action, result: str, *, ok: bool = True) -> None:
        """Mark an action done and advance the cursor (call after a successful execute)."""
        action.status = ActionStatus.COMPLETED if ok else ActionStatus.FAILED
        action.result = result
        wf = self._workflows[wfid]
        wf.cursor += 1
        if wf.cursor >= len(wf.actions):
            wf.status = WorkflowStatus.COMPLETED

    def reject(self, wfid: str) -> None:
        wf = self._workflows.get(wfid)
        if wf is not None:
            wf.status = WorkflowStatus.REJECTED
