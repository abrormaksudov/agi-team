{%- macro get_revoke_sql(relation, privilege, grantees) -%}
    revoke {{ privilege }} on {{ relation.render() }} from {{ grantees | map('tojson') | join(', ') }}
{%- endmacro -%}
