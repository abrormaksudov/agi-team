"""One JSON line per answered question: who asked, what ran, tokens, cost, time. Never the user's token."""

import json
import os
import time
from pathlib import Path

JOURNAL = Path(os.environ.get("AGENT_JOURNAL", "data/journal.jsonl"))


def write(record: dict) -> None:
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **record}, ensure_ascii=False) + "\n")
