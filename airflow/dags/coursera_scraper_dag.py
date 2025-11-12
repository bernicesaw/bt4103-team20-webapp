import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

DEFAULT_PARAMS = {
    "keywords": "machine learning, data science",
    "pages": 2,
    "concurrency": 16,
    "limit_per_keyword": 20,
    "output": "/opt/airflow/data/coursera_courses.csv"
}

tz = pendulum.timezone("Asia/Singapore")

with DAG(
    dag_id="coursera_scraper_dag",
    description="Run the Coursera keyword scraper daily at 09:00 SGT",
    start_date=pendulum.datetime(2025, 10, 1, tz=tz),  # must be in the past
    schedule="0 9 * * *",          # ✅ every day at 09:00 Singapore time
    catchup=False,
    params=DEFAULT_PARAMS,
    max_active_runs=1,
    tags=["scraper", "coursera"],
    render_template_as_native_obj=True,
) as dag:

    bash_cmd = """
    python /opt/airflow/dags/scripts/coursera_scraper.py \
        --keywords "{{ dag_run.conf.get('keywords', params.keywords) }}" \
        --pages "{{ dag_run.conf.get('pages', params.pages) }}" \
        --concurrency "{{ dag_run.conf.get('concurrency', params.concurrency) }}" \
        --limit-per-keyword "{{ dag_run.conf.get('limit_per_keyword', params.limit_per_keyword) }}" \
        -o "{{ dag_run.conf.get('output', params.output) }}"
    """

    run_scraper = BashOperator(
        task_id="run_coursera_scraper",
        bash_command=bash_cmd,
    )
