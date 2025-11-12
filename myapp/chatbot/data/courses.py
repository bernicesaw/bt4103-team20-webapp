from sentence_transformers import SentenceTransformer
from supabase import create_client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# Load embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Fetch all courses
courses = supabase.table("all_courses").select("*").execute().data

# Generate and store embeddings
for course in courses:
    text_to_embed = f"{course['title']} {course['description_full']}"
    embedding = model.encode(text_to_embed).tolist()

    supabase.table("course_embeddings").insert({
        "course_url": course["url"],
        "embedding": embedding
    }).execute()

print("Manually added courses inserted successfully.")
