{{ config(
    tags="cod",
    meta={ "owner": "data_platform" },
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="clients_id_xref",
    schema="datamart",
    grants={ "select": [ "l3__datamart__bs" ] }
) }}

with iabs_people as (
    select
        i.pinfl
        , i.last_name
        , i.first_name
        , i.middle_name
        , i.birth_date
        , c.customer_id
        , i.customer_code
    from {{ ref("ods__iabs__customer_individual") }} as i
        inner join {{ ref("ods__iabs__customer") }} as c
            on c.customer_code = i.customer_code
)

, tx_clients as (
    select pinfl, client_id
    from {{ ref("ods__tranzaxis__client") }}
)

, app_accounts as (
    select
        pinfl
        , count(*) as app_user_count
        , min(created_at) as first_registered_at
        , string_agg(user_id::text, ',' order by created_at) as app_user_ids
    from {{ ref("ods__mobile__app_user") }}
    group by pinfl
)

-- the newest app account of a person is the one in use; older ones are duplicates
, latest_app_account as (
    select
        pinfl
        , user_id
        , last_name
        , first_name
        , middle_name
        , date_of_birth
        , row_number() over (partition by pinfl order by created_at desc) as rn
    from {{ ref("ods__mobile__app_user") }}
)

, people as (
    select pinfl from iabs_people
    union
    select pinfl from tx_clients
    union
    select pinfl from app_accounts
)

select
    p.pinfl
    , coalesce(i.last_name, u.last_name) as last_name
    , coalesce(i.first_name, u.first_name) as first_name
    , coalesce(i.middle_name, u.middle_name) as middle_name
    , coalesce(i.birth_date, u.date_of_birth) as birth_date
    , i.customer_id as iabs_customer_id
    , i.customer_code as iabs_customer_code
    , t.client_id as tranzaxis_client_id
    , coalesce(a.app_user_count, 0)::integer as app_user_count
    , u.user_id as primary_app_user_id
    , a.app_user_ids
    , coalesce(a.app_user_count, 0) > 1 as has_duplicate_app_accounts
    , a.first_registered_at
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from people as p
    left join iabs_people as i
        on i.pinfl = p.pinfl
    left join tx_clients as t
        on t.pinfl = p.pinfl
    left join app_accounts as a
        on a.pinfl = p.pinfl
    left join latest_app_account as u
        on u.pinfl = p.pinfl
        and u.rn = 1
