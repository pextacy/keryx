"""Approved-action workflows backed directly by Circle's OOAK WorkflowManager (in-process).

These assert that Keryx's workflow capability runs the *real* circlefin/circle-ooak engine
(installed as the ``circle-ooak`` package, adopted at ``apps/circle-ooak``), not a
reimplementation: approve a batch, execute in the approved order, reject anything else.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import agent.main as main
from shared.ooak_workflow import WorkflowError, WorkflowManager

A = "0x" + "a" * 40
B = "0x" + "b" * 40


def test_engine_is_the_real_ooak_library() -> None:
    # The adapter wraps circle_ooak.workflow_manager.WorkflowManager directly.
    from circle_ooak.workflow_manager import WorkflowManager as OoakManager

    mgr = WorkflowManager()
    assert isinstance(mgr._ooak, OoakManager)
    assert mgr.summary()["engine"] == "circle-ooak"


def test_approve_then_execute_in_order_completes() -> None:
    mgr = WorkflowManager()
    a1 = {"function": "settle", "args": {"to": A, "amount": "0.01", "kind": "workflow"}}
    a2 = {"function": "settle", "args": {"to": B, "amount": "0.02", "kind": "workflow"}}
    wfid = mgr.approve([a1, a2])
    assert wfid

    h1 = mgr.check(wfid, "settle", a1["args"])
    mgr.complete(wfid, h1, "0xtx1")
    h2 = mgr.check(wfid, "settle", a2["args"])
    mgr.complete(wfid, h2, "0xtx2")

    wf = mgr.get(wfid)
    assert wf is not None
    assert wf.status.value == "completed"
    assert wf.remaining() == 0
    assert [a.result for a in wf.actions] == ["0xtx1", "0xtx2"]


def test_unapproved_call_is_rejected() -> None:
    mgr = WorkflowManager()
    approved = {"function": "settle", "args": {"to": A, "amount": "0.01", "kind": "workflow"}}
    wfid = mgr.approve([approved])
    with pytest.raises(WorkflowError):
        mgr.check(wfid, "settle", {"to": B, "amount": "9.99", "kind": "workflow"})


def test_out_of_order_execution_is_rejected() -> None:
    mgr = WorkflowManager()
    a1 = {"function": "settle", "args": {"to": A, "amount": "0.01", "kind": "workflow"}}
    a2 = {"function": "settle", "args": {"to": B, "amount": "0.02", "kind": "workflow"}}
    wfid = mgr.approve([a1, a2])
    # second action cannot run before the first
    with pytest.raises(WorkflowError):
        mgr.check(wfid, "settle", a2["args"])


def test_empty_approval_rejected() -> None:
    with pytest.raises(WorkflowError):
        WorkflowManager().approve([])


def test_unknown_workflow_rejected() -> None:
    with pytest.raises(WorkflowError):
        WorkflowManager().check("nope", "settle", {"to": A, "amount": "0.01"})


# --- endpoint level: the agent API drives the real OOAK engine ---


@pytest.fixture()
def client() -> TestClient:
    return TestClient(main.app)


def test_workflow_endpoints_approve_and_execute(client: TestClient) -> None:
    approve = client.post(
        "/workflow/approve",
        json={"intents": [{"to": A, "amount": "0.01"}, {"to": B, "amount": "0.02"}]},
    )
    assert approve.status_code == 200, approve.text
    wfid = approve.json()["wfid"]
    assert wfid

    ex1 = client.post(f"/workflow/{wfid}/execute", json={"to": A, "amount": "0.01"})
    assert ex1.json()["settled"] is True

    # wrong next action is refused
    bad = client.post(f"/workflow/{wfid}/execute", json={"to": A, "amount": "0.01"})
    assert "error" in bad.json()

    ex2 = client.post(f"/workflow/{wfid}/execute", json={"to": B, "amount": "0.02"})
    assert ex2.json()["settled"] is True

    status = client.get(f"/workflow/{wfid}").json()
    assert status["status"] == "completed"
    assert status["remaining"] == 0
