--liquibase formatted sql

--changeset abror:1
create table ods__iabs.customer_individual
(
    customer_code   char(8),
    pinfl           char(14),
    last_name       text,
    first_name      text,
    middle_name     text,
    birth_date      date,
    gender          char(1),
    passport_series char(2),
    passport_number char(7),
    passport_issued date,
    district_code   char(7),
    address         text,
    phone           text,
    monthly_income  bigint,
    dwh_job_id      text,
    dwh_created_at  timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (customer_code);

alter table ods__iabs.customer_individual
    owner to gpadmin;
