"""Catalog content as code, applied by apply.py after the services: owners of the source systems, domains, tiers,
personal-data tags along column lineage, column descriptions carried upstream, the glossary, metrics, Context Center
articles and data contracts. Everything is read from content/ and applied idempotently: a rerun changes nothing.
Standard library only.
"""

import json
from collections import defaultdict
from fnmatch import fnmatch
from pathlib import Path
from urllib.parse import quote

CONTENT = Path(__file__).resolve().parent / "content"
SOURCES = ("iabs.", "mobile.", "tranzaxis.")


def load(name: str):
    path = CONTENT / name
    return json.loads(path.read_text()) if path.exists() else None


def label(fqn: str, source: str = "Classification", label_type: str = "Manual") -> dict:
    return {"tagFQN": fqn, "source": source, "labelType": label_type, "state": "Confirmed"}


def short(fqn: str) -> str:
    return fqn.rsplit(".", 1)[-1]


class Catalog:
    """Tables with their columns, tags and domains, read once; edits are collected per table and sent as one patch."""

    def __init__(self, api) -> None:
        self.api = api
        self.tables = {}
        after = ""
        while True:
            page = api.call("GET", f"/tables?limit=500&fields=columns,tags,domains,owners{after}")
            self.tables.update({t["fullyQualifiedName"]: t for t in page["data"]})
            cursor = page.get("paging", {}).get("after")
            if not cursor:
                break
            after = f"&after={quote(cursor)}"
        self.teams = {}
        self.patches = defaultdict(list)

    def team(self, name: str) -> dict:
        if name not in self.teams:
            self.teams[name] = {"id": self.api.call("GET", f"/teams/name/{name}")["id"], "type": "team"}
        return self.teams[name]

    def match(self, patterns: list[str]) -> list[dict]:
        return [t for fqn, t in self.tables.items() if any(fnmatch(fqn, p) for p in patterns)]

    def column(self, column_fqn: str) -> tuple[dict, int, dict] | None:
        table = self.tables.get(column_fqn.rsplit(".", 1)[0])
        if table:
            for i, c in enumerate(table["columns"]):
                if c["fullyQualifiedName"] == column_fqn:
                    return table, i, c
        return None

    def add_column_tag(self, column_fqn: str, tag: dict) -> bool:
        found = self.column(column_fqn)
        if not found:
            return False
        table, i, col = found
        if any(t["tagFQN"] == tag["tagFQN"] for t in col.get("tags") or []):
            return False
        col.setdefault("tags", []).append(tag)
        self.patches[table["id"]].append({"op": "add", "path": f"/columns/{i}/tags/-", "value": tag})
        return True

    def flush(self) -> int:
        for table_id, ops in self.patches.items():
            self.api.call("PATCH", f"/tables/{table_id}", ops)
        count = len(self.patches)
        self.patches.clear()
        return count

    def column_edges(self) -> list[tuple[list[str], str]]:
        """Every column-lineage mapping as (from columns, to column), read from each table's downstream edges."""
        edges = []
        for fqn in self.tables:
            lineage = self.api.call("GET", f"/lineage/table/name/{quote(fqn)}?upstreamDepth=0&downstreamDepth=1")
            for edge in lineage.get("downstreamEdges") or []:
                for mapping in (edge.get("lineageDetails") or {}).get("columnsLineage") or []:
                    if mapping.get("toColumn") and mapping.get("fromColumns"):
                        edges.append((mapping["fromColumns"], mapping["toColumn"]))
        return edges


def apply_owners(cat: Catalog, services: list[dict]) -> None:
    """A source system belongs to the team that runs it: owner on the service and its databases, inherited by
    schemas and tables that name no owner of their own (dbt models do, from meta.owner)."""
    for spec in services:
        if "owner" not in spec:
            continue
        name, owner = spec["service"]["name"], [cat.team(spec["owner"])]
        endpoint = {"databaseService": "databaseServices", "pipelineService": "pipelineServices"}[spec["kind"]]
        service = cat.api.call("GET", f"/services/{endpoint}/name/{name}?fields=owners")
        entities = [(f"/services/{endpoint}", service)]
        if spec["kind"] == "databaseService":
            databases = cat.api.call("GET", f"/databases?service={name}&fields=owners&limit=100")["data"]
            entities += [("/databases", db) for db in databases]
        for path, entity in entities:
            if [o["id"] for o in entity.get("owners") or []] != [owner[0]["id"]]:
                cat.api.call("PATCH", f"{path}/{entity['id']}", [{"op": "add", "path": "/owners", "value": owner}])
        print(f"  owner {name}: {spec['owner']}")


