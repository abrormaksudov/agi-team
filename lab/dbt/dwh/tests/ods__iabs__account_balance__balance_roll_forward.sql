-- Opening balance plus the day's movement equals the closing balance, by the account's side in the chart of accounts:
-- debits increase active (asset) accounts, credits increase passive (liability) ones — customer card and deposit
-- accounts are passive.
select
    b.account_id
    , b.oper_day
from {{ ref("ods__iabs__account_balance") }} as b
    inner join {{ ref("ods__iabs__account") }} as a
        on a.account_id = b.account_id
    inner join {{ ref("ods__iabs__balance_account") }} as s
        on s.code = a.balance_account
where case
        when s.side = 'active' then b.opening_balance + b.debit_turnover - b.credit_turnover
        else b.opening_balance - b.debit_turnover + b.credit_turnover
    end <> b.closing_balance
