--liquibase formatted sql

--changeset abror:1
create table ods__tranzaxis.client
(
    client_id          bigint,
    core_customer_code char(8),
    pinfl              char(14),
    full_name          text,
    birth_date         date,
    phone              text,
    risk_level         text,
    created_at         timestamptz,
    dwh_job_id         text,
    dwh_created_at     timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (client_id);

alter table ods__tranzaxis.client
    owner to gpadmin;
