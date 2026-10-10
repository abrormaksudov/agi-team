--liquibase formatted sql

--changeset abror:1
create table ods__tranzaxis.credit_line_cycle
(
    contract_id        bigint,
    statement_date     date,
    cycle_start_date   date,
    due_date           date,
    grace_end_date     date,
    statement_balance  bigint,
    min_payment        bigint,
    used_limit         bigint,
    paid_amount        bigint,
    overdue_start_date date,
    last_payment_date  date,
    dwh_job_id         text,
    dwh_created_at     timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (contract_id);

alter table ods__tranzaxis.credit_line_cycle
    owner to gpadmin;
