from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import os
import sys

# Додаємо шлях до наших скриптів, щоб Python їх бачив
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'scripts')))
from data_generator import load_data_to_dwh  # імпортуємо функцію з ЛР №1

# Базові налаштування для DAG-а
default_args = {
    'owner': 'data_engineer',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,  # Кількість спроб перезапуску в разі помилки
    'retry_delay': timedelta(minutes=5),
}

# Шлях до папки з dbt проєктом
DBT_PROJECT_DIR = '/mnt/c/Users/kutsu/Documents/modern-data-stack-ecommerce/ecommerce_dbt'
# Шлях до файлу profiles.yml
DBT_PROFILES_DIR = '/mnt/c/Users/kutsu/Documents/modern-data-stack-ecommerce/ecommerce_dbt'

# Оголошення DAG-а
with DAG(
        'ecommerce_elt_pipeline',
        default_args=default_args,
        description='Конвеєр завантаження та трансформації даних мікрокредитування',
        schedule_interval='@daily',  # Запуск кожного дня опівночі
        catchup=False  # Не запускати за минулі дати при першому старті
) as dag:
    # Task 1: Видобуток та завантаження "сирих" даних (ЛР №1)
    extract_load_task = PythonOperator(
        task_id='extract_and_load_raw_data',
        python_callable=load_data_to_dwh
    )

    # Task 2: Трансформація даних за допомогою dbt (ЛР №2)
    # Використовуємо BashOperator для запуску термінальної команди dbt run
    dbt_run_task = BashOperator(
        task_id='dbt_run_transformations',
        bash_command=f'dbt run --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILES_DIR}'
    )

    # Task 3: Перевірка якості даних (Data Quality Gate) за допомогою dbt test
    # Запускає тести з models/staging/schema.yml (unique та not_null для borrower_id)
    dbt_test_task = BashOperator(
        task_id='dbt_test_task',
        bash_command=f'dbt test --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILES_DIR}'
    )

    # Налаштування залежностей (Послідовність виконання)
    # Трансформація почнеться ТІЛЬКИ після успішного завантаження
    extract_load_task >> dbt_run_task >> dbt_test_task