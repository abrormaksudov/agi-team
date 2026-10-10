{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="deposit_contract",
    schema="ods__iabs",
    grants={ "select": [ "l2__iabs__bs" ] }
) }}

select
    deposit_id
    , contract_number
    , customer_code
    , deposit_type
    , currency_code
    , amount
    , interest_rate
    , start_date
    , planned_end_date
    , account_number
    , actual_end_date
    , state
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("iabs", "deposit_contract") }}
