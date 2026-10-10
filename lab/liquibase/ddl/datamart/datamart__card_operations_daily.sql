--liquibase formatted sql

--changeset abror:1
create table datamart.card_operations_daily
(
    oper_day               date,
    network                text,
    channel                text,
    mcc_group              text,
    transaction_kind       text,
    transactions_count     integer,
    approved_count         integer,
    declined_count         integer,
    amount_uzs             bigint,
    approved_amount_uzs    bigint,
    cash_like_amount_uzs   bigint,
    high_risk_count        integer,
    cards_count            integer,
    dwh_job_id             text,
    dwh_created_at         timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (oper_day);

alter table datamart.card_operations_daily
    owner to gpadmin;
