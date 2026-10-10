{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="balance_account",
    schema="ods__iabs",
    grants={ "select": [ "l2__iabs__bs" ] }
) }}

select
    code
    , name
    , account_class
    , section
    , side
    , is_contra
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("iabs", "balance_account") }}
