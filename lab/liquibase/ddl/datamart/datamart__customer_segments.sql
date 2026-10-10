--liquibase formatted sql

--changeset abror:1
create table datamart.customer_segments
(
    snap_dt       date,
    pinfl         char(14),
    cust_cd       char(8),
    age_yrs       integer,
    rgn_cd        char(4),
    inc_band      text,
    prod_cnt      integer,
    spend_30d     bigint,
    txn_cnt_30d   integer,
    avg_tkt       bigint,
    dpd_max       integer,
    seg_cd        text,
    dwh_job_id    text,
    dwh_created_at timestamptz
)
with (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
distributed by (pinfl);

alter table datamart.customer_segments
    owner to gpadmin;
