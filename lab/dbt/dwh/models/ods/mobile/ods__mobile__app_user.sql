{{ config(
    tags="cod",
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="app_user",
    schema="ods__mobile",
    grants={ "select": [ "l2__mobile__bs" ] }
) }}

select
    user_id::uuid as user_id
    , phone_number
    , email
    , first_name
    , last_name
    , middle_name
    , date_of_birth
    , gender
    , pinfl
    , lang
    , account_status
    , verification_level
    , core_customer_id
    , created_at
    , updated_at
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from {{ source("mobile", "app_user") }}
