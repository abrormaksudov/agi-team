--liquibase formatted sql

--changeset abror:1
create table ods__mobile.app_user
(
    user_id            uuid,
    phone_number       text,
    email              text,
    first_name         text,
    last_name          text,
    middle_name        text,
    date_of_birth      date,
    gender             char(1),
    pinfl              char(14),
    lang               text,
    account_status     text,
    verification_level text,
    core_customer_id   bigint,
    created_at         timestamptz,
    updated_at         timestamptz,
    dwh_job_id         text,
    dwh_created_at     timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (user_id);

alter table ods__mobile.app_user
    owner to gpadmin;
