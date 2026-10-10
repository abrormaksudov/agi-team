{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="effective_date",
    on_schema_change="fail",
    alias="delinquency_history",
    schema="ods__tranzaxis",
    grants={ "select": [ "l2__tranzaxis__bs" ] }
) }}

select
    contract_id
    , effective_date
    , state
    , previous_state
    , days_past_due
    , recorded_at
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("tranzaxis", "delinquency_history") }}
where {{ day_filter("effective_date") }}
