# A Career Path Navigator for Developers

The Career Path Navigator for Developers is an integrated web application designed to help software developers explore potential career paths, analyze industry trends, and receive personalized skill and course recommendations.
Using insights from the Stack Overflow Developer Survey (2020–2025), the platform provides interactive visualizations, an AI-driven recommendation system, and a conversational chatbot to support data-driven career decision-making.

## Quick start

1. Create and activate a virtual environment at project root

```
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate      # Windows
```

2. Install dependencies

```
pip install -r requirements.txt
```

3. Run App
## Run App

First navigate to the app's directory:

```text
bt4013-team20-webapp/
├── myapp/   <-- navigate here!
│   └── ...
├── .gitignore
├── requirements.txt
└── README.md
```

Run the web app with the following command:

```bash
python manage.py runserver
```

The app opens at http://localhost:8000. Create account and sign in to experience the skill adjacency graph and intereact with our chatbot.

## Troubleshooting
- “Scheme 'b''://' is unknown”:
  - Ensure .env is in myapp directory.

## Alternative: Docker Build and Run

To run the webapp inside Docker, navigate to the 'docker' branch first, then:

1. Build the image

```bash
docker build -t team20-webapp .
```

2. Run the container

```bash
docker run -p 8000:8000 team20-webapp
```

3. Access the app

```bash
Visit: http://localhost:8000
```

## Project structure

```
bt4103-team20-webapp/
├── airflow/          # contains code for the airflow automated course scrapping
├── docs/            #  contains initial user account authentication flow
├── myapp/         # contains all the Django web app code
├── README.md
└── requirements.txt

# Below are more details on our Django web app:
myapp/
├── accounts/        # contains web app’s user accounts implementation
├── chatbot/          # contains chatbot web page implementation and evaluation
├── dashboard/    # contains dashboard web page logic and embedding with streamlit
├── myapp/         # contains web app’s configuration
├── skillgraph/     # contains skill graph web page implementation
├── templates/     # contains html templates of web app
├── load_env.py   # loads .env file with API keys
├── .env               # contains all API keys
├── manage.py  
├── settings.py
└── urls.py

# Below are more details on the airflow implementation:
airflow
├── dags      #contains all the dags
│     ├─ scripts        # contains all the scrapers
│     ├─ codecademy_scraper_dag.py  
│     ├─ coursera_scraper_dag.py
│     ├─ datacamp_scraper_dag.py
│     ├─ datapipeline_merge.py
│     └─ so_survey_scraper_dag.py
├── docker-compose.yaml     # dockerised
├── Dockerfile
├── requirements.txt

```