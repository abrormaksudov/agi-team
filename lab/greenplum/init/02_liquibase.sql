-- Liquibase keeps its changelog journal here; every other schema comes from liquibase/ddl.
create schema liquibase;

alter schema liquibase
    owner to gpadmin;
