{{ config(
    tags="cod",
    meta={ "owner": "data_platform" },
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="report_date",
    on_schema_change="fail",
    alias="portfolio_daily",
    schema="datamart",
    grants={ "select": [ "l3__datamart__bs" ] }
) }}

{% set report_date = "'" ~ var("oper_day") ~ "'::date" %}

with contracts as (
    select *
        -- worst first, to pick the borrower's worst class
        , case classification
            when 'written_off' then 1
            when 'overdue' then 2
            when 'repaying_carried_balance' then 3
            when 'interest_only' then 4
            when 'principal_only' then 5
            when 'microloan_first_period' then 6
            when 'performing' then 7
            when 'dormant' then 8
        end as severity
    from {{ ref("datamart__contract_classification_daily") }}
    where report_date = {{ report_date }}
)

, borrowers as (
    select
        client_id
        , count(*) as contracts_count
        , sum(case when contract_type = 'credit_line' then 1 else 0 end) as credit_lines_count
        , sum(case when contract_type = 'microloan' then 1 else 0 end) as microloans_count
        , sum(principal_balance)::bigint as principal_balance
        , sum(overdue_principal_balance)::bigint as overdue_principal_balance
        , sum(overdue_interest_balance)::bigint as overdue_interest_balance
        , sum(penalty_balance)::bigint as penalty_balance
        , max(days_past_due) as max_days_past_due
        , min(severity) as worst_severity
    from contracts
    group by client_id
)

, worst as (
    select distinct client_id, classification, severity
    from contracts
)

select
    {{ report_date }} as report_date
    , b.client_id
    , c.pinfl
    , c.core_customer_code as iabs_customer_code
    , b.contracts_count::integer as contracts_count
    , b.credit_lines_count::integer as credit_lines_count
    , b.microloans_count::integer as microloans_count
    , b.principal_balance
    , b.overdue_principal_balance
    , b.overdue_interest_balance
    , b.penalty_balance
    , b.principal_balance + b.overdue_principal_balance + b.overdue_interest_balance + b.penalty_balance as total_exposure
    , b.max_days_past_due
    , w.classification as worst_classification
    , b.max_days_past_due > 90 as is_npl
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from borrowers as b
    inner join worst as w
        on w.client_id = b.client_id
        and w.severity = b.worst_severity
    left join {{ ref("ods__tranzaxis__client") }} as c
        on c.client_id = b.client_id
