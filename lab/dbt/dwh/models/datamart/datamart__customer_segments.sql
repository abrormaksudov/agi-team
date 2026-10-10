{{ config(
    tags="cod",
    meta={ "owner": "data_platform" },
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="customer_segments",
    schema="datamart",
    grants={ "select": [ "l3__datamart__bs" ] }
) }}

{% set report_date = "'" ~ var("oper_day") ~ "'::date" %}

with people as (
    select
        x.pinfl
        , x.iabs_customer_code
        , x.birth_date
    from {{ ref("datamart__clients_id_xref") }} as x
    where x.iabs_customer_code is not null
)

, individuals as (
    select
        i.customer_code
        , i.monthly_income
        , d.region_code
    from {{ ref("ods__iabs__customer_individual") }} as i
        left join {{ ref("ods__iabs__district") }} as d
            on d.district_code = i.district_code
)

, contracts_by_person as (
    select
        c.pinfl
        , count(k.contract_id)::integer as prod_cnt
    from {{ ref("ods__tranzaxis__client") }} as c
        left join {{ ref("ods__tranzaxis__contract") }} as k
            on k.client_id = c.client_id
            and k.status <> 'closed'
    group by c.pinfl
)

, spend_by_person as (
    select
        c.pinfl
        , sum(t.amount_uzs)::bigint as spend_30d
        , count(*)::integer as txn_cnt_30d
    from {{ ref("ods__tranzaxis__client") }} as c
        inner join {{ ref("ods__tranzaxis__card") }} as k
            on k.client_id = c.client_id
        inner join {{ ref("ods__tranzaxis__card_transaction") }} as t
            on t.card_id = k.card_id
    where t.status = 'approved'
        and t.oper_day between {{ report_date }} - 29 and {{ report_date }}
    group by c.pinfl
)

, dpd_by_person as (
    select
        pinfl
        , max_days_past_due
    from {{ ref("datamart__portfolio_daily") }}
    where report_date = {{ report_date }}
)

, scored as (
    select
        {{ report_date }} as snap_dt
        , p.pinfl
        , p.iabs_customer_code as cust_cd
        , date_part('year', age({{ report_date }}, p.birth_date))::integer as age_yrs
        , i.region_code as rgn_cd
        , case
            when i.monthly_income is null then 'unk'
            when i.monthly_income < 300000000 then 'low'
            when i.monthly_income < 1000000000 then 'mid'
            else 'high'
        end as inc_band
        , coalesce(cp.prod_cnt, 0)::integer as prod_cnt
        , coalesce(s.spend_30d, 0)::bigint as spend_30d
        , coalesce(s.txn_cnt_30d, 0)::integer as txn_cnt_30d
        , case
            when coalesce(s.txn_cnt_30d, 0) = 0 then 0::bigint
            else (s.spend_30d / s.txn_cnt_30d)::bigint
        end as avg_tkt
        , coalesce(d.max_days_past_due, 0)::integer as dpd_max
    from people as p
        left join individuals as i
            on i.customer_code = p.iabs_customer_code
        left join contracts_by_person as cp
            on cp.pinfl = p.pinfl
        left join spend_by_person as s
            on s.pinfl = p.pinfl
        left join dpd_by_person as d
            on d.pinfl = p.pinfl
)

select
    snap_dt
    , pinfl
    , cust_cd
    , age_yrs
    , rgn_cd
    , inc_band
    , prod_cnt
    , spend_30d
    , txn_cnt_30d
    , avg_tkt
    , dpd_max
    , case
        when dpd_max > 30 then 'RISK'
        when inc_band = 'high' and spend_30d > 500000000 then 'VIP'
        when txn_cnt_30d >= 10 then 'ACTV'
        when txn_cnt_30d = 0 and prod_cnt <= 1 then 'DRMT'
        else 'MASS'
    end as seg_cd
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from scored
