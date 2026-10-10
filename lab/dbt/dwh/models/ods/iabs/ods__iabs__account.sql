{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="account",
    schema="ods__iabs",
    grants={ "select": [ "l2__iabs__bs" ] }
) }}

select
    account_id
    , account_number
    , balance_account
    , currency_code
    , customer_code
    , account_type
    , status
    , open_date
    , close_date
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("iabs", "account") }}
