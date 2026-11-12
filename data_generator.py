"""
Лабораторна робота №1 — Extract & Load (варіант 10: Мікрокредитування).

Скрипт:
  1) генерує 5 пов'язаних таблиць (3 виміри + 2 факти) з навмисно «брудними» даними;
  2) зберігає їх у папку data_lake/ у форматі Parquet (імітація Озера Даних);
  3) завантажує їх «як є» у схему raw сховища PostgreSQL (Docker).

Таблиці:
  Виміри:  borrowers (Позичальники), loan_types (Типи позик), credit_scores (Кредитні рейтинги)
  Факти:   issued_loans (Видані кредити), repayments (Погашення)
  Додаткове завдання: reviews (Відгуки позичальників про типи позик)
"""

import os
import random
from datetime import timedelta

import pandas as pd
from faker import Faker
from sqlalchemy import create_engine, text

# ==========================================
# 0. НАЛАШТУВАННЯ
# ==========================================

fake = Faker('uk_UA')
Faker.seed(42)
random.seed(42)

NUM_BORROWERS = 1000
NUM_LOANS = 3000
NUM_REVIEWS = 1500

# "+psycopg2" явно вказує драйвер (SQLAlchemy 2.1+ за замовчуванням шукає інший — psycopg 3)
DB_URL = "postgresql+psycopg2://admin:adminpassword@localhost:5432/ecommerce_dwh"
DATA_LAKE_DIR = "data_lake"


# ==========================================
# 1. ТАБЛИЦІ ВИМІРІВ (DIMENSIONS)
# ==========================================

def generate_loan_types():
    """Вимір: типи позик (довідник)."""
    print("Генерація типів позик...")
    loan_types = [
        # назва,                    мін. сума, макс. сума, річна ставка %, макс. термін (днів)
        ('Позика до зарплати',       500,      10000,      365.0,          30),
        ('Споживчий кредит',         5000,     100000,     45.0,           365),
        ('Кредит на техніку',        3000,     80000,      29.9,           540),
        ('Кредит на навчання',       10000,    150000,     19.5,           730),
        ('Бізнес-мікрокредит',       20000,    300000,     32.0,           720),
        ('Рефінансування',           10000,    200000,     25.0,           900),
    ]
    data = []
    for i, (name, min_amt, max_amt, rate, term) in enumerate(loan_types, start=1):
        data.append({
            'loan_type_id': i,
            'type_name': name,
            'min_amount': float(min_amt),
            'max_amount': float(max_amt),
            'annual_interest_rate': rate,
            'max_term_days': term,
        })
    return pd.DataFrame(data)


def generate_borrowers(num=NUM_BORROWERS):
    """Вимір: позичальники (з імітацією «брудних» даних)."""
    print(f"Генерація {num} позичальників (з 'брудними' даними)...")
    data = []
    for i in range(1, num + 1):
        # 10% пропущених email — для перевірки dbt-тестів у ЛР №2
        email = fake.email() if random.random() > 0.1 else None
        data.append({
            'borrower_id': i,
            'full_name': fake.name(),
            'email': email,
            'phone': fake.phone_number(),
            'city': fake.city(),
            'birth_date': fake.date_of_birth(minimum_age=18, maximum_age=70),
            'monthly_income': round(random.uniform(8000, 120000), 2),
            'registration_date': fake.date_between(start_date='-2y', end_date='today'),
        })
    df = pd.DataFrame(data)

    # 5% дублікатів — щоб у ЛР №2 очистити їх через ROW_NUMBER() у dbt
    duplicates = df.sample(frac=0.05, random_state=42)
    df = pd.concat([df, duplicates], ignore_index=True)
    return df


def score_to_grade(score):
    if score >= 750:
        return 'A'
    if score >= 680:
        return 'B'
    if score >= 600:
        return 'C'
    if score >= 500:
        return 'D'
    return 'E'


def generate_credit_scores(borrower_ids):
    """Вимір: кредитні рейтинги позичальників (оцінка від бюро)."""
    print(f"Генерація кредитних рейтингів для {len(borrower_ids)} позичальників...")
    bureaus = ['УБКІ', 'ПВБКІ', 'МБКІ']
    data = []
    for i, borrower_id in enumerate(borrower_ids, start=1):
        score = random.randint(300, 850)
        data.append({
            'score_id': i,
            'borrower_id': borrower_id,                 # Зв'язок з позичальником
            'score': score,
            'risk_grade': score_to_grade(score),
            'bureau': random.choice(bureaus),
            'assessed_date': fake.date_between(start_date='-2y', end_date='today'),
        })
    return pd.DataFrame(data)


# ==========================================
# 2. ТАБЛИЦІ ФАКТІВ (FACTS)
# ==========================================

