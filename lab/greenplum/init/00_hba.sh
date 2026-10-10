# Trust gpadmin from this host's own addresses: gpinitsystem trusts only the IP the container had at
# first start, so after a restart with a new IP, PXF startup (gpadmin over TCP, no password) is refused.
# pg_hba matches top-down, so the line goes above the image's catch-all md5 rules.
hba="${GREENPLUM_DATA_DIRECTORY}/master/${GREENPLUM_SEG_PREFIX}-1/pg_hba.conf"
sed -i '/^host all all 0.0.0.0\/0 md5/i host all gpadmin samehost trust' "${hba}"
gpstop -u
