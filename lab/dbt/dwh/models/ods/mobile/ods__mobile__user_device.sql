{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="user_device",
    schema="ods__mobile",
    grants={ "select": [ "l2__mobile__bs" ] }
) }}

select
    user_device_id
    , user_id::uuid as user_id
    , device_id::uuid as device_id
    , is_trusted
    , is_blocked
    , is_rooted
    , malware_detected
    , malware_scan_at
    , first_linked_at
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("mobile", "user_device") }}
