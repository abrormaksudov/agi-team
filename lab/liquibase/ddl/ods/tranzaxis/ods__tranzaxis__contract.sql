--liquibase formatted sql

--changeset abror:1
create table ods__tranzaxis.contract
(
    contract_id        bigint,
    client_id          bigint,
    contract_type      text,
    product_code       text,
    status             text,
    currency_code      char(3),
    credit_limit       bigint,
    interest_rate      numeric(5, 2),
    term_months        smallint,
    principal_amount   bigint,
    settlement_account char(20),
    open_date          date,
    close_date         date,
    dwh_job_id         text,
    dwh_created_at     timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (contract_id);

alter table ods__tranzaxis.contract
    owner to gpadmin;
