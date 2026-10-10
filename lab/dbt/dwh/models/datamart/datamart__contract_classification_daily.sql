{{ config(
    tags="cod",
    meta={ "owner": "data_platform" },
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="report_date",
    on_schema_change="fail",
    alias="contract_classification_daily",
    schema="datamart",
    grants={ "select": [ "l3__datamart__bs" ] }
) }}

{% set report_date = "'" ~ var("oper_day") ~ "'::date" %}

with today as (
    select *
    from {{ ref("datamart__contract_classification_tech") }}
    where report_date = {{ report_date }}
)

-- stateful: yesterday's row of this same table carries the clocks forward
, yesterday as (
    select
        contract_id
        , classification
        , days_in_classification
        , consecutive_overdue_days
    from {{ this }}
    where report_date = {{ report_date }} - 1
)

-- first match wins
, classified as (
    select
        t.*
        , case
            when t.overdue_principal_balance + t.overdue_interest_balance > 0 then 'overdue'
            when t.written_off_principal + t.written_off_interest > 0 then 'written_off'
            when t.contract_type = 'credit_line' and t.principal_balance > 0 and t.interest_balance > 0
                then 'repaying_carried_balance'
            when t.principal_balance = 0 and t.interest_balance > 0 then 'interest_only'
            when t.contract_type = 'credit_line' and t.principal_balance > 0 then 'principal_only'
            when t.contract_type = 'credit_line' and coalesce(t.last_draw_date, t.open_date) < {{ report_date }} - 90
                then 'dormant'
            when t.contract_type = 'microloan' and {{ report_date }} <= t.first_due_date then 'microloan_first_period'
            else 'performing'
        end as classification
    from today as t
)

select
    c.report_date
    , c.contract_id
    , c.client_id
    , c.contract_type
    , c.product_code
    , c.classification
    , y.classification as previous_classification
    , case
        when y.classification = c.classification then y.days_in_classification + 1
        else 1
    end as days_in_classification
    , c.days_past_due
    , case
        when c.classification <> 'overdue' then 0
        when y.classification = 'overdue' then y.consecutive_overdue_days + 1
        when y.contract_id is null then c.days_past_due + 1
        else 1
    end as consecutive_overdue_days
    , case
        when c.classification <> 'overdue' then null
        when c.days_past_due <= 30 then '1_30'
        when c.days_past_due <= 60 then '31_60'
        when c.days_past_due <= 90 then '61_90'
        when c.days_past_due <= 180 then '91_180'
        when c.days_past_due <= 360 then '181_360'
        when c.days_past_due <= 730 then '361_730'
        else '730_plus'
    end as overdue_band
    , c.contract_type = 'credit_line'
        and (c.first_due_date is null or {{ report_date }} <= c.first_due_date) as is_first_grace_period
    , c.principal_balance
    , c.interest_balance
    , c.overdue_principal_balance
    , c.overdue_interest_balance
    , c.penalty_balance
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from classified as c
    left join yesterday as y
        on y.contract_id = c.contract_id
