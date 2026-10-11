#!/bin/sh
# Bring agi-demo in line with the commit checked out in /opt/agi: start the lab, then the catalog (Compose recreates
# only what changed; the one-shot services rerun every time: Liquibase DDL, dbt deps + parse for the manifest and the
# Airflow DAGs, OM migrations), then apply the catalog as code. Idempotent.
# Run by .github/workflows/deploy.yml right after it checks the pushed commit out; by hand, from the repo root:
#   ssh agi-demo /opt/agi/tools/deploy/deploy.sh
set -eu
cd "$(dirname "$0")/../.."
rev=$(git log -1 --format='%h %s')
start=$(date +%s)
echo "deploying $rev"

# Images are rebuilt only when their inputs changed since the last successful deploy (ref refs/deploy/agi-demo); a
# missing image is built by `up` anyway. Even a no-change `--build` asks each base image's registry for metadata, and
# docker.getcollate.io answers that with 429 Too Many Requests.
last=$(git rev-parse -q --verify refs/deploy/agi-demo || true)
changed() { [ -n "$last" ] && ! git diff --quiet "$last" HEAD -- "$@"; }
lab_build=; changed lab/airflow/Dockerfile pyproject.toml uv.lock lab/greenplum lab/liquibase/Dockerfile && lab_build=--build
catalog_build=; changed product/openmetadata/ingestion && catalog_build=--build

echo "::group::lab ${lab_build:-(no image changes)}"
docker compose -f lab/compose.yaml up -d $lab_build --wait --remove-orphans
# init scripts run only on an empty volume: replay the source DDL's table and column comments (idempotent)
for source in mobile iabs tranzaxis; do
    grep -h '^COMMENT ON' lab/sources/init/1?_"$source".sql | docker compose -f lab/compose.yaml exec -T "$source" \
        sh -c 'psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
done
echo "::endgroup::"

echo "::group::catalog ${catalog_build:-(no image changes)}"
docker compose -f product/openmetadata/compose.yaml --profile public up -d $catalog_build --wait --remove-orphans
# the proxy's config is mounted from the repo, so a changed file does not recreate the container
docker compose -f product/openmetadata/compose.yaml --profile public exec -T proxy caddy reload --config /etc/caddy/Caddyfile
echo "::endgroup::"

echo "::group::catalog as code"
python3 product/openmetadata/catalog/apply.py
echo "::endgroup::"

git update-ref refs/deploy/agi-demo HEAD
mkdir -p /opt/agi-logs
echo "$(date '+%F %T') $rev ($(( $(date +%s) - start ))s)" | tee -a /opt/agi-logs/deploys.log
