--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__tranzaxis.credit_line_cycle;

create readable external table ext__tranzaxis.credit_line_cycle
(
    contract_id        bigint,
    statement_date     date,
    cycle_start_date   date,
    due_date           date,
    grace_end_date     date,
    statement_balance  bigint,
    min_payment        bigint,
    used_limit         bigint,
    paid_amount        bigint,
    overdue_start_date date,
    last_payment_date  date
)
location ('pxf://tx.credit_line_cycle?profile=jdbc&server=tranzaxis')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__tranzaxis.credit_line_cycle
    owner to gpadmin;
