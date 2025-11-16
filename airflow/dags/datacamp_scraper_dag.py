from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
import os

from scripts.db_supabase_datacamp import ensure_table_exists, upsert_rows
from scripts.datacamp_scraper import scrape_datacamp_rows_sync, transform_for_db

# Optional: just for sanity when debugging logs
POOLER = os.getenv("SUPABASE_POOLER_URL")


def _create_table():
    """
    Ensure the demo table exists in Supabase.
    Mirrors coursera_scraper_dag_demo.py behaviour.
    """
    # Expose to helper (which accepts SUPABASE_DB_URL or SUPABASE_POOLER_URL)
    os.environ["SUPABASE_POOLER_URL"] = os.environ.get("SUPABASE_POOLER_URL", "")
    ensure_table_exists()
    print("✅ ensured public.datacamp_demo exists")


def _scrape_and_upsert():
    """
    Scrape all DataCamp courses and upsert into Supabase.
    """
    os.environ["SUPABASE_POOLER_URL"] = os.environ.get("SUPABASE_POOLER_URL", "")

    rows = scrape_datacamp_rows_sync()
    db_rows = transform_for_db(rows)
    upsert_rows(db_rows)

    print(f"✅ scraped {len(rows)} raw DataCamp rows")
    print(f"✅ upserted {len(db_rows)} rows into public.datacamp_demo")


with DAG(
    dag_id="datacamp_scraper_dag",
    start_date=datetime(2024, 1, 1),
    schedule=None,  # trigger manually via UI
    catchup=False,
    tags=["demo", "supabase", "datacamp"],
) as dag:

    create_table = PythonOperator(
        task_id="create_datacamp_demo_table_if_needed",
        python_callable=_create_table,
    )

    scrape_and_save = PythonOperator(
        task_id="scrape_datacamp_and_upsert_to_supabase",
        python_callable=_scrape_and_upsert,
    )

    create_table >> scrape_and_save
