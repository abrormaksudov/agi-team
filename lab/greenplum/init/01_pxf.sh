# JDBC driver and one PXF server per source system; sourced by the image on first start.
cp /opt/lab/pxf/lib/*.jar "${PXF_BASE}/lib/"
cp -r /opt/lab/pxf/servers/. "${PXF_BASE}/servers/"
pxf cluster sync
pxf cluster restart
