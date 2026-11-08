"""Every tool in one place. Each entry holds the Python function and the schema the model sees."""
import ast
import operator
from contextlib import closing
from datetime import datetime

from harness.context import ROOT, SKILLS_DIR
from tools.company_db import connect

SANDBOX_DIR = ROOT / "sandbox"

# For the prompt-injection demo only. False means read_file stays inside sandbox/.
# Only `python -m harness.loop ... --unguarded` sets it to True, for that one run.
UNGUARDED = False

# The only operations the calculator allows. Anything not listed here is refused.
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,  # a minus sign in front of a number, as in -5
}
MAX_EXPRESSION_LENGTH = 100


def get_time():
    """Return the current local date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def load_skill(skill_name):
    """Return the full text of a skill, or an error message the model can read."""
    known = [path.parent.name for path in SKILLS_DIR.glob("*/SKILL.md")]
    if skill_name not in known:
        return f"Unknown skill '{skill_name}'. Known skills: {', '.join(known)}"
    skill_path = SKILLS_DIR / skill_name / "SKILL.md"
    return skill_path.read_text(encoding="utf-8")


def read_file(path):
    """Return the text of a file inside the sandbox folder, or an error message the model can read."""
    target = (SANDBOX_DIR / path).resolve()
    if UNGUARDED:
        if not target.is_file():
            return f"File not found: {path} is not a file."
        return target.read_text(encoding="utf-8")
    if not target.is_relative_to(SANDBOX_DIR.resolve()):
        return f"Access denied: {path} is outside the sandbox."
    if not target.is_file():
        return f"File not found: {path} is not a file."
    return target.read_text(encoding="utf-8")


def evaluate(node):
    """Work out the value of one node of the expression tree. Calls itself for the parts below it."""
    # A plain number, such as 12. type(...) in, not isinstance, so True and False don't count.
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value

    # Two sides joined by an allowed operator, such as 3 * 4.
    # Work out each side first (each may be a whole tree itself), then apply the operator.
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        left = evaluate(node.left)
        right = evaluate(node.right)
        return OPERATORS[type(node.op)](left, right)

    # A minus sign in front, such as -5.
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](evaluate(node.operand))

    # Anything else, such as a function call, a name or **, is refused.
    # Raising is fine here, because calculator() catches it and returns a message.
    raise ValueError(f"'{type(node).__name__}' is not allowed")


def calculator(expression):
    """Calculate an arithmetic expression safely, without eval(). Returns the result or an error message."""
    if len(expression) > MAX_EXPRESSION_LENGTH:
        return f"Expression is too long (max {MAX_EXPRESSION_LENGTH} characters)."
    try:
        tree = ast.parse(expression, mode="eval")
        return evaluate(tree.body)
    except (SyntaxError, ValueError, ZeroDivisionError) as e:
        return f"Error evaluating expression: {e}"


def customer_lookup(name):
    """Return one customer's record as a dict, or an error message the model can read."""
    # closing(...) closes the connection when the block ends, even if the query fails.
    with closing(connect()) as connection:
        row = connection.execute(
            "SELECT * FROM customers WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
    if row is None:
        return f"No customer found with the name '{name}'. Please provide the full name."
    return dict(row)


def revenue_summary(quarter):
    """Return the company's revenue for one quarter. Finance-only data, so role permissions decide who sees it."""
    with closing(connect()) as connection:
        row = connection.execute("SELECT * FROM revenue WHERE quarter = ?", (quarter,)).fetchone()
    if row is None:
        return f"No revenue recorded for '{quarter}'. Use a quarter like 2026-Q3."
    return dict(row)


def send_proposal(customer, summary):
    """Send a proposal to a customer. Here, "send" means one new row in the local outbox table.

    This is the agent's first action with a side effect, so the middleware asks a person first.
    """
    with closing(connect()) as connection:
        cursor = connection.execute(
            "INSERT INTO outbox (customer, summary, created_at) VALUES (?, ?, ?)",
            (customer, summary, datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        connection.commit()
    return f"Proposal for {customer} sent (outbox #{cursor.lastrowid})."


def outbox_count():
    """How many proposals are in the outbox. For tests only, not a tool."""
    with closing(connect()) as connection:
        return connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]


TOOLS = {
    "get_time": {
        "function": get_time,
        "schema": {
            "type": "function",
            "function": {
                "name": "get_time",
                "description": "Get the current local date and time.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    },

    "read_file": {
        "function": read_file,
        "schema": {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file from the sandbox folder. Example: welcome.txt",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "The relative path of the file to read, inside the sandbox folder.",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
    },
    "calculator": {
        "function": calculator,
        "schema": {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": (
                    "Evaluate a simple arithmetic expression safely. "
                    "Supports +, -, *, /, and brackets."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "The arithmetic expression to evaluate.",
                        }
                    },
                    "required": ["expression"],
                },
            },
        },
    },

    "customer_lookup": {
        "function": customer_lookup,
        "schema": {
            "type": "function",
            "function": {
                "name": "customer_lookup",
                "description": (
                    "Look up one customer by full name, such as Acme Retail. "
                    "Returns their id, product, monthly spend and status."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The full name of the customer to look up.",
                        }
                    },
                    "required": ["name"],
                },
            },
        },
    },

    "revenue_summary": {
        "function": revenue_summary,
        "schema": {
            "type": "function",
            "function": {
                "name": "revenue_summary",
                "description": (
                    "Get the company's total revenue for one quarter, such as 2026-Q3. "
                    "Returns the quarter and the amount in USD."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "quarter": {
                            "type": "string",
                            "description": "The quarter, written like 2026-Q3.",
                        }
                    },
                    "required": ["quarter"],
                },
            },
        },
    },

    "send_proposal": {
        "function": send_proposal,
        "schema": {
            "type": "function",
            "function": {
                "name": "send_proposal",
                "description": (
                    "Send a short proposal to a customer. Use only when the user asks to send one. "
                    "A person must approve it before it is sent."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer": {
                            "type": "string",
                            "description": "The customer's full name.",
                        },
                        "summary": {
                            "type": "string",
                            "description": "The proposal in one or two sentences, under 200 characters.",
                        },
                    },
                    "required": ["customer", "summary"],
                },
            },
        },
    },

    "load_skill": {
        "function": load_skill,
        "schema": {
            "type": "function",
            "function": {
                "name": "load_skill",
                "description": "Load the full steps of a skill by its name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "The name of the skill to load.",
                        }
                    },
                    "required": ["skill_name"],
                },
            },
        },
    },
}


