--liquibase formatted sql

--changeset abror:1
create table ods__iabs.customer
(
    customer_id    bigint,
    customer_code  char(8),
    customer_type  text,
    tax_id         char(9),
    branch_code    char(5),
    status         text,
    open_date      date,
    close_date     date,
    updated_at     timestamptz,
    dwh_job_id     text,
    dwh_created_at timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (customer_id);

alter table ods__iabs.customer
    owner to gpadmin;
