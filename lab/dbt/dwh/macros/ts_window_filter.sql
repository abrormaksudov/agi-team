{#
    Rows whose timestamp falls in the operating day being closed (a whole UZT day, load_from_datetime ≤ ts <
    load_to_datetime). On the history day also everything earlier: its source files carry the whole history.
#}
{% macro ts_window_filter(column) -%}
    {%- if var("oper_day") != var("history_day") -%}
        {{ column }} >= '{{ var("load_from_datetime") }}'::timestamptz and {% endif -%}
    {{ column }} < '{{ var("load_to_datetime") }}'::timestamptz
{%- endmacro %}
