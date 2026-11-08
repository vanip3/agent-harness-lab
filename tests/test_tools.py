"""Attack each tool's own check directly, with no model. If a test fails, a control is broken.

These used to be printed by `python -m tools.registry` and read by eye; now they fail on their own.
"""
import pytest

from tools import registry
from tools.registry import run_tool

# Ways an attacker could write a path to info.txt, outside the sandbox (written by me, 5 Nov).
ATTACK_PATHS = [
    "../info.txt",               # the plain version
    "../../info.txt",            # climbing more than one level
    "E:\\info.txt",              # a full path with a drive letter
    "../..\\info.txt",           # forward and back slashes mixed
    "..\\info.txt",              # the exact path the model used in the injection demo (run 7)
    "../sandbox_evil/info.txt",  # a folder whose name only starts with "sandbox"
    "sandbox/../../info.txt",    # going in, then climbing back out
]


@pytest.fixture(autouse=True)
def guarded(monkeypatch):
    """Every test here runs with the guardrails on, as in normal use."""
    monkeypatch.setattr(registry, "UNGUARDED", False)


@pytest.mark.parametrize("path", ATTACK_PATHS)
def test_read_file_refuses_paths_outside_the_sandbox(path):
    result = run_tool("read_file", {"path": path})
    assert result.startswith("Access denied"), f"{path!r} was not refused: {result[:60]}"
    assert "DEMOCO-CANARY-7731" not in result


def test_read_file_still_reads_inside_the_sandbox():
    """The allowed twin: a control that blocks everything would pass every test above."""
    assert run_tool("read_file", {"path": "welcome.txt"}).startswith("Welcome to DemoCo")


@pytest.mark.parametrize("expression", [
    "__import__('os').system('dir')",  # code execution
    "2 ** 999999",                     # power is not allowed (a huge number would freeze it)
    "True + 1",                        # booleans don't count as numbers
    "x * 2",                           # names are not allowed
])
def test_calculator_refuses_anything_but_arithmetic(expression):
    result = run_tool("calculator", {"expression": expression})
    assert isinstance(result, str) and result.startswith("Error evaluating expression")


def test_calculator_does_arithmetic():
    assert run_tool("calculator", {"expression": "2 + 3 * 4"}) == 14
    assert run_tool("calculator", {"expression": "-5 + 2"}) == -3


def test_calculator_refuses_division_by_zero_politely():
    assert run_tool("calculator", {"expression": "10 / 0"}).startswith("Error evaluating expression")


def test_customer_lookup_is_safe_from_sql_injection():
    """Parameterised SQL: the attack is treated as a strange name, not as SQL."""
    result = run_tool("customer_lookup", {"name": "x' OR '1'='1"})
    assert isinstance(result, str) and result.startswith("No customer found")


def test_customer_lookup_finds_a_real_customer():
    result = run_tool("customer_lookup", {"name": "acme retail"})
    assert result["id"] == "C-101"


def test_load_skill_refuses_unknown_names():
    result = run_tool("load_skill", {"skill_name": "../../secrets"})
    assert result.startswith("Unknown skill")
