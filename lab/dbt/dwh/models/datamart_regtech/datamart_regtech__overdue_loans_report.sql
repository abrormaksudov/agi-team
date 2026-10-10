{{ config(
    tags="cod",
    meta={ "owner": "regulatory_reporting" },
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="report_date",
    on_schema_change="fail",
    alias="overdue_loans_report",
    schema="datamart_regtech",
    grants={ "select": [ "l3__datamart_regtech__bs" ] }
) }}

{% set report_date = "'" ~ var("oper_day") ~ "'::date" %}

-- the report is as of the last calendar day of a month; other days produce nothing
with report_day as (
    select {{ report_date }} as report_date
    where {{ report_date }} = (date_trunc('month', {{ report_date }}) + interval '1 month - 1 day')::date
)

, overdue_loans as (
    select
        contract_type
        , overdue_band
        , overdue_principal_balance
        , overdue_interest_balance
    from {{ ref("datamart__contract_classification_daily") }}
    where report_date = {{ report_date }}
        and classification = 'overdue'
)

, report_rows as (
    select row_code, row_name, borrower_type, contract_type, sort_order
    from {{ ref("dictionary__overdue_report_rows") }}
)

, bands as (
    select band_code, band_name, sort_order
    from {{ ref("dictionary__overdue_bands") }}
)

-- every retail loan is an individual's; a row without a contract type takes every product
, by_band as (
    select
        r.row_code
        , l.overdue_band as band_code
        , count(*) as contracts_count
        , sum(l.overdue_principal_balance) as overdue_principal
        , sum(l.overdue_interest_balance) as overdue_interest
    from overdue_loans as l
        inner join report_rows as r
            on r.borrower_type = 'individual'
            and (r.contract_type is null or r.contract_type = l.contract_type)
    group by r.row_code, l.overdue_band
)

, with_total as (
    select row_code, band_code, contracts_count, overdue_principal, overdue_interest
    from by_band
    union all
    select row_code, 'total', sum(contracts_count), sum(overdue_principal), sum(overdue_interest)
    from by_band
    group by row_code
)

select
    d.report_date
    , r.row_code
    , r.row_name
    , b.band_code
    , b.band_name
    , coalesce(t.contracts_count, 0)::integer as contracts_count
    , (coalesce(t.overdue_principal, 0) / 100000.0)::numeric(20, 5) as overdue_principal_thousand_uzs
    , (coalesce(t.overdue_interest, 0) / 100000.0)::numeric(20, 5) as overdue_interest_thousand_uzs
    , ((coalesce(t.overdue_principal, 0) + coalesce(t.overdue_interest, 0)) / 100000.0)::numeric(20, 5) as overdue_total_thousand_uzs
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from report_day as d
    cross join report_rows as r
    cross join bands as b
    left join with_total as t
        on t.row_code = r.row_code
        and t.band_code = b.band_code
