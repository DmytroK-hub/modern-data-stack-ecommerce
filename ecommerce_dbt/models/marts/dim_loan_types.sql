-- Завдання 3: вимір типів позик (аналог dim_products)
{{ config(materialized='table') }}

with stg_loan_types as (
    select * from {{ ref('stg_loan_types') }}
)

select
    loan_type_id,
    type_name,
    min_amount,
    max_amount,
    annual_interest_rate,
    max_term_days
from stg_loan_types
