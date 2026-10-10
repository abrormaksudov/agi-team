{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="oper_day",
    on_schema_change="fail",
    alias="account_turnover",
    schema="ods__tranzaxis",
    grants={ "select": [ "l2__tranzaxis__bs" ] }
) }}

select
    account_id
    , oper_day
    , opening_balance
    , debit_turnover
    , credit_turnover
    , closing_balance
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("tranzaxis", "account_turnover") }}
where {{ day_filter("oper_day") }}