def apply_domains(cat: Catalog, domains: list[dict]) -> None:
    for d in domains:
        cat.api.call("PUT", "/domains", {
            "name": d["name"], "displayName": d["displayName"], "description": d["description"],
            "domainType": d["domainType"], "owners": [cat.team(d["owner"])],
        })
        missing = [t for t in cat.match(d["assets"]) if d["name"] not in {x["name"] for x in t.get("domains") or []}]
        if missing:
            cat.api.call("PUT", f"/domains/{quote(d['name'])}/assets/add",
                         {"assets": [{"id": t["id"], "type": "table"} for t in missing]})
        print(f"  domain {d['name']}: {len(cat.match(d['assets']))} tables ({len(missing)} added)")


def apply_tiers(cat: Catalog, tiers: dict) -> None:
    for tier, patterns in tiers.items():
        for table in cat.match(patterns):
            tags = table.get("tags") or []
            if any(t["tagFQN"] == tier for t in tags):
                continue
            kept = [t for t in tags if not t["tagFQN"].startswith("Tier.")]
            cat.patches[table["id"]].append({"op": "add", "path": "/tags", "value": kept + [label(tier)]})
            table["tags"] = kept + [label(tier)]
        print(f"  {tier}: {len(cat.match(patterns))} tables")
    cat.flush()


def apply_pii(cat: Catalog, pii: dict, edges: list) -> None:
    """Tag the declared source columns, then follow column lineage downstream and tag every column the value reaches
    unchanged (same name, or a declared rename), so the tag shows wherever the personal data flows."""
    children = defaultdict(set)
    for sources, target in edges:
        for source in sources:
            children[source].add(target)
    tagged = {c: "Manual" for c in pii["sourceColumns"]}
    frontier = list(tagged)
    while frontier:
        column = frontier.pop()
        for target in children[column]:
            name, target_name = short(column), short(target)
            if target not in tagged and (target_name == name or target_name in pii["renames"].get(name, [])):
                tagged[target] = "Propagated"
                frontier.append(target)
    added = sum(cat.add_column_tag(c, {**label(pii["tag"], label_type=kind), "reason": pii["reason"]})
                for c, kind in tagged.items())
    cat.flush()
    print(f"  {pii['tag']}: {len(tagged)} columns ({len(pii['sourceColumns'])} declared, {added} newly tagged)")


def carry_descriptions_upstream(cat: Catalog, edges: list) -> None:
    """Column descriptions are written once, in dbt YAML for the ODS. A PXF ext__ table and the source table behind it
    carry the same column 1:1, so an empty description there takes the documented one (never overwrites)."""
    filled = 0
    for _ in range(3):  # ods → ext__ → source
        for sources, target in edges:
            if len(sources) != 1 or short(sources[0]) != short(target):
                continue
            source = sources[0]
            if not (source.startswith(SOURCES) or ".ext__" in source):
                continue
            found_source, found_target = cat.column(source), cat.column(target)
            if not (found_source and found_target) or found_source[2].get("description"):
                continue
            description = found_target[2].get("description")
            if description:
                table, i, col = found_source
                col["description"] = description
                cat.patches[table["id"]].append({"op": "add", "path": f"/columns/{i}/description", "value": description})
                filled += 1
    cat.flush()
    print(f"  column descriptions carried upstream: {filled}")


def apply_glossary(cat: Catalog, glossary: dict) -> None:
    g = glossary["glossary"]
    cat.api.call("PUT", "/glossaries", {**g, "owners": [cat.team("data_platform")]})
    fqn = {t["name"]: f"{g['name']}.{t['name']}" for t in glossary["terms"]}
    for with_relations in (False, True):
        for t in glossary["terms"]:
            body = {"glossary": g["name"], "name": t["name"], "displayName": t.get("displayName", t["name"]),
                    "description": t["description"], "synonyms": t.get("synonyms", [])}
            if with_relations:
                body["relatedTerms"] = [fqn[r] for r in t.get("relatedTerms", []) if r in fqn]
            term = cat.api.call("PUT", "/glossaryTerms", body)
            if with_relations:
                t["id"] = term["id"]
    linked = 0
    for t in glossary["terms"]:
        tables = cat.match(t.get("assets", {}).get("tables", []))
        if tables:
            assets = cat.api.call("GET", f"/glossaryTerms/{t['id']}/assets?limit=1000").get("data", [])
            missing = [x for x in tables if x["id"] not in {a["id"] for a in assets}]
            if missing:
                cat.api.call("PUT", f"/glossaryTerms/{t['id']}/assets/add",
                             {"assets": [{"id": x["id"], "type": "table"} for x in missing]})
        patterns = t.get("assets", {}).get("columns", [])
        for table in cat.tables.values():
            for col in table["columns"]:
                if any(fnmatch(col["fullyQualifiedName"], p) for p in patterns):
                    linked += cat.add_column_tag(col["fullyQualifiedName"], label(fqn[t["name"]], source="Glossary"))
    cat.flush()
    print(f"  glossary {g['name']}: {len(glossary['terms'])} terms, {linked} columns newly linked")


