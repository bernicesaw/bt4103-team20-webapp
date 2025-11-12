import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

DEFAULT_PARAMS = {
    "keywords": "python, java, sql",
    "include_catalog": True,
    "max_pages": 0,        # 0 = auto until dry
    "concurrency": 32,
    "output": "/opt/airflow/data/codecademy_courses.csv"
}

tz = pendulum.timezone("Asia/Singapore")

with DAG(
    dag_id="codecademy_scraper_dag",
    description="Run the Codecademy course scraper daily at 09:00 SGT",
    start_date=pendulum.datetime(2025, 10, 1, tz=tz),
    schedule="0 9 * * *",    # ✅ daily at 09:00 Singapore time
    catchup=False,
    params=DEFAULT_PARAMS,
    max_active_runs=1,
    tags=["scraper", "codecademy"],
    render_template_as_native_obj=True,
) as dag:

    bash_cmd = """
    python /opt/airflow/dags/scripts/codecademy_scraper.py \
        --keywords "{{ dag_run.conf.get('keywords', params.keywords) }}" \
        {% if dag_run.conf.get('include_catalog', params.include_catalog) %} --include-catalog {% endif %} \
        --max-pages "{{ dag_run.conf.get('max_pages', params.max_pages) }}" \
        --concurrency "{{ dag_run.conf.get('concurrency', params.concurrency) }}" \
        -o "{{ dag_run.conf.get('output', params.output) }}"
    """

    run_scraper = BashOperator(
        task_id="run_codecademy_scraper",
        bash_command=bash_cmd,
    )
