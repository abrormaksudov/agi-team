--liquibase formatted sql

--changeset abror:1
create schema datamart;

alter schema datamart
    owner to gpadmin;

grant usage on schema datamart to read__prod;

--changeset abror:2
create role l3__datamart__bs;
grant l3__datamart__bs to openmetadata;
