-- Завдання 2: аналог stg_products з методички.
-- "Ціною" кредитного продукту є суми позики та відсоткова ставка,
-- тому очищаємо їх: значення не можуть бути меншими за 0 або порожніми.
with source as (
    select * from {{ source('raw_ecommerce', 'loan_types') }}
),

cleaned as (
    select
        loan_type_id,
        type_name,
        greatest(coalesce(cast(min_amount as numeric(12, 2)), 0), 0) as min_amount,
        greatest(coalesce(cast(max_amount as numeric(12, 2)), 0), 0) as max_amount,
        greatest(coalesce(cast(annual_interest_rate as numeric(6, 2)), 0), 0) as annual_interest_rate,
        greatest(coalesce(max_term_days, 0), 0) as max_term_days
    from source
)

select * from cleaned
