--liquibase formatted sql

--changeset abror:1
create table ods__iabs.customer_company
(
    customer_code     char(8),
    company_name      text,
    registration_date date,
    oked_code         char(5),
    legal_form        text,
    director_name     text,
    director_pinfl    char(14),
    dwh_job_id        text,
    dwh_created_at    timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (customer_code);

alter table ods__iabs.customer_company
    owner to gpadmin;
