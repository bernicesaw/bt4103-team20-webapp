import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

DEFAULT_OUT = "/opt/airflow/data/datacamp_courses.csv"
tz = pendulum.timezone("Asia/Singapore")

with DAG(
    dag_id="datacamp_scraper_dag",
    description="Scrape DataCamp courses daily at 09:00 SGT",
    start_date=pendulum.datetime(2025, 10, 1, tz=tz),
    schedule="0 9 * * *",  # daily 09:00
    catchup=False,
    max_active_runs=1,
    tags=["scraper","datacamp"],
) as dag:

    run_scraper = BashOperator(
        task_id="run_datacamp_scraper",
        bash_command=f"python /opt/airflow/dags/scripts/datacamp_scraper.py -o {DEFAULT_OUT}",
    )
