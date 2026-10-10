{{ config(
    tags="cod",
    meta={ "owner": "data_platform" },
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="report_date",
    on_schema_change="fail",
    alias="contract_classification_tech",
    schema="datamart",
    grants={ "select": [ "l3__datamart__bs" ] }
) }}

{% set report_date = "'" ~ var("oper_day") ~ "'::date" %}

with contracts as (
    select
        contract_id
        , client_id
        , contract_type
        , product_code
        , status
        , open_date
    from {{ ref("ods__tranzaxis__contract") }}
    where contract_type in ('credit_line', 'microloan')
        and status <> 'closed'
        and open_date <= {{ report_date }}
)

, turnover as (
    select
        contract_id
        , account_role
        , oper_day
        , debit_turnover
        , credit_turnover
        , closing_balance
    from {{ ref("datamart__tx_turnover") }}
    where contract_type in ('credit_line', 'microloan')
        and oper_day <= {{ report_date }}
)

, latest_balance as (
    select
        contract_id
        , account_role
        , closing_balance
        , row_number() over (partition by contract_id, account_role order by oper_day desc) as rn
    from turnover
)

, balances as (
    select
        contract_id
        , sum(case when account_role = 'principal' then closing_balance else 0 end)::bigint as principal_balance
        , sum(case when account_role = 'interest' then closing_balance else 0 end)::bigint as interest_balance
        , sum(case when account_role = 'overdue_principal' then closing_balance else 0 end)::bigint as overdue_principal_balance
        , sum(case when account_role = 'overdue_interest' then closing_balance else 0 end)::bigint as overdue_interest_balance
        , sum(case when account_role = 'penalty' then closing_balance else 0 end)::bigint as penalty_balance
        , sum(case when account_role = 'write_off' then closing_balance else 0 end)::bigint as written_off_principal
        , sum(case when account_role = 'write_off_interest' then closing_balance else 0 end)::bigint as written_off_interest
        , sum(case when account_role = 'limit' then closing_balance else 0 end)::bigint as unused_limit
    from latest_balance
    where rn = 1
    group by contract_id
)

-- FIFO: each debit of an overdue account is a slice dated by its posting day; repayments clear the oldest slice
-- first, so the oldest unpaid slice is the first debit whose running total exceeds everything credited so far
, overdue_slices as (
    select
        contract_id
        , account_role
        , oper_day
        , debit_turnover
        , sum(debit_turnover) over (
            partition by contract_id, account_role order by oper_day rows between unbounded preceding and current row
        ) as debited_to_date
        , sum(credit_turnover) over (partition by contract_id, account_role) as credited_total
    from turnover
    where account_role in ('overdue_principal', 'overdue_interest')
)

, oldest_unpaid as (
    select
        contract_id
        , min(case when account_role = 'overdue_principal' then oper_day end) as oldest_unpaid_principal_date
        , min(case when account_role = 'overdue_interest' then oper_day end) as oldest_unpaid_interest_date
    from overdue_slices
    where debit_turnover > 0
        and debited_to_date > credited_total
    group by contract_id
)

-- a write-off credits every balance account at once; that is not a repayment
, write_off_day as (
    select
        contract_id
        , min(oper_day) as write_off_date
    from turnover
    where account_role = 'write_off'
        and debit_turnover > 0
    group by contract_id
)

, activity as (
    select
        t.contract_id
        , max(case when t.account_role = 'principal' and t.debit_turnover > 0 then t.oper_day end) as last_draw_date
        , max(
            case
                when t.account_role in ('principal', 'interest', 'overdue_principal', 'overdue_interest', 'penalty')
                    and t.credit_turnover > 0
                    and t.oper_day is distinct from w.write_off_date
                    then t.oper_day
            end
        ) as last_repayment_date
    from turnover as t
        left join write_off_day as w
            on w.contract_id = t.contract_id
    group by t.contract_id
)

, statements as (
    select
        contract_id
        , statement_date
        , due_date
        , min_payment
        , paid_amount
        , row_number() over (partition by contract_id order by statement_date desc) as rn
    from {{ ref("ods__tranzaxis__credit_line_cycle") }}
    where statement_date <= {{ report_date }}
)

, first_due as (
    select
        contract_id
        , min(due_date) as first_due_date
    from (
        select contract_id, due_date from {{ ref("ods__tranzaxis__payment_schedule") }}
        union all
        select contract_id, due_date from {{ ref("ods__tranzaxis__credit_line_cycle") }}
    ) as dues
    group by contract_id
)

select
    {{ report_date }} as report_date
    , c.contract_id
    , c.client_id
    , c.contract_type
    , c.product_code
    , c.status as contract_status
    , c.open_date
    , coalesce(b.principal_balance, 0) as principal_balance
    , coalesce(b.interest_balance, 0) as interest_balance
    , coalesce(b.overdue_principal_balance, 0) as overdue_principal_balance
    , coalesce(b.overdue_interest_balance, 0) as overdue_interest_balance
    , coalesce(b.penalty_balance, 0) as penalty_balance
    , coalesce(b.written_off_principal, 0) as written_off_principal
    , coalesce(b.written_off_interest, 0) as written_off_interest
    , coalesce(b.unused_limit, 0) as unused_limit
    , o.oldest_unpaid_principal_date
    , o.oldest_unpaid_interest_date
    , ({{ report_date }} - o.oldest_unpaid_principal_date)::integer as days_past_due_principal
    , ({{ report_date }} - o.oldest_unpaid_interest_date)::integer as days_past_due_interest
    , coalesce(
        ({{ report_date }} - least(o.oldest_unpaid_principal_date, o.oldest_unpaid_interest_date))::integer, 0
    ) as days_past_due
    , a.last_draw_date
    , a.last_repayment_date
    , f.first_due_date
    , s.statement_date
    , s.due_date as statement_due_date
    , s.min_payment as statement_min_payment
    , s.paid_amount as statement_paid_amount
    , '{{ var("dwh_job_id") }}'::text as dwh_job_id
    , now() as dwh_created_at
from contracts as c
    left join balances as b
        on b.contract_id = c.contract_id
    left join oldest_unpaid as o
        on o.contract_id = c.contract_id
    left join activity as a
        on a.contract_id = c.contract_id
    left join statements as s
        on s.contract_id = c.contract_id
        and s.rn = 1
    left join first_due as f
        on f.contract_id = c.contract_id
