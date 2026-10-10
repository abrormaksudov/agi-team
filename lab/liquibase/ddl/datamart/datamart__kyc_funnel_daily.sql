--liquibase formatted sql

--changeset abror:1
create table datamart.kyc_funnel_daily
(
    report_date             date,
    registrations           integer,
    onboarding_started      integer,
    onboarding_succeeded    integer,
    onboarding_failed       integer,
    onboarding_refused      integer,
    onboarding_on_hold      integer,
    device_checks           integer,
    password_reset_checks   integer,
    first_products          integer,
    onboarding_pass_rate    numeric(9, 4),
    dwh_job_id              text,
    dwh_created_at          timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (report_date);

alter table datamart.kyc_funnel_daily
    owner to gpadmin;
