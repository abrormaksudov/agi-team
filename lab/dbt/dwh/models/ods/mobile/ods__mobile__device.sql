{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="device",
    schema="ods__mobile",
    grants={ "select": [ "l2__mobile__bs" ] }
) }}

select
    device_id::uuid as device_id
    , device_fingerprint
    , platform
    , device_model
    , os_version
    , app_version
    , first_seen_at
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("mobile", "device") }}
