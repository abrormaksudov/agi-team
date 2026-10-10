{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="oper_day",
    on_schema_change="fail",
    alias="card_transaction",
    schema="ods__tranzaxis",
    grants={ "select": [ "l2__tranzaxis__bs" ] }
) }}

select
    transaction_id
    , card_id
    , contract_id
    , oper_day
    , registered_at
    , transaction_kind
    , channel
    , mcc
    , amount
    , currency_code
    , amount_uzs
    , status
    , decline_reason
    , rrn
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("tranzaxis", "card_transaction") }}
where {{ day_filter("oper_day") }}
