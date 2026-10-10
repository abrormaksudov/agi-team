--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__mobile.kyc_attempt;

create readable external table ext__mobile.kyc_attempt
(
    attempt_id       text,
    user_id          text,
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
    updated_at       timestamptz
)
location ('pxf://kyc.kyc_attempt?profile=jdbc&server=mobile')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__mobile.kyc_attempt
    owner to gpadmin;
