"""Backport open-metadata/OpenMetadata#32031 (issue #32030) into openmetadata-ingestion 2.0.5.

Usage ingestion looked a Query up by its bare hash, but the Query FQN is `service.hash`:
the lookup always missed, so a query seen again for another table was re-created and lost
its links to the earlier tables. Merged to main 2026-09-10, not in any 2.0.x release.
"""

import importlib.util
from pathlib import Path

REPLACEMENTS = [
    (
        "from metadata.ingestion.ometa.client import REST\n",
        "from metadata.ingestion.ometa.client import REST, APIError\n",
    ),
    (
        """\
        query_hash = self._get_query_hash(query=query.query.root)
        query_entity = self.get_by_name(entity=Query, fqn=query_hash)
        if query_entity is None:
            resp = self.client.put(self.get_suffix(Query), data=query.model_dump_json())
            if resp and resp.get("id"):
                query_entity = Query(**resp)
        return query_entity
""",
        """\
        fqn = f"{model_str(query.service)}.{self._get_query_hash(query=query.query.root)}"
        query_entity = self.get_by_name(entity=Query, fqn=fqn)
        if query_entity is None:
            try:
                resp = self.client.put(self.get_suffix(Query), data=query.model_dump_json())
                if resp and resp.get("id"):
                    query_entity = Query(**resp)
            except APIError as err:
                # Same SQL created by another table in this run: fetch it so usage still attaches.
                if err.status_code == 409:
                    query_entity = self.get_by_name(entity=Query, fqn=fqn)
                else:
                    raise
        return query_entity
""",
    ),
]

package = Path(importlib.util.find_spec("metadata").submodule_search_locations[0])
path = package / "ingestion/ometa/mixins/query_mixin.py"
source = path.read_text()
for old, new in REPLACEMENTS:
    assert source.count(old) == 1, f"{path} changed upstream; review the backport: {old.strip()[:60]!r}"
    source = source.replace(old, new)
path.write_text(source)
print(f"patched {path}")
