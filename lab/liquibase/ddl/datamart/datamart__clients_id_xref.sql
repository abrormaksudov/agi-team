--liquibase formatted sql

--changeset abror:1
create table datamart.clients_id_xref
(
    pinfl                      char(14),
    last_name                  text,
    first_name                 text,
    middle_name                text,
    birth_date                 date,
    iabs_customer_id           bigint,
    iabs_customer_code         char(8),
    tranzaxis_client_id        bigint,
    app_user_count             integer,
    primary_app_user_id        uuid,
    app_user_ids               text,
    has_duplicate_app_accounts boolean,
    first_registered_at        timestamptz,
    dwh_job_id                 text,
    dwh_created_at             timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (pinfl);

alter table datamart.clients_id_xref
    owner to gpadmin;
