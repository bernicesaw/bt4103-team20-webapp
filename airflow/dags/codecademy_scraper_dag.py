# airflow/dags/codecademy_scraper_dag_demo.py
from datetime import datetime
import os

from airflow import DAG
from airflow.operators.python import PythonOperator

# Helper that manages the Supabase demo table for Codecademy
from scripts.db_supabase_codecademy import ensure_table_exists, upsert_rows

# Scraper and transformer for Codecademy courses
from scripts.codecademy_scraper import scrape_codecademy_rows_sync, transform_for_db


def _create_table():
    # Ensures that a Supabase connection URL is available in the environment
    if not os.getenv("SUPABASE_POOLER_URL") and not os.getenv("SUPABASE_DB_URL"):
        raise RuntimeError(
            "Missing SUPABASE_POOLER_URL or SUPABASE_DB_URL in environment"
        )

    # Creates the public.codecademy_demo table with the expected schema if it does not exist
    ensure_table_exists()
    print("✅ ensured public.codecademy_demo exists")


def _scrape_and_upsert():
    # Scrapes Codecademy course data using the configured keywords and pagination
    rows = scrape_codecademy_rows_sync(
        keywords_csv="python, data science",  # Adjust keywords as needed
        pages=2,
        concurrency=8,
    )
    print(f"✅ scraped {len(rows)} Codecademy rows")

    # Transforms raw scraper output into the schema expected by public.codecademy_demo
    formatted = transform_for_db(rows)

    # Performs batched upserts into the Supabase table
    total = upsert_rows(formatted)
    print(f"✅ upserted {total} rows into public.codecademy_demo")


with DAG(
    dag_id="codecademy_scraper_dag",
    start_date=datetime(2024, 1, 1),
    schedule=None,  # Run manually from the Airflow UI
    catchup=False,
    tags=["demo", "supabase", "codecademy"],
) as dag:

    # Task that ensures the target table exists before any scraping occurs
    create_table = PythonOperator(
        task_id="create_table_if_needed",
        python_callable=_create_table,
    )

    # Task that performs the scraping and writes the results to Supabase
    scrape_and_upsert = PythonOperator(
        task_id="scrape_and_upsert_to_supabase",
        python_callable=_scrape_and_upsert,
    )

    # Execution order: create table first, then scrape and upsert
    create_table >> scrape_and_upsert
