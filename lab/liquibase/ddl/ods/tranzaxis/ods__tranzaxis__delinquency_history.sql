--liquibase formatted sql

--changeset abror:1
create table ods__tranzaxis.delinquency_history
(
    contract_id    bigint,
    effective_date date,
    state          text,
    previous_state text,
    days_past_due  integer,
    recorded_at    timestamptz,
    dwh_job_id     text,
    dwh_created_at timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (contract_id);

alter table ods__tranzaxis.delinquency_history
    owner to gpadmin;
