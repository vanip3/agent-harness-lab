"""The middleware pipeline, tested with hand-crafted calls: no model, same result every time."""
import pytest

from harness.middleware import run_checks
from tools.registry import outbox_count

PROPOSAL = {"customer": "Acme Retail", "summary": "Upgrade to DemoCo Sync at 10% off."}


def say(answer):
    """A stand-in approver that always gives this answer."""
    return lambda name, args: answer


@pytest.mark.parametrize("name, args, role, expected_check", [
    ("delete_everything", {}, "finance", "check_unknown_tool"),
    ("revenue_summary", {"quarter": "2026-Q3"}, "engineering", "check_permission"),
    ("get_time", {}, "intern", "check_permission"),  # unknown role: default deny
    ("customer_lookup", {}, "sales", "check_arguments"),  # missing argument
    ("customer_lookup", {"name": "Acme Retail", "sql": "DROP TABLE"}, "sales", "check_arguments"),
    ("customer_lookup", {"name": 42}, "sales", "check_arguments"),  # not text
    ("customer_lookup", {"name": "A" * 500}, "sales", "check_arguments"),  # too long
])
def test_the_first_failing_check_stops_the_call(name, args, role, expected_check):
    problem = run_checks(name, args, role)
    assert problem is not None and problem[0] == expected_check


def test_a_valid_call_passes_every_check():
    assert run_checks("revenue_summary", {"quarter": "2026-Q3"}, "finance") is None


def test_approval_no_blocks_and_yes_passes():
    assert run_checks("send_proposal", PROPOSAL, "sales", approver=say(False))[0] == "check_approval"
    assert run_checks("send_proposal", PROPOSAL, "sales", approver=say(True)) is None


def test_a_forbidden_role_is_refused_before_anyone_is_asked():
    asked = []
    approver = lambda name, args: asked.append(name) or True
    problem = run_checks("send_proposal", PROPOSAL, "engineering", approver=approver)
    assert problem[0] == "check_permission"
    assert asked == [], "a person was asked to approve a call the role may not make"


def test_checks_alone_never_send_anything():
    before = outbox_count()
    run_checks("send_proposal", PROPOSAL, "sales", approver=say(True))
    assert outbox_count() == before  # the checks decide; only run_tool sends
