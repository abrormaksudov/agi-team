{% macro _uzt_instant(dt_var) %}

    {% set instant = modules.datetime.datetime.fromisoformat(var(dt_var)) %}
    {% if instant.tzinfo is none %}
        {% set instant = instant.replace(tzinfo=modules.pytz.utc) %}
    {% endif %}

    {{ return(instant.astimezone(modules.pytz.FixedOffset(300))) }}

{% endmacro %}


{% macro uzt_d(dt_var) %}

    {{ return(_uzt_instant(dt_var).strftime("'%Y-%m-%d'")) }}

{% endmacro %}


{% macro uzt_ts(dt_var) %}

    {{ return(_uzt_instant(dt_var).strftime("'%Y-%m-%d %H:%M:%S'")) }}

{% endmacro %}