def generate_issued_loans(num, borrower_ids, loan_types_df):
    """Факт: видані кредити."""
    print(f"Генерація {num} виданих кредитів...")
    loan_types = loan_types_df.to_dict('records')
    data = []
    for i in range(1, num + 1):
        lt = random.choice(loan_types)
        term_days = random.randint(7, lt['max_term_days'])
        data.append({
            'loan_id': i,
            'borrower_id': random.choice(borrower_ids),      # FK -> borrowers
            'loan_type_id': lt['loan_type_id'],              # FK -> loan_types
            'amount': round(random.uniform(lt['min_amount'], lt['max_amount']), 2),
            'annual_interest_rate': lt['annual_interest_rate'],
            'term_days': term_days,
            'issue_date': fake.date_time_between(start_date='-1y', end_date='now'),
            'status': random.choices(
                ['active', 'closed', 'overdue', 'defaulted'],
                weights=[50, 35, 10, 5]
            )[0],
        })
    return pd.DataFrame(data)


def generate_repayments(loans_df):
    """Факт: погашення кредитів (кілька платежів по кожному кредиту)."""
    print("Генерація погашень...")
    methods = ['card', 'bank_transfer', 'terminal', 'apple_pay', 'google_pay']
    data = []
    repayment_id = 1
    for loan in loans_df.to_dict('records'):
        num_payments = random.randint(0, 6)
        payment_amount = loan['amount'] / max(num_payments, 1)
        for _ in range(num_payments):
            payment_date = loan['issue_date'] + timedelta(days=random.randint(1, loan['term_days'] + 30))
            data.append({
                'repayment_id': repayment_id,
                'loan_id': loan['loan_id'],                  # FK -> issued_loans
                'borrower_id': loan['borrower_id'],          # FK -> borrowers
                'payment_date': payment_date,
                'amount': round(payment_amount * random.uniform(0.8, 1.2), 2),
                'payment_method': random.choice(methods),
                'is_late': random.random() < 0.15,
                # 20% коментарів порожні (NULL)
                'comment': fake.sentence(nb_words=8) if random.random() > 0.2 else None,
            })
            repayment_id += 1
    return pd.DataFrame(data)


def generate_reviews(num, borrower_ids, loan_type_ids):
    """
    Додаткове завдання ЛР №1: таблиця reviews (відгуки).
    Позичальники оцінюють кредитні продукти (типи позик) від 1 до 5.
    Відповідність полям з методички: product_id -> loan_type_id, user_id -> borrower_id.
    """
    print(f"Генерація {num} відгуків...")
    data = []
    for i in range(1, num + 1):
        data.append({
            'review_id': i,
            'loan_type_id': random.choice(loan_type_ids),    # FK -> loan_types («товар»)
            'borrower_id': random.choice(borrower_ids),      # FK -> borrowers («користувач»)
            'rating': random.randint(1, 5),
            # 20% відгуків без тексту (NULL)
            'comment': fake.sentence() if random.random() > 0.2 else None,
        })
    return pd.DataFrame(data)


# ==========================================
# 3. ГЕНЕРАЦІЯ ТА ЗБЕРЕЖЕННЯ В DATA LAKE
# ==========================================

print("Починаємо генерацію даних...")

df_loan_types = generate_loan_types()
df_borrowers = generate_borrowers()

# Для решти таблиць беремо тільки унікальні ID (бо в позичальниках є дублікати)
unique_borrower_ids = sorted(df_borrowers['borrower_id'].unique().tolist())

df_credit_scores = generate_credit_scores(unique_borrower_ids)
df_issued_loans = generate_issued_loans(NUM_LOANS, unique_borrower_ids, df_loan_types)
df_repayments = generate_repayments(df_issued_loans)
df_reviews = generate_reviews(NUM_REVIEWS, unique_borrower_ids, df_loan_types['loan_type_id'].tolist())

TABLES = {
    'borrowers': df_borrowers,
    'loan_types': df_loan_types,
    'credit_scores': df_credit_scores,
    'issued_loans': df_issued_loans,
    'repayments': df_repayments,
    'reviews': df_reviews,
}

print(
    f"Згенеровано: {len(df_borrowers)} borrowers, {len(df_loan_types)} loan_types, "
    f"{len(df_credit_scores)} credit_scores, {len(df_issued_loans)} issued_loans, "
    f"{len(df_repayments)} repayments, {len(df_reviews)} reviews."
)


def save_to_data_lake():
    os.makedirs(DATA_LAKE_DIR, exist_ok=True)
    for name, df in TABLES.items():
        df.to_parquet(os.path.join(DATA_LAKE_DIR, f'raw_{name}.parquet'), index=False)
    print(f"Parquet-файли збережено у папку {DATA_LAKE_DIR}/")


# ==========================================
# 4. ЗАВАНТАЖЕННЯ (LOAD) У DWH
# ==========================================

def load_data_to_dwh():
    engine = create_engine(DB_URL)

    with engine.connect() as conn:
        # Створення «сирої» схеми, якщо вона не існує
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw;"))
        conn.commit()

    # if_exists='replace' — повне перезавантаження (Full Load).
    # Завдяки цьому скрипт можна безпечно запускати повторно (ідемпотентність).
    for name, df in TABLES.items():
        print(f"Завантаження {name}...")
        df.to_sql(name, engine, schema='raw', if_exists='replace', index=False)

    print("Дані успішно завантажені у схему 'raw'!")


if __name__ == "__main__":
    save_to_data_lake()
    load_data_to_dwh()
