{{ config(severity="warn") }}

-- Our FIFO days past due, bucketed like TranzAxis, agree with the delinquency state TranzAxis itself recorded
-- (its latest state change on or before the report date; a contract never delinquent is current).
with ours as (
    select
        report_date
        , contract_id
        , case
            when classification = 'written_off' then 'written_off'
            when days_past_due = 0 then 'current'
            when days_past_due <= 30 then 'dpd_1_30'
            when days_past_due <= 60 then 'dpd_31_60'
            when days_past_due <= 90 then 'dpd_61_90'
            when days_past_due <= 180 then 'dpd_91_180'
            else 'dpd_181_360'
        end as state
    from {{ ref("datamart__contract_classification_daily") }}
)

, theirs as (
    select
        o.report_date
        , o.contract_id
        , h.state
        , row_number() over (partition by o.report_date, o.contract_id order by h.effective_date desc) as rn
    from ours as o
        inner join {{ ref("ods__tranzaxis__delinquency_history") }} as h
            on h.contract_id = o.contract_id
            and h.effective_date <= o.report_date
)

select
    o.report_date
    , o.contract_id
    , o.state as our_state
    , coalesce(t.state, 'current') as tranzaxis_state
from ours as o
    left join theirs as t
        on t.report_date = o.report_date
        and t.contract_id = o.contract_id
        and t.rn = 1
where o.state <> coalesce(t.state, 'current')
