FROM woblerr/opengpdb:6.29.11

ADD --checksum=sha256:73914527305a40cce504b0d3d90b23caf565136912d607ae8ae7c5895512332c --chown=1001:1001 \
    https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.14/postgresql-42.7.14.jar /opt/lab/pxf/lib/
COPY --chown=1001:1001 pxf/servers /opt/lab/pxf/servers
COPY --chown=1001:1001 init /docker-entrypoint-initdb.d
