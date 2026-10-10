--liquibase formatted sql

--changeset abror:1
create table ods__iabs.payment_document
(
    document_id     bigint,
    document_date   date,
    oper_day        date,
    payer_account   char(20),
    payer_bank_code char(5),
    payer_name      text,
    payee_account   char(20),
    payee_bank_code char(5),
    payee_name      text,
    amount          bigint,
    currency_code   char(3),
    purpose         text,
    state           text,
    created_at      timestamptz,
    dwh_job_id      text,
    dwh_created_at  timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (document_id);

alter table ods__iabs.payment_document
    owner to gpadmin;
