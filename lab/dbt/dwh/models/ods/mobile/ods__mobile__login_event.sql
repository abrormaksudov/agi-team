{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="event_id",
    on_schema_change="fail",
    alias="login_event",
    schema="ods__mobile",
    grants={ "select": [ "l2__mobile__bs" ] }
) }}

select
    event_id
    , user_id::uuid as user_id
    , device_id::uuid as device_id
    , session_id::uuid as session_id
    , event_type
    , auth_result
    , ip_address::inet as ip_address
    , app_version
    , occurred_at
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("mobile", "login_event") }}
where {{ ts_window_filter("occurred_at") }}
