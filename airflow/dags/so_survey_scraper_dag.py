
import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

DEFAULTS = {
    "min_year": 2021,
    "out_dir": "/opt/airflow/data/so_survey_datasets"
}

tz = pendulum.timezone("Asia/Singapore")

with DAG(
    dag_id="so_survey_scraper_dag",
    description="Auto-scrape Stack Overflow Developer Survey (>= min_year), daily at 09:00 SGT",
    start_date=pendulum.datetime(2025, 10, 1, tz=tz),
    schedule="0 9 * * *",  # 09:00 every day SGT
    catchup=False,
    max_active_runs=1,
    params=DEFAULTS,
    tags=["scraper", "stackoverflow", "survey"],
    render_template_as_native_obj=True,
) as dag:

    bash_cmd = """
    mkdir -p "{{ dag_run.conf.get('out_dir', params.out_dir) }}" && \
    python /opt/airflow/dags/scripts/SO_scraper.py \
        --min-year "{{ dag_run.conf.get('min_year', params.min_year) }}" \
        --out-dir "{{ dag_run.conf.get('out_dir', params.out_dir) }}"
    """

    run_scraper = BashOperator(
        task_id="run_so_survey_scraper",
        bash_command=bash_cmd,
    )
