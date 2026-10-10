--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__iabs.customer_company;

create readable external table ext__iabs.customer_company
(
    customer_code     char(8),
    company_name      text,
    registration_date date,
    oked_code         char(5),
    legal_form        text,
    director_name     text,
    director_pinfl    char(14)
)
location ('pxf://core.customer_company?profile=jdbc&server=iabs')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__iabs.customer_company
    owner to gpadmin;
