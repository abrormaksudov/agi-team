--liquibase formatted sql

--changeset abror:1
create table datamart.portfolio_daily
(
    report_date               date,
    client_id                 bigint,
    pinfl                     char(14),
    iabs_customer_code        char(8),
    contracts_count           integer,
    credit_lines_count        integer,
    microloans_count          integer,
    principal_balance         bigint,
    overdue_principal_balance bigint,
    overdue_interest_balance  bigint,
    penalty_balance           bigint,
    total_exposure            bigint,
    max_days_past_due         integer,
    worst_classification      text,
    is_npl                    boolean,
    dwh_job_id                text,
    dwh_created_at            timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (client_id);

alter table datamart.portfolio_daily
    owner to gpadmin;
