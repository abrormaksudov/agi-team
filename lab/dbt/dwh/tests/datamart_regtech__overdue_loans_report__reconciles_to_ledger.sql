-- The report's overdue principal of individuals equals the closing balance of the overdue-principal balance accounts
-- (16400 credit lines, 16410 microloans) in the TranzAxis ledger on the report date.
with ledger as (
    select
        r.report_date
        , sum(t.closing_balance) as ledger_overdue_principal
    from (select distinct report_date from {{ ref("datamart_regtech__overdue_loans_report") }}) as r
        inner join (
            select
                account_id
                , oper_day
                , closing_balance
                , balance_account
            from {{ ref("datamart__tx_turnover") }}
            where balance_account in ('16400', '16410')
        ) as t
            on t.oper_day <= r.report_date
            and not exists (
                select 1
                from {{ ref("datamart__tx_turnover") }} as later
                where later.account_id = t.account_id
                    and later.oper_day > t.oper_day
                    and later.oper_day <= r.report_date
            )
    group by r.report_date
)

, report as (
    select
        report_date
        , overdue_principal_thousand_uzs * 100000 as report_overdue_principal
    from {{ ref("datamart_regtech__overdue_loans_report") }}
    where row_code = '0100'
        and band_code = 'total'
)

select
    r.report_date
    , r.report_overdue_principal
    , coalesce(l.ledger_overdue_principal, 0) as ledger_overdue_principal
from report as r
    left join ledger as l
        on l.report_date = r.report_date
where r.report_overdue_principal <> coalesce(l.ledger_overdue_principal, 0)
