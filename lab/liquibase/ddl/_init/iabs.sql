--liquibase formatted sql

--changeset abror:1
create role l2__iabs__bs;
grant l2__iabs__bs to openmetadata;

create schema ext__iabs;

alter schema ext__iabs
    owner to gpadmin;

grant usage on schema ext__iabs to read__prod_tech;

create schema ods__iabs;

alter schema ods__iabs
    owner to gpadmin;

grant usage on schema ods__iabs to read__prod;
