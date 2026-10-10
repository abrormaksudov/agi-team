{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="operating_day",
    schema="ods__iabs",
    grants={ "select": [ "l2__iabs__bs" ] }
) }}

select
    oper_day
    , prev_oper_day
    , next_oper_day
    , is_holiday
    , is_weekend
    , day_status
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("iabs", "operating_day") }}
