{{ config(
    tags="cod",
    meta={ "owner": "data_platform" },
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="oper_day",
    on_schema_change="fail",
    alias="tx_turnover",
    schema="datamart",
    grants={ "select": [ "l3__datamart__bs" ] }
) }}

select
    t.oper_day
    , t.account_id
    , a.account_number
    , a.contract_id
    , c.contract_type
    , a.account_role
    , a.balance_account
    , a.currency_code
    , t.opening_balance
    , t.debit_turnover
    , t.credit_turnover
    , t.closing_balance
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ ref("ods__tranzaxis__account_turnover") }} as t
    inner join {{ ref("ods__tranzaxis__contract_account") }} as a
        on a.account_id = t.account_id
    inner join {{ ref("ods__tranzaxis__contract") }} as c
        on c.contract_id = a.contract_id
where {{ day_filter("t.oper_day") }}
