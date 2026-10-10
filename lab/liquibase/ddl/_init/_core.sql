--liquibase formatted sql

--changeset abror:1
create role read__prod;
create role read__prod_tech;

--changeset abror:2
create role openmetadata login password 'openmetadata';
grant read__prod, read__prod_tech to openmetadata;
