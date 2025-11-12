"""
Helper functions for personalized career recommendations
Fetches user profile and generates recommendations with courses
"""
import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
from langchain_postgres.vectorstores import PGVector
from langchain_community.embeddings import SentenceTransformerEmbeddings
import psycopg2
from accounts.models import Profile 

load_dotenv()


def fetch_user_profile(user_id: int) -> Optional[Dict[str, any]]:
    """
    Fetch user's job_title and skills from accounts_profile table using Django ORM
    
    Args:
        user_id: The authenticated user's ID (integer)
    
    Returns:
        {"job_title": "Data or business analyst", "skills": ["Databricks SQL", "Python"]}
    """
    try:
        # Use Django ORM instead of raw SQL
        user_profile = Profile.objects.get(user=user_id)
        
        # Extract job title
        job_title = user_profile.job_title
        
        # Extract skills - it's already a JSONField (list)
        skills = user_profile.skills
        if not isinstance(skills, list):
            skills = []
        
        # Clean up skills list
        skills = [s for s in skills if s]  # Remove empty strings
        
        print(f"✅ Fetched profile: job='{job_title}', skills={skills}")
        return {
            "job_title": job_title,
            "skills": [s.lower().strip() for s in skills]  # Normalize to lowercase
        }
        
    except Profile.DoesNotExist:
        print(f"⚠️ No profile found for user_id: {user_id}")
        return None
            
    except Exception as e:
        print(f"❌ Error fetching user profile: {e}")
        return None
    

def find_missing_skills(user_skills: List[str], job_skills_dict: Dict[str, str]) -> List[str]:
    """
    Compare user's skills vs job's required skills
    
    Args:
        user_skills: ["databricks sql", "python"]
        job_skills_dict: {"language": "Python, Java, SQL", "database": "PostgreSQL", ...}
    
    Returns:
        List of missing skills: ["Java", "PostgreSQL"]
    """
    # Normalize user skills to lowercase for comparison
    user_skills_normalized = [skill.lower() for skill in user_skills]
    
    # Extract all job skills from the dict
    all_job_skills = []
    for field, skills_str in job_skills_dict.items():
        if skills_str:
            # Split comma-separated skills
            skills_list = [s.strip() for s in skills_str.split(',')]
            all_job_skills.extend(skills_list)
    
    # Find missing skills (case-insensitive comparison)
    missing = []
    for job_skill in all_job_skills:
        # Check if this job skill is NOT in user's skills
        if not any(user_skill in job_skill.lower() or job_skill.lower() in user_skill 
                   for user_skill in user_skills_normalized):
            missing.append(job_skill)
    
    # Remove duplicates while preserving order
    seen = set()
    missing_unique = []
    for skill in missing:
        if skill.lower() not in seen:
            seen.add(skill.lower())
            missing_unique.append(skill)
    
    return missing_unique


def find_course_for_skill(skill: str, vector_store: PGVector, max_results: int = 1) -> Optional[Dict[str, str]]:
    """
    Search course_embeddings for a course teaching this skill
    
    Args:
        skill: "PostgreSQL"
        vector_store: PGVector instance
        max_results: Number of courses to return
    
    Returns:
        {"title": "PostgreSQL for Beginners", "url": "https://..."}
    """
    try:
        # Search for courses related to this skill
        docs = vector_store.similarity_search(
            query=f"Learn {skill} tutorial course",
            k=max_results
        )
        
        if docs:
            doc = docs[0]
            return {
                "title": doc.metadata.get('title', f'{skill} Course'),
                "url": doc.metadata.get('course_url', '#')
            }
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error finding course for {skill}: {e}")
        return None


def format_recommendation_output(
    user_job: str,
    recommendations: List[Dict],
    user_skills: List[str],
    vector_store: PGVector
) -> str:
    """
    Format the final recommendation output with jobs, missing skills, and courses
    
    Args:
        user_job: "Data or business analyst"
        recommendations: List of dicts from Neo4j query result
        user_skills: ["databricks sql", "python"]
        vector_store: PGVector instance for course search
    
    Returns:
        Formatted string with recommendations
    """
    output = f"For your job as a **{user_job}**, here are the top 3 recommended career pathways:\n\n"
    
    for i, job_data in enumerate(recommendations, 1):
        job_name = job_data.get('job_name', 'Unknown Job')
        salary = job_data.get('salary', 'N/A')
        experience = job_data.get('experience', 'N/A')
        
        # Get all skills for this job
        job_skills = {
            'language': job_data.get('language', ''),
            'database': job_data.get('database', ''),
            'platform': job_data.get('platform', ''),
            'framework': job_data.get('framework', '')
        }
        
        # Find missing skills
        missing_skills = find_missing_skills(user_skills, job_skills)
        
        # Format job header
        output += f"### {i}. {job_name}\n"
        output += f"- **Salary**: ${salary:,.0f}\n" if isinstance(salary, (int, float)) else f"- **Salary**: {salary}\n"
        output += f"- **Experience**: {experience} years\n\n"
        
        if missing_skills:
            output += "**Skills to learn:**\n"
            
            # For each missing skill, find a course
            for skill in missing_skills[:5]:  # Limit to 5 missing skills per job
                course = find_course_for_skill(skill, vector_store)
                
                if course:
                    output += f"- {skill}: [{course['title']}]({course['url']})\n"
                else:
                    output += f"- {skill}: (No course found)\n"
        else:
            output += "**Great news!** You already have all the key skills for this role.\n"
        
        output += "\n"
    
    return output