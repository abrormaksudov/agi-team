{#
    Rows of the operating day being closed. On the history day (the lab's first operating day) also every
    earlier day: its source files carry the whole history. Compare the raw column so PXF pushes the filter
    down to the source.
#}
{% macro day_filter(column) -%}
    {{ column }} {{ "<=" if var("oper_day") == var("history_day") else "=" }} '{{ var("oper_day") }}'::date
{%- endmacro %}
