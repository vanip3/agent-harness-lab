"""The middleware pipeline. Every tool call passes these checks, in order, before it runs.

Each check takes (name, args, role, approver) and returns None if the call is fine,
or a message the model can read if it isn't. The first failing check stops the call.
"""
from tools.registry import TOOLS
from harness.permissions import is_allowed

MAX_ARG_LENGTH = 200  # no tool here needs a longer argument

# Tools with side effects: a person must say yes before each call runs.
NEEDS_APPROVAL = {"send_proposal"}


def ask_human(name, args):
    """The default approver: ask at the terminal, and return True only for a clear yes.

    Any function with the same shape, (name, args) -> True or False, can be passed to
    run_checks instead, for example approve/reject buttons in a web UI.
    """
    print(f"\n  APPROVAL NEEDED: the agent wants to call {name}")
    for key, value in args.items():
        print(f"    {key}: {value}")
    try:
        answer = input("  Approve? (y/n): ")
    except EOFError:  # no person at the keyboard, for example in an automated run
        return False
    return answer.strip().lower() == "y"


def check_unknown_tool(name, args, role, approver):
    """Is there a tool with this name at all?"""
    if name not in TOOLS:
        return f"Access denied: unknown tool '{name}'"
    return None


def check_permission(name, args, role, approver):
    """May this role use this tool? (Layer 2: holds even if the model names a hidden tool.)"""
    if not is_allowed(role, name):
        return f"Access denied: role '{role}' may not use tool '{name}'"
    return None


def check_arguments(name, args, role, approver):
    """Do the arguments match the tool's schema?"""
    # The schema the model was given for this tool, for example for customer_lookup:
    #   expected = {"name": {...}}   (the argument names allowed)
    #   required = ["name"]          (the ones that must be there)
    parameters = TOOLS[name]["schema"]["function"]["parameters"]
    expected = parameters["properties"]
    required = parameters["required"]
    # "Invalid arguments", not "Access denied": the model can fix these and try again.
    prefix = f"Invalid arguments for '{name}'"
    if not isinstance(args, dict):
        return f"{prefix}: expected a dict of arguments, got {type(args).__name__}."
    if not all(isinstance(key, str) for key in args):
        return f"{prefix}: argument names must be text."
    if not all(key in args for key in required):
        return f"{prefix}: missing {set(required) - set(args)}. Try again with them."
    if not all(key in expected for key in args):
        return f"{prefix}: unexpected {set(args) - set(expected)}. Use only {list(expected)}."
    if not all(isinstance(value, str) for value in args.values()):
        return f"{prefix}: every argument value must be text."
    if not all(len(value) <= MAX_ARG_LENGTH for value in args.values()):
        return f"{prefix}: an argument is longer than {MAX_ARG_LENGTH} characters."
    return None


def check_approval(name, args, role, approver):
    """Did a person approve this call? Only tools in NEEDS_APPROVAL ask."""
    # Look up ask_human at call time (not as a default argument), so a replacement
    # set by a test or the eval runner still takes effect.
    approve = approver or ask_human
    if name in NEEDS_APPROVAL and not approve(name, args):
        return (
            f"A person did not approve the call to '{name}'. Nothing was sent. "
            f"Do not call {name} again for this request; tell the user it was not approved."
        )
    return None


# Unknown tool first: it's the only check that's safe on its own, and the others need TOOLS[name].
# Permission before arguments: a role that may not use a tool gets no help fixing the call.
# A person last: only asked about calls that are real, permitted and well formed.
CHECKS = [check_unknown_tool, check_permission, check_arguments, check_approval]


def run_checks(name, args, role, approver=None):
    """Run every check in order. Return None if all pass, or (check name, message) for the first that fails.

    approver: a function (name, args) -> True or False. None means ask at the terminal.
    """
    for check in CHECKS:
        problem = check(name, args, role, approver)
        if problem:
            return check.__name__, problem
    return None


if __name__ == "__main__":
    # A quick demo with hand-crafted calls: no model, so the result is the same every time.
    # The same calls are asserted in tests/test_middleware.py.
    from tools.registry import outbox_count, run_tool

    calls = [
        ("delete_everything", {}, "finance"),                                         # no such tool
        ("revenue_summary", {"quarter": "2026-Q3"}, "engineering"),                   # role not allowed
        ("customer_lookup", {}, "sales"),                                             # argument missing
        ("customer_lookup", {"name": "Acme Retail", "sql": "DROP TABLE"}, "sales"),   # extra argument
        ("customer_lookup", {"name": 42}, "sales"),                                   # not text
        ("customer_lookup", {"name": "A" * 500}, "sales"),                            # too long
        ("revenue_summary", {"quarter": "2026-Q3"}, "finance"),                       # fine
        ("get_time", {}, "intern"),                                                   # unknown role
    ]
    for name, args, role in calls:
        shown = {key: (value[:20] + "...") if isinstance(value, str) and len(value) > 20 else value
                 for key, value in args.items()}
        print(f"{role:12} {name:18} {shown}")
        print("   ->", run_checks(name, args, role) or "PASS")

    # Approval with a stand-in person, so no typing is needed. The tool runs only if every
    # check passes, the same as in the loop.
    proposal = {"customer": "Acme Retail", "summary": "Upgrade to DemoCo Sync at 10% off."}
    for answer, role in (("y", "sales"), ("n", "sales"), ("y", "engineering")):
        before = outbox_count()
        problem = run_checks("send_proposal", proposal, role, approver=lambda n, a: answer == "y")
        if not problem:
            run_tool("send_proposal", proposal)
        print(f"{role:12} send_proposal, person says {answer!r}")
        print("   ->", problem or "PASS", f"| outbox rows added: {outbox_count() - before}")
