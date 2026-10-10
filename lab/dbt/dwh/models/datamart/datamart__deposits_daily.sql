{{ config(
    tags="cod",
    meta={ "owner": "data_platform" },
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="report_date",
    on_schema_change="fail",
    alias="deposits_daily",
    schema="datamart",
    grants={ "select": [ "l3__datamart__bs" ] }
) }}

{% set report_date = "'" ~ var("oper_day") ~ "'::date" %}

with deposits as (
    select *
    from {{ ref("ods__iabs__deposit_contract") }}
    where start_date <= {{ report_date }}
        and (actual_end_date is null or actual_end_date > {{ report_date }})
)

-- latest balance of the deposit's account on or before the report day; the account is found by account number
, last_balance as (
    select
        d.deposit_id
        , b.closing_balance
        , b.closing_balance_eqv
        , row_number() over (partition by d.deposit_id order by b.oper_day desc) as rn
    from deposits as d
        inner join {{ ref("ods__iabs__account") }} as a
            on a.account_number = d.account_number
        inner join {{ ref("ods__iabs__account_balance") }} as b
            on b.account_id = a.account_id
            and b.oper_day <= {{ report_date }}
)

select
    {{ report_date }} as report_date
    , d.deposit_id
    , d.contract_number
    , d.customer_code
    , d.deposit_type
    , d.currency_code
    , d.amount as contract_amount
    , d.interest_rate
    , d.start_date
    , d.planned_end_date
    , (d.planned_end_date - {{ report_date }})::integer as days_to_maturity
    , coalesce(b.closing_balance, 0)::bigint as balance
    , coalesce(b.closing_balance_eqv, 0)::bigint as balance_uzs
    , round(d.amount * d.interest_rate / 100 * ({{ report_date }} - d.start_date) / 365)::bigint as accrued_interest
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from deposits as d
    left join last_balance as b
        on b.deposit_id = d.deposit_id
        and b.rn = 1
