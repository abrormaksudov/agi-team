"""Run the evaluation cases against a running agent and report quality, LLM calls, time and cost per case.

    uv run python eval/run.py --base http://localhost:8601 --runs 2 [--only q4-document]

Signs in as the demo user on the LOCAL catalog (password from product/openmetadata/.env). Results go to eval/results/.
"""

import argparse
import base64
import json
import re
import statistics
import time
from pathlib import Path

import httpx

HERE = Path(__file__).parent
OM = "http://localhost:8585"


def demo_token() -> str:
    env = dict(line.split("=", 1) for line in (HERE / "../../openmetadata/.env").read_text().splitlines() if "=" in line)
    password = env["OM_DEMO_PASSWORD"].strip().strip('"')
    r = httpx.post(f"{OM}/api/v1/users/login",
                   json={"email": "demo@agi.uz", "password": base64.b64encode(password.encode()).decode()})
    r.raise_for_status()
    return r.json()["accessToken"]


def ask(base: str, token: str, case: dict, conversation: str) -> dict:
    answer, proposals, errors, done = [], [], [], {}
    with httpx.stream("POST", f"{base}/agent/chat", headers={"Authorization": f"Bearer {token}"}, timeout=300,
                      json={"conversation_id": conversation, "message": case["question"], "page": case.get("page")}) as r:
        event = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                d = json.loads(line[6:])
                if event == "text":
                    answer.append(d["text"])
                elif event == "proposal":
                    proposals.append(d)
                elif event == "error":
                    errors.append(d["message"])
                elif event == "done":
                    done = d
    text = "".join(answer) + "".join(json.dumps(p, ensure_ascii=False) for p in proposals)
    failed = [f"missing {p!r}" for p in case.get("expect", []) if not re.search(p, text)]
    failed += [f"found {p!r}" for p in case.get("reject", []) if re.search(p, text)]
    if case.get("proposal") and not proposals:
        failed.append("no proposal")
    failed += [f"error: {e}" for e in errors]
    return {"case": case["id"], "ok": not failed, "failed": failed, "llm_calls": done.get("llm_calls"),
            "tools": len(done.get("tool_calls") or []), "seconds": done.get("seconds"), "cost_usd": done.get("cost_usd"),
            "answer": "".join(answer), "proposals": proposals}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8601")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--only", action="append")
    args = ap.parse_args()
    cases = [c for c in json.loads((HERE / "cases.json").read_text()) if not args.only or c["id"] in args.only]
    token = demo_token()
    stamp = time.strftime("%Y%m%d-%H%M%S") + "-" + args.base.rsplit(":", 1)[-1].strip("/")
    results = []
    for case in cases:
        for i in range(args.runs):
            res = ask(args.base, token, case, f"eval-{stamp}-{case['id']}-{i}")
            results.append(res)
            print(f"{'PASS' if res['ok'] else 'FAIL'}  {case['id']:<18} calls={res['llm_calls']} tools={res['tools']} "
                  f"{res['seconds']}s ${res['cost_usd']}  {'; '.join(res['failed'])}", flush=True)
    ok = sum(r["ok"] for r in results)
    secs = [r["seconds"] for r in results if r["seconds"]]
    cost = [r["cost_usd"] for r in results if r["cost_usd"] is not None]
    print(f"\n{ok}/{len(results)} passed · median {statistics.median(secs):.1f}s · max {max(secs):.1f}s · "
          f"total ${sum(cost):.4f} · mean ${statistics.mean(cost):.4f}/question")
    out = HERE / "results" / f"{stamp}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
