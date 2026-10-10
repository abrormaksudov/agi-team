--liquibase formatted sql

--changeset abror:1
create table dbt_test__audit.dq_test_log
(
    unique_id      text,
    model_name     text,
    test_name      text,
    started_at     timestamp,
    status         text,
    execution_time numeric,
    finished_at    timestamp
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed randomly;

alter table dbt_test__audit.dq_test_log
    owner to gpadmin;
