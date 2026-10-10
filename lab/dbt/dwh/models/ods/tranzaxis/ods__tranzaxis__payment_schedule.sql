{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="payment_schedule",
    schema="ods__tranzaxis",
    grants={ "select": [ "l2__tranzaxis__bs" ] }
) }}

select
    schedule_line_id
    , contract_id
    , schedule_revision
    , debt_kind
    , due_date
    , scheduled_amount
    , paid_amount
    , unpaid_amount
    , last_paid_date
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("tranzaxis", "payment_schedule") }}
