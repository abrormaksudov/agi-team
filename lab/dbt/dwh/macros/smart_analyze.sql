{% macro smart_analyze(interval_hours=6) %}

    {% set mat = config.get('materialized', 'view') %}
    {% if mat in ('table', 'incremental') %}
        do $$
        declare
            v_partition text;
        begin
            -- Найти последнюю партицию (если таблица партиционированная)
            select partitiontablename into v_partition
            from pg_partitions
            where
                schemaname = '{{ this.schema }}'
                and tablename = '{{ this.table }}'
            order by partitionposition desc
            limit 1;

            if v_partition is not null then
                -- Партиционированная таблица: проверяем и анализируем только последнюю партицию
                if not exists (
                    select 1
                    from pg_stat_user_tables
                    where
                        schemaname = '{{ this.schema }}'
                        and relname = v_partition
                        and last_analyze > now() - interval '{{ interval_hours }} hours'
                ) then
                    execute 'analyze {{ this.schema }}.' || quote_ident(v_partition);
                end if;
            else
                -- Обычная таблица: проверяем и анализируем целиком
                if not exists (
                    select 1
                    from pg_stat_user_tables
                    where
                        schemaname = '{{ this.schema }}'
                        and relname = '{{ this.table }}'
                        and last_analyze > now() - interval '{{ interval_hours }} hours'
                ) then
                    execute 'analyze {{ this }}';
                end if;
            end if;
        end $$
    {% endif %}

{% endmacro %}
