{% macro distribution(distributed_by, distributed_replicated) %}

    {% set distribution %}
        {% if distributed_by is not none %}
            distributed by ({{ distributed_by }})
        {% elif distributed_replicated %}
            distributed replicated
        {% else %}
            distributed randomly
        {% endif %}
    {% endset %}

    {{ return(distribution) }}

{% endmacro %}
