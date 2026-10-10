{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="exchange_rate",
    schema="ods__iabs",
    grants={ "select": [ "l2__iabs__bs" ] }
) }}

select
    currency_numeric
    , currency_code
    , rate_date
    , rate
    , nominal
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("iabs", "exchange_rate") }}
