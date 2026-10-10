{{ config(
    tags="cod",
    meta={ "owner": "data_platform" },
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="oper_day",
    on_schema_change="fail",
    alias="card_operations_daily",
    schema="datamart",
    grants={ "select": [ "l3__datamart__bs" ] }
) }}

select
    t.oper_day
    , c.network
    , t.channel
    , m.category_group as mcc_group
    , t.transaction_kind
    , count(*)::integer as transactions_count
    , sum(case when t.status = 'approved' then 1 else 0 end)::integer as approved_count
    , sum(case when t.status = 'declined' then 1 else 0 end)::integer as declined_count
    , sum(t.amount_uzs)::bigint as amount_uzs
    , sum(case when t.status = 'approved' then t.amount_uzs else 0 end)::bigint as approved_amount_uzs
    , sum(case when t.status = 'approved' and m.is_cash_like then t.amount_uzs else 0 end)::bigint as cash_like_amount_uzs
    , sum(case when m.is_high_risk then 1 else 0 end)::integer as high_risk_count
    , count(distinct t.card_id)::integer as cards_count
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ ref("ods__tranzaxis__card_transaction") }} as t
    inner join {{ ref("ods__tranzaxis__card") }} as c
        on c.card_id = t.card_id
    inner join {{ ref("ods__tranzaxis__mcc") }} as m
        on m.mcc = t.mcc
where {{ day_filter("t.oper_day") }}
group by
    t.oper_day
    , c.network
    , t.channel
    , m.category_group
    , t.transaction_kind
