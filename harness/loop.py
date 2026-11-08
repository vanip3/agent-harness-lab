"""The core agent loop: model -> tool request -> checks -> run tool -> append result -> repeat."""
import argparse

import httpx
import ollama

from harness.context import build_system_prompt
from harness.guardrails import UNTRUSTED_RULE, detect_injection, wrap_untrusted
from harness.middleware import NEEDS_APPROVAL, run_checks
from harness.permissions import schemas_for
from harness.trace import log_event, new_run_id
from tools import registry
from tools.registry import run_tool

MODEL = "qwen2.5:7b"
NUM_CTX = 8192
MAX_STEPS = 5  # the most times we will call the model in one run
MODEL_TIMEOUT = 300  # seconds to wait for one model reply before giving up

client = ollama.Client(timeout=MODEL_TIMEOUT)


def run_agent(question, role, max_steps=MAX_STEPS, approver=None):
    """Run the loop until the model gives a final answer or we hit max_steps.

    role comes from the application (the person using it), never from the model.
    approver: a function (name, args) -> True or False that decides on actions needing
    approval. None means ask at the terminal.
    """
    run_id = new_run_id()
    log_event(run_id, 0, "run_start", unguarded=registry.UNGUARDED, question=question,
              model=MODEL, role=role)
    system_prompt = build_system_prompt()
    if not registry.UNGUARDED:
        system_prompt += "\n" + UNTRUSTED_RULE  # layer 2: tell the model what the markers mean
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    message = None
    step = 0
    while step < max_steps:
        step += 1
        try:
            response = client.chat(model=MODEL, messages=messages,
                                   options={"num_ctx": NUM_CTX}, tools=schemas_for(role))
        except (ConnectionError, httpx.TimeoutException, ollama.ResponseError) as error:
            # Not something the model can fix: stop cleanly, record why, and tell the user.
            log_event(run_id, step, "decision", action="model_error", error=str(error))
            return f"The model could not be reached ({type(error).__name__}). Is Ollama running?"
        message = response.message
        messages.append(message)
        log_event(run_id, step, "model_reply",
                  tool_calls=[call.function.name for call in message.tool_calls or []],
                  content=message.content)

        if not message.tool_calls:
            if not message.content:
                log_event(run_id, step, "decision", action="empty_reply")
                return "The reply was empty."
            log_event(run_id, step, "decision", action="final_answer")
            return message.content

        for call in message.tool_calls:
            name = call.function.name
            args = call.function.arguments
            problem = run_checks(name, args, role, approver)
            if problem:
                check_name, result = problem  # result, not message: message is the model's reply
                log_event(run_id, step, "decision", action="block", check=check_name, tool=name)
                log_event(run_id, step, "tool_result", tool=name, result=result)
                # Not wrapped as untrusted: the harness wrote this text, not an outsider.
                messages.append({"role": "tool", "tool_name": name, "content": str(result)})
                continue
            if name in NEEDS_APPROVAL:
                log_event(run_id, step, "decision", action="approved", tool=name)

            log_event(run_id, step, "decision", action="run_tool", tool=name, args=args)
            result = run_tool(name, args)
            log_event(run_id, step, "tool_result", tool=name, result=result)
            # Layer 3: an alarm, not a block. It logs a warning and changes nothing the model sees.
            injection_patterns = detect_injection(str(result))
            if injection_patterns:
                log_event(run_id, step, "warning", type="injection_suspected", tool=name,
                          patterns=injection_patterns)
            content = str(result) if registry.UNGUARDED else wrap_untrusted(name, result)
            messages.append({"role": "tool", "tool_name": name, "content": content})

    log_event(run_id, step, "decision", action="step_limit")
    last = message.content if message else ""
    return f"Reached max steps ({max_steps}) without a final answer. Last content: {last}"


if __name__ == "__main__":
    # Usage: python -m harness.loop "your question" --role finance [--max-steps 5]
    parser = argparse.ArgumentParser(description="Run the agent once.")
    parser.add_argument("question")
    parser.add_argument("--role", default="sales",
                        help="who is using the agent: sales, engineering or finance")
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS)
    # store_true: the flag is False unless it is typed. For the prompt-injection demo only.
    parser.add_argument("--unguarded", action="store_true",
                        help="DEMO ONLY: switch off the guardrails (read_file sandbox, "
                             "untrusted-output markers) to show prompt injection")
    options = parser.parse_args()

    if options.unguarded:
        registry.UNGUARDED = True
        # The trace records it too: run_start has unguarded=True for this run.
        print("WARNING: UNGUARDED mode is ON. The read_file sandbox and the untrusted-output "
              "markers are disabled. This is a security risk.")
    print("Final answer:", run_agent(options.question, options.role, options.max_steps))
