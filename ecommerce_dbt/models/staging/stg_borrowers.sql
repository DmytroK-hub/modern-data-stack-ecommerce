-- Аналог stg_users з методички: позичальники
with source as (
    select * from {{ source('raw_ecommerce', 'borrowers') }}
),

-- У сирих даних ~5% позичальників продубльовано (ЛР №1).
-- Нумеруємо рядки в межах одного borrower_id і далі лишаємо лише перший.
deduplicated as (
    select
        *,
        row_number() over (
            partition by borrower_id
            order by registration_date
        ) as row_num
    from source
),

renamed_and_cleaned as (
    select
        borrower_id,
        full_name,
        -- Обробка пустих email-ів
        coalesce(email, 'unknown@example.com') as email,
        phone,
        city,
        cast(birth_date as date) as birth_date,
        cast(monthly_income as numeric(12, 2)) as monthly_income,
        cast(registration_date as date) as registration_date
    from deduplicated
    where row_num = 1
)

select * from renamed_and_cleaned
