{{ config(
    tags="cod",
    meta={ "owner": "data_platform" },
    materialized="incremental",
    incremental_strategy="truncate+insert",
    on_schema_change="fail",
    alias="overdue_report_rows",
    schema="dictionary",
    grants={ "select": [ "l3__dictionary__bs" ] }
) }}

select
    row_code
    , row_name
    , borrower_type
    , contract_type
    , sort_order::smallint as sort_order
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from (
    values
        ('0100'::char(4), 'Loans to individuals, total', 'individual', null::text, 1::smallint)
        , ('0110', 'of which: microloans', 'individual', 'microloan', 2)
        , ('0120', 'of which: credit lines on cards', 'individual', 'credit_line', 3)
        , ('0200', 'Loans to legal entities and individual entrepreneurs', 'legal_entity', null, 4)
) as rows (row_code, row_name, borrower_type, contract_type, sort_order)
