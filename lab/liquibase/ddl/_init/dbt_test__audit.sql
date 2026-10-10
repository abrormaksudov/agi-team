--liquibase formatted sql

--changeset abror:1
create schema dbt_test__audit;

alter schema dbt_test__audit
    owner to gpadmin;

grant usage on schema dbt_test__audit to read__prod_tech;
