{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="contract",
    schema="ods__tranzaxis",
    grants={ "select": [ "l2__tranzaxis__bs" ] }
) }}

select
    contract_id
    , client_id
    , contract_type
    , product_code
    , status
    , currency_code
    , credit_limit
    , interest_rate
    , term_months
    , principal_amount
    , settlement_account
    , open_date
    , close_date
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("tranzaxis", "contract") }}
