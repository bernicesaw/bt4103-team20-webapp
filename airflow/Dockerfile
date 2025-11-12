# airflow/Dockerfile
FROM apache/airflow:2.9.3

# Copy requirements file
COPY requirements.txt /requirements.txt

# Switch to airflow user before pip install
USER airflow
RUN pip install --no-cache-dir -r /requirements.txt
