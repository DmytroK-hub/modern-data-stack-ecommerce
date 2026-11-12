-- Таблиця фактів виданих кредитів (аналог fct_orders)
{{ config(materialized='table') }}

with stg_issued_loans as (
    select * from {{ ref('stg_issued_loans') }}
),

stg_borrowers as (
    select * from {{ ref('stg_borrowers') }}
),

-- Завдання 4: приєднуємо типи позик, щоб порахувати total_amount
stg_loan_types as (
    select * from {{ ref('stg_loan_types') }}
)

select
    l.loan_id,
    l.borrower_id,
    l.loan_type_id,
    l.amount,
    l.term_days,
    l.status,
    l.issued_at,
    -- Аналог quantity * price: сума до повернення =
    -- сума кредиту * (1 + річна ставка / 100 * термін у днях / 365)
    round(
        l.amount * (1 + p.annual_interest_rate / 100 * l.term_days / 365.0),
        2
    ) as total_amount
from stg_issued_loans l
-- Перевіряємо, що ми беремо тільки тих позичальників, які існують (Data Integrity)
join stg_borrowers u on l.borrower_id = u.borrower_id
join stg_loan_types p on l.loan_type_id = p.loan_type_id
