# airflow/dags/coursera_scraper_dag_demo.py
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
from scripts.db_supabase import ensure_table_exists, upsert_rows
from scripts.coursera_scraper import scrape_coursera_rows_sync, transform_for_db

# Use the same var your webapp uses; it's already in container env via docker-compose env_file
POOLER = os.getenv("SUPABASE_POOLER_URL")  # optional: for log sanity checks

def _create_table():
    # expose to helper (which now accepts either var)
    os.environ["SUPABASE_POOLER_URL"] = os.environ.get("SUPABASE_POOLER_URL", "")
    ensure_table_exists()
    print("✅ ensured public.coursera_demo exists")

def _scrape_and_upsert():
    os.environ["SUPABASE_POOLER_URL"] = os.environ.get("SUPABASE_POOLER_URL", "")
    rows = scrape_coursera_rows_sync(
        keywords_csv="machine learning, data science",
        pages=2,
        concurrency=8,
    )
    upsert_rows(transform_for_db(rows))
    print(f"✅ upserted {len(rows)} rows")

with DAG(
    dag_id="coursera_scraper_dag",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["demo", "supabase", "coursera"],
) as dag:

    create_table = PythonOperator(
        task_id="create_table_if_needed",
        python_callable=_create_table,
    )

    scrape_and_save = PythonOperator(
        task_id="scrape_and_upsert_to_supabase",
        python_callable=_scrape_and_upsert,
    )

    create_table >> scrape_and_save
