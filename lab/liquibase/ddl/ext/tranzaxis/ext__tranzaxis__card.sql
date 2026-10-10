--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__tranzaxis.card;

create readable external table ext__tranzaxis.card
(
    card_id      bigint,
    contract_id  bigint,
    client_id    bigint,
    product_type text,
    network      text,
    status       text,
    masked_pan   text,
    issued_at    timestamptz,
    expiry_date  date,
    pan_hash     char(64)
)
location ('pxf://tx.card?profile=jdbc&server=tranzaxis')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__tranzaxis.card
    owner to gpadmin;
