"""Role-based permissions. The application sets the role; the model never chooses it."""
from tools.registry import TOOLS

# Which tools each role may use. This is the policy: change it here, and the whole harness follows.
# Any role not listed here gets no tools at all (default deny).
ACCESS = {
    "sales": {"get_time", "load_skill", "read_file", "calculator", "customer_lookup", "send_proposal"},
    "engineering": {"get_time", "load_skill", "read_file", "calculator"},
    "finance": {
        "get_time", "load_skill", "read_file", "calculator",
        "customer_lookup", "revenue_summary", "send_proposal",
    },
}


def is_allowed(role, tool_name):
    """True only if this role may use this tool."""
    return tool_name in ACCESS.get(role, set())


def schemas_for(role):
    """The tool schemas this role is allowed to see. The model is only told about these."""
    return [entry["schema"] for name, entry in TOOLS.items() if is_allowed(role, name)]


if __name__ == "__main__":
    for role in ("sales", "engineering", "finance", "intern"):
        print(f"{role:12}", [schema["function"]["name"] for schema in schemas_for(role)])
    print("engineering -> revenue_summary allowed?", is_allowed("engineering", "revenue_summary"))
    print("finance     -> revenue_summary allowed?", is_allowed("finance", "revenue_summary"))
