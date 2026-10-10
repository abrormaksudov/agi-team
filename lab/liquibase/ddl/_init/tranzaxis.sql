--liquibase formatted sql

--changeset abror:1
create role l2__tranzaxis__bs;
grant l2__tranzaxis__bs to openmetadata;

create schema ext__tranzaxis;

alter schema ext__tranzaxis
    owner to gpadmin;

grant usage on schema ext__tranzaxis to read__prod_tech;

create schema ods__tranzaxis;

alter schema ods__tranzaxis
    owner to gpadmin;

grant usage on schema ods__tranzaxis to read__prod;
