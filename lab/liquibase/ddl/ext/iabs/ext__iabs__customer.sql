--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__iabs.customer;

create readable external table ext__iabs.customer
(
    customer_id   bigint,
    customer_code char(8),
    customer_type text,
    tax_id        char(9),
    branch_code   char(5),
    status        text,
    open_date     date,
    close_date    date,
    updated_at    timestamptz
)
location ('pxf://core.customer?profile=jdbc&server=iabs')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__iabs.customer
    owner to gpadmin;
