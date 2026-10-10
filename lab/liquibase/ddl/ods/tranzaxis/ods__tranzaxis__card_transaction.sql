--liquibase formatted sql

--changeset abror:1
create table ods__tranzaxis.card_transaction
(
    transaction_id   bigint,
    card_id          bigint,
    contract_id      bigint,
    oper_day         date,
    registered_at    timestamptz,
    transaction_kind text,
    channel          text,
    mcc              char(4),
    amount           bigint,
    currency_code    char(3),
    amount_uzs       bigint,
    status           text,
    decline_reason   text,
    rrn              char(12),
    dwh_job_id       text,
    dwh_created_at   timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (transaction_id);

alter table ods__tranzaxis.card_transaction
    owner to gpadmin;
