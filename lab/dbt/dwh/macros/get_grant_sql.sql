{%- macro get_grant_sql(relation, privilege, grantees) -%}
    grant {{ privilege }} on {{ relation.render() }} to {{ grantees | map('tojson') | join(', ') }}
{%- endmacro -%}
