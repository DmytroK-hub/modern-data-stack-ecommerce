-- Вимір позичальників (аналог dim_users)
{{ config(materialized='table') }}

with stg_borrowers as (
    select * from {{ ref('stg_borrowers') }}
)

select
    borrower_id,
    full_name,
    email,
    phone,
    city,
    birth_date,
    monthly_income,
    registration_date
from stg_borrowers
