--liquibase formatted sql

--changeset abror:1
create schema dbt;

alter schema dbt
    owner to gpadmin;

grant usage on schema dbt to read__prod_tech;
