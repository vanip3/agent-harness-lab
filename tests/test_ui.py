"""The web UI's safety behaviour. Skipped if Gradio isn't installed (it's optional)."""
import pytest

pytest.importorskip("gradio")

from ui import app  # noqa: E402  (after the skip check on purpose)


def test_no_answer_counts_as_no(monkeypatch):
    """Fail closed: if nobody clicks Approve or Reject in time, nothing is approved."""
    monkeypatch.setattr(app, "APPROVAL_TIMEOUT", 0.1)
    desk = app.ApprovalDesk()
    assert desk("send_proposal", {"customer": "Acme Retail"}) is False
    assert desk.pending is None


def test_canary_in_a_tool_result_raises_the_alarm():
    event = {"event": "tool_result", "tool": "read_file", "result": f"... {app.CANARY} ..."}
    assert "reached the model" in app.describe(event)


def test_path_check_refusal_is_shown():
    event = {"event": "tool_result", "tool": "read_file",
             "result": "Access denied: ..\\info.txt is outside the sandbox."}
    assert "Path check refused" in app.describe(event)
