"""Record every step of a run to logs/trace.jsonl, and print a readable line for each."""
import json
import sys
import uuid
from datetime import datetime

from harness.context import ROOT

TRACE_FILE = ROOT / "logs" / "trace.jsonl"  # logs/ is git-ignored
PREVIEW = 160  # how many characters of long text to show on screen (the file keeps it all)


def new_run_id():
    """A short unique id, so all the events from one run can be grouped together."""
    return uuid.uuid4().hex[:8]


def log_event(run_id, step, event, **details):
    """Append one event to the trace file as a JSON line, and print it for the console."""
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "run_id": run_id,
        "step": step,
        "event": event,
        **details,  # whatever extra fields the caller passes, such as tool="calculator"
    }
    TRACE_FILE.parent.mkdir(exist_ok=True)
    with TRACE_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, default=str) + "\n")  # default=str copes with odd types
    print(format_event(record))


def format_event(record):
    """Turn one event into a short line for the screen."""
    details = {k: v for k, v in record.items() if k not in ("time", "run_id", "step", "event")}
    parts = []
    for key, value in details.items():
        text = str(value).replace("\n", " ")
        if len(text) > PREVIEW:
            text = text[:PREVIEW] + "..."
        parts.append(f"{key}={text}")
    return f"[{record['run_id']} step {record['step']}] {record['event']:<12} " + "  ".join(parts)


def show_last_run():
    """Print every event from the most recent run in the trace file."""
    if not TRACE_FILE.exists():
        print("No trace yet. Run the agent first.")
        return
    records = [json.loads(line) for line in TRACE_FILE.read_text(encoding="utf-8").splitlines() if line]
    last_run = records[-1]["run_id"]
    for record in records:
        if record["run_id"] == last_run:
            print(format_event(record))


if __name__ == "__main__":
    # Usage: python -m harness.trace     shows the most recent run
    sys.stdout.reconfigure(encoding="utf-8")
    show_last_run()
