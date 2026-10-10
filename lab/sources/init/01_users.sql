-- Lab users, identical on every source system; password equals user name.
CREATE USER loader PASSWORD 'loader';
CREATE USER pxf PASSWORD 'pxf';
CREATE USER openmetadata PASSWORD 'openmetadata';

GRANT pg_read_all_data, pg_write_all_data TO loader;
GRANT pg_read_all_data TO pxf;
GRANT pg_read_all_data, pg_read_all_stats TO openmetadata;

CREATE EXTENSION pg_stat_statements;
