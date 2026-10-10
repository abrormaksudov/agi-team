{{ config(
    tags="cod",
    meta={ "owner": "data_platform" },
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="overdue_bands",
    schema="dictionary",
    grants={ "select": [ "l3__dictionary__bs" ] }
) }}

select
    band_code
    , band_name
    , min_days::integer as min_days
    , max_days::integer as max_days
    , sort_order::smallint as sort_order
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from (
    values
        ('1_30'::text, 'up to 30 days', 0, 30, 1::smallint)
        , ('31_60', '31 to 60 days', 31, 60, 2)
        , ('61_90', '61 to 90 days', 61, 90, 3)
        , ('91_180', '91 to 180 days', 91, 180, 4)
        , ('181_360', '181 to 360 days', 181, 360, 5)
        , ('361_730', '361 days to 2 years', 361, 730, 6)
        , ('730_plus', 'over 2 years', 731, null::integer, 7)
        , ('total', 'Total overdue', null, null, 99)
) as bands (band_code, band_name, min_days, max_days, sort_order)