def domain_names(cat: Catalog) -> dict:
    domains = cat.api.call("GET", "/domains?limit=100")["data"]
    return {d.get("displayName", d["name"]): d["fullyQualifiedName"] for d in domains} | {
        d["name"]: d["fullyQualifiedName"] for d in domains}


def apply_metrics(cat: Catalog, metrics: list[dict]) -> None:
    domains = domain_names(cat)
    for with_relations in (False, True):
        for m in metrics:
            description = m["description"]
            if m.get("computation"):
                description += f"\n\n**How it is computed**\n\n```sql\n{m['computation'].strip()}\n```"
            body = {
                "name": m["name"], "displayName": m["displayName"], "description": description,
                "metricExpression": {"language": "SQL", "code": m["expression"]},
                "metricType": m["metricType"], "unitOfMeasurement": m["unitOfMeasurement"],
                "granularity": m.get("granularity", "DAY"), "owners": [cat.team("data_platform")],
                "domains": [domains[m["domain"]]] if m.get("domain") in domains else [],
            }
            if m.get("customUnitOfMeasurement"):
                body["customUnitOfMeasurement"] = m["customUnitOfMeasurement"]
            if with_relations:
                body["relatedMetrics"] = [r for r in m.get("relatedMetrics", []) if r != m["name"]]
            metric = cat.api.call("PUT", "/metrics", body)
            if with_relations:
                source = next((a for a in m.get("assets", []) if a.endswith(".metrics_daily")), None)
                table = cat.tables.get(source or (m.get("assets") or [""])[0])
                if table:
                    cat.api.call("PUT", "/lineage", {"edge": {
                        "fromEntity": {"id": table["id"], "type": "table"},
                        "toEntity": {"id": metric["id"], "type": "metric"},
                        "lineageDetails": {"description": "Metric read from this table", "sqlQuery": m["expression"]},
                    }})
    print(f"  metrics: {len(metrics)}")


def apply_articles(cat: Catalog, articles: list[dict]) -> None:
    domains = domain_names(cat)
    for a in articles:
        related = []
        for ref in a.get("relatedEntities", []):
            if ref["type"] == "table" and ref["fqn"] in cat.tables:
                related.append({"id": cat.tables[ref["fqn"]]["id"], "type": "table"})
            elif ref["type"] != "table":
                entity = cat.api.call("GET", f"/{ref['type']}s/name/{quote(ref['fqn'])}", missing_ok=True)
                if entity:
                    related.append({"id": entity["id"], "type": ref["type"]})
        cat.api.call("PUT", "/contextCenter/pages", {
            "name": a["name"], "displayName": a["title"], "description": (CONTENT / a["file"]).read_text(),
            "pageType": "Article", "page": {}, "relatedEntities": related,
            "owners": [cat.team("data_platform")],
            "domains": [domains[a["domain"]]] if a.get("domain") in domains else [],
        })
        print(f"  article {a['name']} ({len(related)} related)")


def apply_contracts(cat: Catalog, contracts: list[dict]) -> None:
    for c in contracts:
        table = cat.tables[c["entity"]]
        tests = []
        for test_fqn in c.get("qualityExpectations", []):
            test = cat.api.call("GET", f"/dataQuality/testCases/name/{quote(test_fqn)}", missing_ok=True)
            if test:
                tests.append({"id": test["id"], "type": "testCase"})
        cat.api.call("PUT", "/dataContracts", {
            "name": c["name"], "displayName": c["displayName"], "description": c["description"],
            "entity": {"id": table["id"], "type": "table"}, "entityStatus": c.get("entityStatus", "Approved"),
            "owners": [cat.team(c["owner"])], "termsOfUse": c["termsOfUse"],
            "security": c.get("security"), "sla": c.get("sla"), "qualityExpectations": tests,
            "schema": [{k: col[k] for k in ("name", "dataType", "dataTypeDisplay", "description") if k in col}
                       for col in table["columns"]],
        })
        print(f"  data contract {c['name']} on {c['entity']} ({len(tests)} quality expectations)")


def apply_content(api, services: list[dict]) -> None:
    cat = Catalog(api)
    print(f"content ({len(cat.tables)} tables)")
    apply_owners(cat, services)
    if domains := load("domains.json"):
        apply_domains(cat, domains)
    governance = load("governance.json") or {}
    if governance.get("tiers"):
        apply_tiers(cat, governance["tiers"])
    edges = cat.column_edges()
    print(f"  column lineage: {len(edges)} mappings")
    carry_descriptions_upstream(cat, edges)
    if governance.get("pii"):
        apply_pii(cat, governance["pii"], edges)
    if glossary := load("glossary.json"):
        apply_glossary(cat, glossary)
    if metrics := load("metrics.json"):
        apply_metrics(cat, metrics)
    if articles := load("articles.json"):
        apply_articles(cat, articles)
    if contracts := load("contracts.json"):
        apply_contracts(cat, contracts)
