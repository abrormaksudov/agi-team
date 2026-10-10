{{ config(
    tags="cod",
    meta={ "owner": "data_platform" },
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="report_date",
    on_schema_change="fail",
    alias="metrics_daily",
    schema="datamart",
    grants={ "select": [ "l3__datamart__bs" ] }
) }}

{% set report_date = "'" ~ var("oper_day") ~ "'::date" %}

with loans as (
    select *
    from {{ ref("datamart__contract_classification_daily") }}
    where report_date = {{ report_date }}
)

, ledger_today as (
    select *
    from {{ ref("datamart__tx_turnover") }}
    where oper_day = {{ report_date }}
)

, credit_lines as (
    select sum(credit_limit) as total_limit
    from {{ ref("ods__tranzaxis__contract") }}
    where contract_type = 'credit_line'
        and status in ('active', 'blocked')
        and open_date <= {{ report_date }}
)

, deposits as (
    select *
    from {{ ref("datamart__deposits_daily") }}
    where report_date = {{ report_date }}
)

, cards_today as (
    select *
    from {{ ref("datamart__card_operations_daily") }}
    where oper_day = {{ report_date }}
)

, funnel as (
    select *
    from {{ ref("datamart__kyc_funnel_daily") }}
    where report_date = {{ report_date }}
)

-- one row per metric: (metric_key, dimension, period, value, unit); amounts converted from tiyin to UZS
, metrics as (
    select 'gross_loan_portfolio' as metric_key, null::text as dimension, 'stock' as period
        , sum(principal_balance + overdue_principal_balance) / 100.0 as value, 'UZS' as unit
    from loans
    where classification <> 'written_off'

    union all
    select 'overdue_portfolio', null, 'stock'
        , sum(overdue_principal_balance + overdue_interest_balance) / 100.0, 'UZS'
    from loans

    union all
    select 'overdue_portfolio', overdue_band, 'stock'
        , sum(overdue_principal_balance + overdue_interest_balance) / 100.0, 'UZS'
    from loans
    where overdue_band is not null
    group by overdue_band

    union all
    select 'npl_90_ratio', null, 'stock'
        , sum(case when days_past_due > 90 then principal_balance + overdue_principal_balance else 0 end)
            / nullif(sum(principal_balance + overdue_principal_balance), 0), 'ratio'
    from loans
    where classification <> 'written_off'

    union all
    select 'write_offs', null, 'day'
        , coalesce(sum(debit_turnover), 0) / 100.0, 'UZS'
    from ledger_today
    where account_role = 'write_off'

    union all
    select 'microloan_disbursements_volume', null, 'day'
        , coalesce(sum(debit_turnover), 0) / 100.0, 'UZS'
    from ledger_today
    where account_role = 'principal'
        and contract_type = 'microloan'

    union all
    select 'microloan_disbursements_count', null, 'day'
        , count(distinct contract_id), 'contracts'
    from ledger_today
    where account_role = 'principal'
        and contract_type = 'microloan'
        and debit_turnover > 0

    union all
    select 'credit_line_utilisation', null, 'stock'
        , (select sum(principal_balance + overdue_principal_balance) from loans where contract_type = 'credit_line')
            / nullif(total_limit, 0), 'ratio'
    from credit_lines

    union all
    select 'term_deposit_balance', null, 'stock'
        , coalesce(sum(balance_uzs), 0) / 100.0, 'UZS'
    from deposits

    union all
    select 'active_depositors', null, 'stock'
        , count(distinct customer_code), 'customers'
    from deposits

    union all
    select 'deposit_interest_expense', null, 'day'
        , coalesce(sum(balance_uzs * interest_rate / 100 / 365), 0) / 100.0, 'UZS'
    from deposits

    union all
    select 'card_payment_volume', null, 'day'
        , coalesce(sum(approved_amount_uzs - cash_like_amount_uzs), 0) / 100.0, 'UZS'
    from cards_today

    union all
    select 'card_decline_rate', null, 'day'
        , sum(declined_count)::numeric / nullif(sum(transactions_count), 0), 'ratio'
    from cards_today

    union all
    select 'cards_issued', null, 'day'
        , count(*), 'cards'
    from {{ ref("ods__tranzaxis__card") }}
    where (issued_at at time zone 'Asia/Tashkent')::date = {{ report_date }}

    union all
    select 'kyc_pass_rate', null, 'day'
        , onboarding_pass_rate, 'ratio'
    from funnel

    union all
    select 'active_customers', null, 'rolling_30_days'
        , count(distinct c.client_id), 'customers'
    from {{ ref("ods__tranzaxis__card_transaction") }} as t
        inner join {{ ref("ods__tranzaxis__card") }} as c
            on c.card_id = t.card_id
    where t.oper_day between {{ report_date }} - 29 and {{ report_date }}
)

select
    {{ report_date }} as report_date
    , metric_key
    , dimension
    , period
    , value::numeric(24, 4) as value
    , unit
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from metrics
