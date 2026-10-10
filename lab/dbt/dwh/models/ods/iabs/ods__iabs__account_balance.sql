{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="oper_day",
    on_schema_change="fail",
    alias="account_balance",
    schema="ods__iabs",
    grants={ "select": [ "l2__iabs__bs" ] }
) }}

select
    account_id
    , oper_day
    , opening_balance
    , debit_turnover
    , credit_turnover
    , closing_balance
    , closing_balance_eqv
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("iabs", "account_balance") }}
where {{ day_filter("oper_day") }}
