{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="kyc_attempt",
    schema="ods__mobile",
    grants={ "select": [ "l2__mobile__bs" ] }
) }}

select
    attempt_id::uuid as attempt_id
    , user_id::uuid as user_id
    , purpose
    , mode
    , status
    , last_step
    , fail_reason
    , face_match_score
    , face_photo_ref
    , aml_result
    , started_at
    , completed_at
    , updated_at
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("mobile", "kyc_attempt") }}
