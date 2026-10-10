{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="credit_line_cycle",
    schema="ods__tranzaxis",
    grants={ "select": [ "l2__tranzaxis__bs" ] }
) }}

select
    contract_id
    , statement_date
    , cycle_start_date
    , due_date
    , grace_end_date
    , statement_balance
    , min_payment
    , used_limit
    , paid_amount
    , overdue_start_date
    , last_payment_date
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("tranzaxis", "credit_line_cycle") }}
