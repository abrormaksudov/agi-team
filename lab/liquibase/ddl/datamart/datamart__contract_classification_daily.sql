--liquibase formatted sql

--changeset abror:1
create table datamart.contract_classification_daily
(
    report_date               date,
    contract_id               bigint,
    client_id                 bigint,
    contract_type             text,
    product_code              text,
    classification            text,
    previous_classification   text,
    days_in_classification    integer,
    days_past_due             integer,
    consecutive_overdue_days  integer,
    overdue_band              text,
    is_first_grace_period     boolean,
    principal_balance         bigint,
    interest_balance          bigint,
    overdue_principal_balance bigint,
    overdue_interest_balance  bigint,
    penalty_balance           bigint,
    dwh_job_id                text,
    dwh_created_at            timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (contract_id);

alter table datamart.contract_classification_daily
    owner to gpadmin;
