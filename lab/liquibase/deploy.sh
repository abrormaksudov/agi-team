#!/bin/sh
# One master changelog includes every DDL file in byte order, so _init/ runs before ext/, ods/, datamart/;
# a single Liquibase run (one JVM) applies them all. Changesets keep their identity (file path + id + author).
set -eu
master=/tmp/changelog.yaml
echo "databaseChangeLog:" > "$master"
find ddl -name '*.sql' | LC_ALL=C sort | while read -r file; do
    echo "  - include: { file: $file }" >> "$master"
done
liquibase --defaults-file=liquibase.properties --search-path=/liquibase/changelog,/tmp \
    update --changelog-file=changelog.yaml
