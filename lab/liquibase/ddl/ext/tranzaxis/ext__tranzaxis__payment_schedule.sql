--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__tranzaxis.payment_schedule;

create readable external table ext__tranzaxis.payment_schedule
(
    schedule_line_id  bigint,
    contract_id       bigint,
    schedule_revision smallint,
    debt_kind         text,
    due_date          date,
    scheduled_amount  bigint,
    paid_amount       bigint,
    unpaid_amount     bigint,
    last_paid_date    date
)
location ('pxf://tx.payment_schedule?profile=jdbc&server=tranzaxis')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__tranzaxis.payment_schedule
    owner to gpadmin;
