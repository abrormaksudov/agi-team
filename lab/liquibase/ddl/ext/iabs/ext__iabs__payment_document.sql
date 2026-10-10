--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__iabs.payment_document;

create readable external table ext__iabs.payment_document
(
    document_id     bigint,
    document_date   date,
    oper_day        date,
    payer_account   char(20),
    payer_bank_code char(5),
    payer_name      text,
    payee_account   char(20),
    payee_bank_code char(5),
    payee_name      text,
    amount          bigint,
    currency_code   char(3),
    purpose         text,
    state           text,
    created_at      timestamptz
)
location ('pxf://core.payment_document?profile=jdbc&server=iabs')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__iabs.payment_document
    owner to gpadmin;
