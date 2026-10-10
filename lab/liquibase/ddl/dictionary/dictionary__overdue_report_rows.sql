--liquibase formatted sql

--changeset abror:1
create table dictionary.overdue_report_rows
(
    row_code       char(4),
    row_name       text,
    borrower_type  text,
    contract_type  text,
    sort_order     smallint,
    dwh_job_id     text,
    dwh_created_at timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed replicated;

alter table dictionary.overdue_report_rows
    owner to gpadmin;
