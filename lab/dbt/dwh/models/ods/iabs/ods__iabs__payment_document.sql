{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="oper_day",
    on_schema_change="fail",
    alias="payment_document",
    schema="ods__iabs",
    grants={ "select": [ "l2__iabs__bs" ] }
) }}

select
    document_id
    , document_date
    , oper_day
    , payer_account
    , payer_bank_code
    , payer_name
    , payee_account
    , payee_bank_code
    , payee_name
    , amount
    , currency_code
    , purpose
    , state
    , created_at
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("iabs", "payment_document") }}
where {{ day_filter("oper_day") }}
