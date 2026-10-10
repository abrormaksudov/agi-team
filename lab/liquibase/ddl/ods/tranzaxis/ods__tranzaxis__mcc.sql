--liquibase formatted sql

--changeset abror:1
create table ods__tranzaxis.mcc
(
    mcc            char(4),
    description    text,
    category_group text,
    is_cash_like   boolean,
    is_high_risk   boolean,
    dwh_job_id     text,
    dwh_created_at timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (mcc);

alter table ods__tranzaxis.mcc
    owner to gpadmin;
