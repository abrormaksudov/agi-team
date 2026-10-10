"""Catalog as code: create or update the teams, services and ingestion pipelines declared next to this file.

    python3 apply.py [--url http://localhost:8585] [--run]

Logs in as admin (password from ../.env), PUTs teams.json, creates the users in users.json, PUTs every services/*.json (create-or-update, so a rerun
changes nothing), deploys each pipeline to the ingestion Airflow, then applies the content in content/ (content.py:
owners, domains, tiers, PII tags, glossary, metrics, articles, data contracts). With --run it first triggers the
pipelines stage by stage, waiting for each stage to finish: 1 metadata, 2 dbt (needs the tables), 3 usage and
pipelines; then adds the source → ext__ lineage dbt cannot know (from the PXF locations in the ext DDL), applies the
content (it follows that lineage), and last runs 4 profiler. The catalog keeps no sample data; any found is deleted.
--lineage and --content do only that step; --trigger runs the named pipelines, then the content.
Standard library only.
"""

import argparse
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from content import apply_content

HERE = Path(__file__).resolve().parent
EXT_DDL = HERE.parents[2] / "lab" / "liquibase" / "ddl" / "ext"
ADMIN = "admin@open-metadata.org"
LOCATION = re.compile(r"location \('pxf://(?P<schema>\w+)\.(?P<table>\w+)\?profile=jdbc&server=(?P<server>\w+)'\)")
EXT_TABLE = re.compile(r"create readable external table (?P<schema>\w+)\.(?P<table>\w+)")
TERMINAL = {"success", "failed", "partialSuccess"}
START_TIMEOUT = 180  # s: a trigger that has produced no run by then was lost (Airflow dropped it); trigger again
TRIGGERS = 3
STAGE_TIMEOUT = 1800  # s
DAG_SCAN = 15  # s: Airflow 3 learns a deployed DAG only on its next scan (no sync_to_db); a trigger before that is lost


def env_value(name: str) -> str:
    for line in (HERE.parent / ".env").read_text().splitlines():
        key, _, value = line.partition("=")
        if key.strip() == name:
            return value.strip()
    sys.exit(f"{name} missing in {HERE.parent / '.env'}")


class Api:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")
        self.token = None

    def call(self, method: str, path: str, body: dict | list | None = None, missing_ok: bool = False) -> dict | None:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(f"{self.url}/api/v1{path}", data=data, method=method)
        content_type = "application/json-patch+json" if method == "PATCH" else "application/json"
        request.add_header("Content-Type", content_type)
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read()
        except urllib.error.HTTPError as error:
            if missing_ok and error.code == 404:
                return None
            sys.exit(f"{method} {path} → {error.code}: {error.read().decode()[:500]}")
        return json.loads(payload) if payload else {}

    def login(self, password: str) -> None:
        encoded = base64.b64encode(password.encode()).decode()
        self.token = self.call("POST", "/users/login", {"email": ADMIN, "password": encoded})["accessToken"]


def apply_service(api: Api, spec: dict) -> list[dict]:
    kind = spec["kind"]
    endpoint = {"databaseService": "databaseServices", "pipelineService": "pipelineServices"}[kind]
    service = api.call("PUT", f"/services/{endpoint}", spec["service"])
    print(f"service {service['name']}")
    deployed = []
    for p in spec.get("pipelines", []):
        pipeline = api.call("PUT", "/services/ingestionPipelines", {
            "name": p["name"],
            "pipelineType": p["pipelineType"],
            "service": {"id": service["id"], "type": kind},
            "sourceConfig": {"config": p["sourceConfig"]},
            "airflowConfig": {"scheduleInterval": p.get("schedule")},
            "loggerLevel": "INFO",
        })
        api.call("POST", f"/services/ingestionPipelines/deploy/{pipeline['id']}")
        print(f"  pipeline {p['name']} ({p['pipelineType']}) deployed")
        deployed.append({"id": pipeline["id"], "name": p["name"], "stage": p.get("stage", 1)})
    declared = {p["name"] for p in spec.get("pipelines", [])}
    for p in api.call("GET", f"/services/ingestionPipelines?service={service['name']}&limit=100")["data"]:
        if p["name"] not in declared:
            api.call("DELETE", f"/services/ingestionPipelines/{p['id']}?hardDelete=true")
            print(f"  pipeline {p['name']} removed (no longer declared)")
    return deployed


def apply_users(api: Api) -> None:
    """Users in users.json: created with the password from .env (only on first creation), roles kept as declared."""
    for spec in json.loads((HERE / "users.json").read_text()):
        roles = [{"id": api.call("GET", f"/roles/name/{r}")["id"], "type": "role"} for r in spec["roles"]]
        user = api.call("GET", f"/users/name/{spec['name']}?fields=roles", missing_ok=True)
        if user is None:
            password = env_value(spec["passwordEnv"])
            api.call("POST", "/users", {
                "name": spec["name"], "email": spec["email"], "displayName": spec["displayName"],
                "description": spec["description"], "roles": [r["id"] for r in roles], "isBot": False,
                "createPasswordType": "ADMIN_CREATE", "password": password, "confirmPassword": password,
            })
            print(f"user {spec['name']} created ({', '.join(spec['roles'])})")
        elif {r["id"] for r in user.get("roles", [])} != {r["id"] for r in roles}:
            api.call("PATCH", f"/users/{user['id']}", [{"op": "add", "path": "/roles", "value": roles}])
            print(f"user {spec['name']}: roles set to {', '.join(spec['roles'])}")
        else:
            print(f"user {spec['name']} ({', '.join(spec['roles'])})")


