--liquibase formatted sql

--changeset abror:1
create schema dictionary;

alter schema dictionary
    owner to gpadmin;

grant usage on schema dictionary to read__prod;

--changeset abror:2
create role l3__dictionary__bs;
grant l3__dictionary__bs to openmetadata;
