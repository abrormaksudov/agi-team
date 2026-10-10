--liquibase formatted sql

--changeset abror:1
create role l3__datamart_regtech__bs;
grant l3__datamart_regtech__bs to openmetadata;

create schema datamart_regtech;

alter schema datamart_regtech
    owner to gpadmin;

grant usage on schema datamart_regtech to read__prod;
