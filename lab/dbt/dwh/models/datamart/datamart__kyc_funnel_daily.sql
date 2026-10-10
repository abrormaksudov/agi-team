{{ config(
    tags="cod",
    meta={ "owner": "data_platform" },
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="report_date",
    on_schema_change="fail",
    alias="kyc_funnel_daily",
    schema="datamart",
    grants={ "select": [ "l3__datamart__bs" ] }
) }}

{% set report_date = "'" ~ var("oper_day") ~ "'::date" %}

with registered as (
    select
        count(case when (created_at at time zone 'Asia/Tashkent')::date = {{ report_date }} then 1 end)::integer as registrations
    from {{ ref("ods__mobile__app_user") }}
)

, started as (
    select
        count(case when purpose = 'onboarding' then 1 end)::integer as onboarding_started
        , count(case when purpose = 'onboarding' and status = 'HOLD' then 1 end)::integer as onboarding_on_hold
        , count(case when purpose = 'new_device_login' then 1 end)::integer as device_checks
        , count(case when purpose = 'password_reset' then 1 end)::integer as password_reset_checks
    from {{ ref("ods__mobile__kyc_attempt") }}
    where (started_at at time zone 'Asia/Tashkent')::date = {{ report_date }}
)

, completed as (
    select
        count(case when purpose = 'onboarding' and status = 'SUCCESS' then 1 end)::integer as onboarding_succeeded
        , count(case when purpose = 'onboarding' and status = 'FAIL' then 1 end)::integer as onboarding_failed
        , count(case when purpose = 'onboarding' and status = 'REFUSE' then 1 end)::integer as onboarding_refused
    from {{ ref("ods__mobile__kyc_attempt") }}
    where (completed_at at time zone 'Asia/Tashkent')::date = {{ report_date }}
)

, first_contracts as (
    select
        k.client_id
        , min(k.open_date) as first_open_date
    from {{ ref("ods__tranzaxis__contract") }} as k
        inner join {{ ref("ods__tranzaxis__client") }} as c
            on c.client_id = k.client_id
    group by k.client_id
)

, first_products as (
    select count(*)::integer as first_products
    from first_contracts
    where first_open_date = {{ report_date }}
)

select
    {{ report_date }} as report_date
    , r.registrations
    , s.onboarding_started
    , c.onboarding_succeeded
    , c.onboarding_failed
    , c.onboarding_refused
    , s.onboarding_on_hold
    , s.device_checks
    , s.password_reset_checks
    , f.first_products
    , (case
        when c.onboarding_succeeded + c.onboarding_failed + c.onboarding_refused = 0 then null
        else c.onboarding_succeeded::numeric / (c.onboarding_succeeded + c.onboarding_failed + c.onboarding_refused)
    end)::numeric(9, 4) as onboarding_pass_rate
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from registered as r
    cross join started as s
    cross join completed as c
    cross join first_products as f
