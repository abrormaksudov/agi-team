--liquibase formatted sql

--changeset abror:1 runAlways:true
drop external table if exists ext__iabs.operating_day;

create readable external table ext__iabs.operating_day
(
    oper_day      date,
    prev_oper_day date,
    next_oper_day date,
    is_holiday    boolean,
    is_weekend    boolean,
    day_status    text
)
location ('pxf://core.operating_day?profile=jdbc&server=iabs')
format 'custom' (formatter='pxfwritable_import');

alter external table ext__iabs.operating_day
    owner to gpadmin;
