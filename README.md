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

# Alternative: Docker Build and Run

To run the webapp inside Docker:

## 1. Build the image

docker build -t team20-webapp .

## 2. Run the container

docker run -p 8000:8000 team20-webapp

## 3. Access the app

Visit: http://localhost:8000
