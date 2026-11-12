-- Аналог stg_orders з методички: видані кредити
with source as (
    select * from {{ source('raw_ecommerce', 'issued_loans') }}
)

select
    loan_id,
    borrower_id,
    loan_type_id,
    cast(amount as numeric(12, 2)) as amount,
    term_days,
    status,
    cast(issue_date as timestamp) as issued_at
from source
