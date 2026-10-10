--liquibase formatted sql

--changeset abror:1
create table ods__mobile.kyc_attempt
(
    attempt_id       uuid,
    user_id          uuid,
    purpose          text,
    mode             text,
    status           text,
    last_step        text,
    fail_reason      text,
    face_match_score numeric(4, 3),
    face_photo_ref   text,
    aml_result       text,
    started_at       timestamptz,
    completed_at     timestamptz,
    updated_at       timestamptz,
    dwh_job_id       text,
    dwh_created_at   timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (attempt_id);

alter table ods__mobile.kyc_attempt
    owner to gpadmin;
