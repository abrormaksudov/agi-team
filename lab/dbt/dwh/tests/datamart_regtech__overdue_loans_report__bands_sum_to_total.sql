-- Every report row: the overdue bands add up to the row's total (contracts, principal, interest).
select
    report_date
    , row_code
from {{ ref("datamart_regtech__overdue_loans_report") }}
group by report_date, row_code
having sum(case when band_code = 'total' then contracts_count else -contracts_count end) <> 0
    or sum(case when band_code = 'total' then overdue_principal_thousand_uzs else -overdue_principal_thousand_uzs end) <> 0
    or sum(case when band_code = 'total' then overdue_interest_thousand_uzs else -overdue_interest_thousand_uzs end) <> 0