def get_schemas():
    """Return the list of schemas to send to the model."""
    return [entry["schema"] for entry in TOOLS.values()]


def run_tool(name, args):
    """Run the tool the model asked for and return its result.

    A tool that crashes is a bug in my code, not something the model can fix, so the error
    is raised rather than returned (return vs raise).
    """
    if name not in TOOLS:
        return f"Unknown tool '{name}'. Known tools: {', '.join(TOOLS)}"
    return TOOLS[name]["function"](**args)


if __name__ == "__main__":
    # A quick demo. The attacks are asserted in tests/test_tools.py.
    print("Tools:", [schema["function"]["name"] for schema in get_schemas()])
    print("Good skill:", run_tool("load_skill", {"skill_name": "triage-issue"})[:40])
    print("Bad skill:", run_tool("load_skill", {"skill_name": "../../secrets"}))
    print("Good file:", run_tool("read_file", {"path": "welcome.txt"})[:40])
    print("Climbs out:", run_tool("read_file", {"path": "..\\info.txt"}))
    print("Calculator:", run_tool("calculator", {"expression": "2 + 3 * 4"}))
    print("Calculator attack:", run_tool("calculator", {"expression": "__import__('os').system('dir')"}))
    print("Customer:", run_tool("customer_lookup", {"name": "Acme Retail"}))
    print("SQL injection attempt:", run_tool("customer_lookup", {"name": "x' OR '1'='1"}))
