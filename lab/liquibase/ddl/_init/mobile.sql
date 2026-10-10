--liquibase formatted sql

--changeset abror:1
create role l2__mobile__bs;
grant l2__mobile__bs to openmetadata;

create schema ext__mobile;

alter schema ext__mobile
    owner to gpadmin;

grant usage on schema ext__mobile to read__prod_tech;

create schema ods__mobile;

alter schema ods__mobile
    owner to gpadmin;

grant usage on schema ods__mobile to read__prod;
