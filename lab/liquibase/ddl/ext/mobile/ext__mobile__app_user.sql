--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__mobile.app_user;

create readable external table ext__mobile.app_user
(
    user_id            text,
    phone_number       text,
    email              text,
    first_name         text,
    last_name          text,
    middle_name        text,
    date_of_birth      date,
    gender             char(1),
    pinfl              char(14),
    lang               text,
    account_status     text,
    verification_level text,
    core_customer_id   bigint,
    created_at         timestamptz,
    updated_at         timestamptz
)
location ('pxf://users.app_user?profile=jdbc&server=mobile')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__mobile.app_user
    owner to gpadmin;
