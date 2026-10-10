{% macro storage_parameters(appendoptimized, blocksize, orientation, compresstype, compresslevel) %}

    {% set storage_parameters %}
        with (
            appendoptimized={{ appendoptimized }}
            {% if appendoptimized %}
                , orientation={{ orientation }}
                , compresstype={{ compresstype }}
                , compresslevel={{ compresslevel }}
                , blocksize={{ blocksize }}
            {% endif %}
        )
    {% endset %}

    {{ return(storage_parameters) }}

{% endmacro %}
