{% macro get_incremental_truncate_insert_sql(arg_dict) %}

    {% set query %}
        truncate table {{ arg_dict["target_relation"] }}
    {% endset %}

    {% do run_query(query) %}

    {{ return(get_insert_into_sql(arg_dict["target_relation"], arg_dict["temp_relation"], arg_dict["dest_columns"])) }}

{% endmacro %}
