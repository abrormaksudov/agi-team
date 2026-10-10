--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__tranzaxis.delinquency_history;

create readable external table ext__tranzaxis.delinquency_history
(
    contract_id    bigint,
    effective_date date,
    state          text,
    previous_state text,
    days_past_due  integer,
    recorded_at    timestamptz
)
location ('pxf://tx.delinquency_history?profile=jdbc&server=tranzaxis')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__tranzaxis.delinquency_history
    owner to gpadmin;