def drop_sample_data(api: Api, services: list[dict]) -> None:
    """The catalog keeps no sample rows: they would copy personal data out of the warehouse. Deletes any found."""
    for spec in services:
        if spec["kind"] != "databaseService":
            continue
        after = ""
        while True:
            page = api.call("GET", f"/tables?service={spec['service']['name']}&limit=500{after}")
            for table in page["data"]:
                sample = api.call("GET", f"/tables/{table['id']}/sampleData").get("sampleData") or {}
                if sample.get("rows"):
                    api.call("DELETE", f"/tables/{table['id']}/sampleData")
                    print(f"  sample data removed: {table['fullyQualifiedName']}")
            cursor = page.get("paging", {}).get("after")
            if not cursor:
                break
            after = f"&after={urllib.parse.quote(cursor)}"


def run_stage(api: Api, pipelines: list[dict]) -> None:
    started = int(time.time() * 1000)
    pending = {}
    for p in pipelines:
        api.call("POST", f"/services/ingestionPipelines/trigger/{p['id']}")
        print(f"  triggered {p['name']}")
        pending[p["id"]] = {"name": p["name"], "triggers": 1, "at": time.time()}
    deadline = time.time() + STAGE_TIMEOUT
    while pending:
        time.sleep(10)
        if time.time() > deadline:
            sys.exit(f"stage not finished after {STAGE_TIMEOUT} s: {', '.join(p['name'] for p in pending.values())}")
        for pid, p in list(pending.items()):
            status = api.call("GET", f"/services/ingestionPipelines/{pid}?fields=pipelineStatuses").get("pipelineStatuses")
            if isinstance(status, list):  # 2.0.x returns the recent runs, older versions only the last one
                status = max(status, key=lambda s: s.get("startDate", 0), default=None)
            ours = status and status.get("startDate", 0) >= started - 60_000
            if ours and status.get("pipelineState") in TERMINAL:
                print(f"  {p['name']}: {status['pipelineState']}")
                del pending[pid]
            elif not ours and time.time() - p["at"] > START_TIMEOUT:
                if p["triggers"] == TRIGGERS:
                    sys.exit(f"{p['name']}: no run after {TRIGGERS} triggers")
                api.call("POST", f"/services/ingestionPipelines/trigger/{pid}")
                p["triggers"] += 1
                p["at"] = time.time()
                print(f"  {p['name']}: no run {START_TIMEOUT} s after the trigger, triggered again")


def pxf_lineage(api: Api) -> None:
    """Source table → ext__ table edges, column level by name. dbt knows every edge from ext__ onward; this hop it cannot
    know, so it is read from the PXF location in each external table's DDL (the same text Greenplum stores)."""
    for path in sorted(EXT_DDL.glob("*/*.sql")):
        ddl = path.read_text()
        location, ext = LOCATION.search(ddl), EXT_TABLE.search(ddl)
        if not (location and ext):
            continue
        source_fqn = f"{location['server']}.{location['server']}.{location['schema']}.{location['table']}"
        target_fqn = f"greenplum.dwh.{ext['schema']}.{ext['table']}"
        source = api.call("GET", f"/tables/name/{source_fqn}?fields=columns")
        target = api.call("GET", f"/tables/name/{target_fqn}?fields=columns")
        source_columns = {c["name"] for c in source["columns"]}
        columns = [
            {"fromColumns": [f"{source_fqn}.{c['name']}"], "toColumn": f"{target_fqn}.{c['name']}"}
            for c in target["columns"]
            if c["name"] in source_columns
        ]
        api.call("PUT", "/lineage", {"edge": {
            "fromEntity": {"id": source["id"], "type": "table"},
            "toEntity": {"id": target["id"], "type": "table"},
            "lineageDetails": {"columnsLineage": columns, "description": "PXF external table reading the source live"},
        }})
        print(f"  lineage {source_fqn} → {target_fqn} ({len(columns)} columns)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8585")
    parser.add_argument("--run", action="store_true", help="trigger every pipeline, stage by stage, with lineage and content")
    parser.add_argument("--lineage", action="store_true", help="only (re)add the source → ext__ lineage")
    parser.add_argument("--content", action="store_true", help="only (re)apply the content in content/")
    parser.add_argument("--trigger", nargs="+", metavar="PIPELINE", help="run only these pipelines, then the content")
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # progress shows in a log file too

    api = Api(args.url)
    api.login(env_value("OM_ADMIN_PASSWORD"))
    services = [json.loads(path.read_text()) for path in sorted((HERE / "services").glob("*.json"))]
    if args.lineage:
        pxf_lineage(api)
        return
    for team in json.loads((HERE / "teams.json").read_text()):
        api.call("PUT", "/teams", team)
        print(f"team {team['name']}")
    apply_users(api)
    if args.content:
        apply_content(api, services)
        return
    pipelines = []
    for spec in services:
        pipelines += apply_service(api, spec)
    drop_sample_data(api, services)
    if args.trigger or args.run:
        time.sleep(DAG_SCAN)
    if args.trigger:
        unknown = set(args.trigger) - {p["name"] for p in pipelines}
        if unknown:
            sys.exit(f"unknown pipelines: {', '.join(sorted(unknown))}")
        run_stage(api, [p for p in pipelines if p["name"] in args.trigger])
    if not args.run:
        apply_content(api, services)
        return
    for stage in sorted({p["stage"] for p in pipelines}):
        if stage == 4:
            print("source → ext__ lineage")
            pxf_lineage(api)
            apply_content(api, services)
        print(f"stage {stage}")
        run_stage(api, [p for p in pipelines if p["stage"] == stage])


if __name__ == "__main__":
    main()
