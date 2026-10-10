--liquibase formatted sql

--changeset abror:1
create table ods__tranzaxis.payment_schedule
(
    schedule_line_id  bigint,
    contract_id       bigint,
    schedule_revision smallint,
    debt_kind         text,
    due_date          date,
    scheduled_amount  bigint,
    paid_amount       bigint,
    unpaid_amount     bigint,
    last_paid_date    date,
    dwh_job_id        text,
    dwh_created_at    timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (schedule_line_id);

alter table ods__tranzaxis.payment_schedule
    owner to gpadmin;
