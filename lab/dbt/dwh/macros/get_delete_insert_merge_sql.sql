{% macro get_delete_insert_merge_sql(target, source, unique_key, dest_columns, incremental_predicates) -%}

    {%- set dest_cols_csv = get_quoted_csv(dest_columns | map(attribute="name")) -%}

    {% if unique_key %}
        {% if unique_key is string %}
            {% set unique_key = [unique_key] %}
        {% endif %}

        delete from {{ target }} as DBT_INTERNAL_DEST
        using (select distinct {{ unique_key | join(', ') }} from {{ source }}) as DBT_INTERNAL_SOURCE
        where
            {% for key in unique_key %}
                {% if not loop.first %}and {% endif %}DBT_INTERNAL_DEST.{{ key }} = DBT_INTERNAL_SOURCE.{{ key }}
            {% endfor %}
            {%- if incremental_predicates %}
                {% for predicate in incremental_predicates %}
                    and {{ predicate }}
                {% endfor %}
            {%- endif -%}
        ;

    {% endif %}

    insert into {{ target }} ({{ dest_cols_csv }})
    (
        select {{ dest_cols_csv }}
        from {{ source }}
    )

{%- endmacro %}
