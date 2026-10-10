{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="customer_individual",
    schema="ods__iabs",
    grants={ "select": [ "l2__iabs__bs" ] }
) }}

select
    customer_code
    , pinfl
    , last_name
    , first_name
    , middle_name
    , birth_date
    , gender
    , passport_series
    , passport_number
    , passport_issued
    , district_code
    , address
    , phone
    , monthly_income
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("iabs", "customer_individual") }}
