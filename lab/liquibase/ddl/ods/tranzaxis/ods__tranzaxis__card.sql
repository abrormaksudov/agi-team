--liquibase formatted sql

--changeset abror:1
create table ods__tranzaxis.card
(
    card_id        bigint,
    contract_id    bigint,
    client_id      bigint,
    product_type   text,
    network        text,
    status         text,
    masked_pan     text,
    issued_at      timestamptz,
    expiry_date    date,
    pan_hash       char(64),
    dwh_job_id     text,
    dwh_created_at timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (card_id);

alter table ods__tranzaxis.card
    owner to gpadmin;
