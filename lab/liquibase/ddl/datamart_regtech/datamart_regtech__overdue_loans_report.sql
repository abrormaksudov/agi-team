--liquibase formatted sql

--changeset abror:1
create table datamart_regtech.overdue_loans_report
(
    report_date                    date,
    row_code                       char(4),
    row_name                       text,
    band_code                      text,
    band_name                      text,
    contracts_count                integer,
    overdue_principal_thousand_uzs numeric(20, 5),
    overdue_interest_thousand_uzs  numeric(20, 5),
    overdue_total_thousand_uzs     numeric(20, 5),
    dwh_job_id                     text,
    dwh_created_at                 timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (row_code);

alter table datamart_regtech.overdue_loans_report
    owner to gpadmin;
