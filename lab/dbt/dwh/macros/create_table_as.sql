{% macro create_table_as(temporary, relation, sql) %}

    {% set sql_header = config.get('sql_header', none) %}
    {% set distributed_replicated = config.get('distributed_replicated', default=false) %}
    {% set distributed_by = config.get('distributed_by', default=none) %}
    {% set appendoptimized = config.get('appendoptimized', default=true) %}
    {% set orientation = config.get('orientation', default='row') %}
    {% set compresstype = config.get('compresstype', default='zstd') %}
    {% set compresslevel = config.get('compresslevel', default=1) %}
    {% set blocksize = config.get('blocksize', default=32768) %}

    {{ sql_header if sql_header is not none }}

    create {% if temporary %} temporary {% endif %} table {{ relation }}
    {{ storage_parameters(appendoptimized, blocksize, orientation, compresstype, compresslevel) }}
    as
    {{ sql }}
    {{ distribution(distributed_by, distributed_replicated) }};

{% endmacro %}
