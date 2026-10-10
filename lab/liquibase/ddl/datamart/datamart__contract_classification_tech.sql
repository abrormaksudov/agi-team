--liquibase formatted sql

--changeset abror:1
create table datamart.contract_classification_tech
(
    report_date                  date,
    contract_id                  bigint,
    client_id                    bigint,
    contract_type                text,
    product_code                 text,
    contract_status              text,
    open_date                    date,
    principal_balance            bigint,
    interest_balance             bigint,
    overdue_principal_balance    bigint,
    overdue_interest_balance     bigint,
    penalty_balance              bigint,
    written_off_principal        bigint,
    written_off_interest         bigint,
    unused_limit                 bigint,
    oldest_unpaid_principal_date date,
    oldest_unpaid_interest_date  date,
    days_past_due_principal      integer,
    days_past_due_interest       integer,
    days_past_due                integer,
    last_draw_date               date,
    last_repayment_date          date,
    first_due_date               date,
    statement_date               date,
    statement_due_date           date,
    statement_min_payment        bigint,
    statement_paid_amount        bigint,
    dwh_job_id                   text,
    dwh_created_at               timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (contract_id);

alter table datamart.contract_classification_tech
    owner to gpadmin;
