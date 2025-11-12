"""
Career RAG Agent for Django
Uses simple regex-based job title normalization with overlap handling
"""
import os
import re
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, Tool, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

load_dotenv()
CAREER_AGENT_MODEL = os.getenv("CAREER_AGENT_MODEL")

from .chains import career_cypher_chain, qa_chain

from .recommendation_helper import (
    fetch_user_profile,
    format_recommendation_output
)
from .chains import supabase_vector_store


# --- Job title synonyms dictionary ---
SYNONYMS = {
    # Backend
    "backend dev": "Developer, back-end",
    "backend developer": "Developer, back-end",
    "back-end dev": "Developer, back-end",
    "back-end developer": "Developer, back-end",
    "backend engineer": "Developer, back-end",
    "be developer": "Developer, back-end",
    
    # Frontend
    "frontend dev": "Developer, front-end",
    "frontend developer": "Developer, front-end",
    "front-end dev": "Developer, front-end",
    "front-end developer": "Developer, front-end",
    "frontend engineer": "Developer, front-end",
    "fe developer": "Developer, front-end",
    
    # Full-stack
    "fullstack": "Developer, full-stack",
    "full stack": "Developer, full-stack",
    "fullstack developer": "Developer, full-stack",
    "full-stack dev": "Developer, full-stack",
    "full stack developer": "Developer, full-stack",
    "fs developer": "Developer, full-stack",
    
    # Data roles
    "data analyst": "Data or business analyst",
    "business analyst": "Data or business analyst",
    "analyst": "Data or business analyst",
    "ba": "Data or business analyst",
    "data scientist": "Data scientist",
    "ds": "Data scientist",
    "scientist": "Data scientist",
    "data engineer": "Data engineer",
    "de": "Data engineer",
    
    # AI/ML roles
    "ml engineer": "AI/ML engineer",
    "machine learning engineer": "AI/ML engineer",
    "ai engineer": "AI/ML engineer",
    "artificial intelligence engineer": "AI/ML engineer",
    "ai developer": "Developer, AI apps or physical AI",
    "ai app developer": "Developer, AI apps or physical AI",
    "physical ai developer": "Developer, AI apps or physical AI",
    "applied scientist": "Applied scientist",
    
    # Cloud/Infrastructure
    "cloud engineer": "Cloud infrastructure engineer",
    "cloud infrastructure": "Cloud infrastructure engineer",
    "infrastructure engineer": "Cloud infrastructure engineer",
    "sysadmin": "System administrator",
    "sys admin": "System administrator",
    "system admin": "System administrator",
    "devops": "DevOps engineer or professional",
    "devops engineer": "DevOps engineer or professional",
    "devops professional": "DevOps engineer or professional",
    
    # Database
    "database admin": "Database administrator or engineer",
    "dba": "Database administrator or engineer",
    "db admin": "Database administrator or engineer",
    "database administrator": "Database administrator or engineer",
    "database engineer": "Database administrator or engineer",
    
    # QA/Testing
    "qa": "Developer, QA or test",
    "qa engineer": "Developer, QA or test",
    "tester": "Developer, QA or test",
    "test engineer": "Developer, QA or test",
    "quality assurance": "Developer, QA or test",
    "qa developer": "Developer, QA or test",
    
    # Management
    "project manager": "Project manager",
    "pm": "Product manager",
    "product manager": "Product manager",
    "engineering manager": "Engineering manager",
    "eng manager": "Engineering manager",
    "em": "Engineering manager",
    
    # Security
    "security": "Cybersecurity or InfoSec professional",
    "cybersecurity": "Cybersecurity or InfoSec professional",
    "infosec": "Cybersecurity or InfoSec professional",
    "security engineer": "Cybersecurity or InfoSec professional",
    "security professional": "Cybersecurity or InfoSec professional",
    
    # Support
    "support engineer": "Support engineer or analyst",
    "support analyst": "Support engineer or analyst",
    "customer support": "Support engineer or analyst",
    
    # Design
    "ux": "UX, Research Ops or UI design professional",
    "ui": "UX, Research Ops or UI design professional",
    "ux designer": "UX, Research Ops or UI design professional",
    "ui designer": "UX, Research Ops or UI design professional",
    "designer": "UX, Research Ops or UI design professional",
    "ux researcher": "UX, Research Ops or UI design professional",
    
    # Executive/Leadership
    "cto": "Senior executive (C-suite, VP, etc.)",
    "ceo": "Senior executive (C-suite, VP, etc.)",
    "vp": "Senior executive (C-suite, VP, etc.)",
    "executive": "Senior executive (C-suite, VP, etc.)",
    "c-suite": "Senior executive (C-suite, VP, etc.)",
    "founder": "Founder, technology or otherwise",
    "co-founder": "Founder, technology or otherwise",
    
    # Specialized developers
    "researcher": "Academic researcher",
    "academic": "Academic researcher",
    "academic researcher": "Academic researcher",
    "mobile dev": "Developer, mobile",
    "mobile developer": "Developer, mobile",
    "mobile engineer": "Developer, mobile",
    "ios developer": "Developer, mobile",
    "android developer": "Developer, mobile",
    "game dev": "Developer, game or graphics",
    "game developer": "Developer, game or graphics",
    "graphics developer": "Developer, game or graphics",
    "desktop dev": "Developer, desktop or enterprise applications",
    "desktop developer": "Developer, desktop or enterprise applications",
    "enterprise developer": "Developer, desktop or enterprise applications",
    "embedded developer": "Developer, embedded applications or devices",
    "embedded engineer": "Developer, embedded applications or devices",
    "iot developer": "Developer, embedded applications or devices",
    
    # Architecture
    "architect": "Architect, software or solutions",
    "software architect": "Architect, software or solutions",
    "solutions architect": "Architect, software or solutions",
    "solution architect": "Architect, software or solutions",
    
    # Finance
    "financial analyst": "Financial analyst or engineer",
    "financial engineer": "Financial analyst or engineer",
    "quant": "Financial analyst or engineer",
}

# --- User context for personalized recommendations ---
_current_user_id = None

def set_user_id(user_id: str):
    """Set the current user's ID for personalized queries"""
    global _current_user_id
    _current_user_id = user_id
    print(f"👤 User ID set: {user_id}")

def get_user_id() -> str:
    """Get the current user's ID"""
    return _current_user_id

def personalized_recommendation_wrapper(query: str) -> str:
    """
    Generate personalized career recommendations based on user profile
    """
    try:
        user_id = get_user_id()
        
        if not user_id:
            return "I need you to be logged in to generate personalized recommendations."
        
        # Fetch user profile from database
        profile = fetch_user_profile(user_id)
        
        if not profile:
            return "I couldn't find your profile. Please make sure you've filled out your job title and skills in your profile."
        
        user_job = profile.get('job_title')
        user_skills = profile.get('skills', [])
        
        if not user_job:
            return "Please add your current job title to your profile first."
        
        print(f"👤 Generating recommendations for: {user_job}")
        print(f"📚 User skills: {user_skills}")
    
        
        # Query Neo4j DIRECTLY (don't use career_cypher_chain)
        from .chains import graph
        
        cypher_query = f"""
        MATCH (current:Job {{name: '{user_job}'}})-[r:RELATED_TO]->(related:Job)
        RETURN related.name AS job_name,
               related.top_language AS language,
               related.top_database AS database, 
               related.top_platform AS platform,
               related.top_webframe AS framework,
               related.median_comp AS salary,
               related.median_workexp AS experience,
               r.weight AS similarity
        ORDER BY r.weight ASC
        LIMIT 3
        """
        
        print(f"🔍 Executing Cypher query...")
        neo4j_results = graph.query(cypher_query)
        
        if not neo4j_results:
            return f"I couldn't find any career recommendations for {user_job}. This might be because the job title isn't in our database."
        
        print(f"✅ Found {len(neo4j_results)} recommendations")
        
        # Format the output with courses using YOUR custom function
        formatted_output = format_recommendation_output(
            user_job=user_job,
            recommendations=neo4j_results,
            user_skills=user_skills,
            vector_store=supabase_vector_store
        )
        
        print(f"📝 Formatted output length: {len(formatted_output)} characters")
        
        return formatted_output
        
    except Exception as e:
        print(f"❌ Error in personalized_recommendation_wrapper: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"I encountered an error generating your recommendations: {str(e)}"

# --- Agent prompt ---
career_agent_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a career advisor assistant with access to three tools:

1. **PersonalizedCareerRecommendation** - for generating career recommendations based on user's profile
2. **CareerGraph** - for general job data, skills, salaries, and career information
3. **CourseRecommendations** - for finding courses and learning materials

TOOL SELECTION RULES:

Use **PersonalizedCareerRecommendation** when user asks:
- "Generate my career recommendation"
- "What career paths for me"
- "Recommend careers for me"
- "Career suggestions based on my profile"

Use **CareerGraph** for general queries:
- "Which jobs use Python?"
- "What skills does a data scientist need?"
- "Jobs similar to backend developer"

Use **CourseRecommendations** for learning materials:
- "Show me courses for Python"
- "Recommend learning materials for machine learning"

CRITICAL: Always pass the COMPLETE user query to the tool.

"""),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])


def normalize_job_title_in_query(query: str) -> str:
    """
    Normalize the job title in the user query based on the SYNONYMS dictionary.
    Handles overlapping matches by prioritizing longer job titles.
    """
    # Find all matches with their positions
    matches = []
    
    for title, normalized_title in SYNONYMS.items():
        # Find all occurrences of this title in the query
        pattern = r'\b' + re.escape(title) + r'\b'
        for match in re.finditer(pattern, query, flags=re.IGNORECASE):
            matches.append({
                'start': match.start(),
                'end': match.end(),
                'original': match.group(),
                'normalized': normalized_title,
                'length': len(title)
            })
    
    # Sort by start position, then by length (longer first for overlaps)
    matches.sort(key=lambda x: (x['start'], -x['length']))
    
    # Remove overlapping matches, keeping only the longest one
    filtered_matches = []
    for match in matches:
        # Check if this match overlaps with any already selected match
        overlaps = False
        for selected in filtered_matches:
            if not (match['end'] <= selected['start'] or match['start'] >= selected['end']):
                # There's an overlap - skip this match
                overlaps = True
                break
        
        if not overlaps:
            filtered_matches.append(match)
    
    # Sort by start position (descending) to replace from end to start
    # This way positions don't shift as we replace
    filtered_matches.sort(key=lambda x: x['start'], reverse=True)
    
    # Apply replacements from end to start
    result = query
    for match in filtered_matches:
        result = result[:match['start']] + match['normalized'] + result[match['end']:]
    
    # Log if any normalization happened
    if result != query:
        print(f"🔄 Normalized query: '{query}' → '{result}'")
    
    return result


def graph_chain_wrapper(query: str) -> str:
    """
    Simple wrapper: normalize job titles in query, pass to Cypher generation
    """
    try:
        # Normalize any job titles in the query
        normalized_query = normalize_job_title_in_query(query)
        
        # Pass the full normalized query to Cypher generation
        result = career_cypher_chain.invoke({"query": normalized_query})
        return result.get("result", str(result))
    
    except Exception as e:
        print(f"❌ Error in graph_chain_wrapper: {str(e)}")
        return f"I encountered an error querying the career database: {str(e)}"


def course_chain_wrapper(query: str) -> str:
    """Wrapper for course recommendations"""
    try:
        result = qa_chain.invoke({"query": query})
        
        # Extract source documents with real URLs
        if isinstance(result, dict) and "source_documents" in result:
            docs = result["source_documents"]
            
            if not docs:
                return "I couldn't find any relevant courses. Try different keywords."
            
            # Format response with REAL URLs from metadata
            response = "Here are some recommended courses:\n\n"
            for i, doc in enumerate(docs, 1):
                title = doc.metadata.get('title', 'Unknown Course')
                url = doc.metadata.get('course_url', '#')
                response += f"{i}. [{title}]({url})\n"
            
            return response
        
        # Fallback to original result if no source_documents
        return result.get("result", str(result))
    
    except Exception as e:
        print(f"❌ Error in course_chain_wrapper: {str(e)}")
        return f"I encountered an error searching for courses: {str(e)}"


# --- Define tools ---
# --- Define tools ---
tools = [
    Tool(
        name="CourseRecommendations",
        func=course_chain_wrapper,
        description=(
            "Use for questions about courses, tutorials, learning materials, or certifications. "
            "Always pass the COMPLETE user query, not just keywords."
            "ONLY for finding TECHNOLOGY and CAREER courses: programming, data science, cloud, web dev, ML, etc. "
            "DO NOT use for non-tech topics like cooking, sports, art, music. "
            "If tool returns 'I don't have courses', DO NOT retry - accept the answer. "
        ),
    ),
    Tool(
        name="PersonalizedCareerRecommendation",
        func=personalized_recommendation_wrapper,
        description=(
            "Use ONLY when user asks for PERSONALIZED career recommendations like: "
            "'Generate my career recommendation', 'What career paths for me', 'Recommend careers for me'. "
            "This tool uses the user's profile (job title and skills) from the database. "
            "Pass the complete query."
        ),
        return_direct = True,
    ),
    Tool(
        name="CareerGraph",
        func=graph_chain_wrapper,
        description=(
            "Use for general questions about jobs, careers, skills, technologies, salaries, or experience. "
            "IMPORTANT: Always pass the COMPLETE user query, not just keywords. "
            "Examples: 'What skills does X need?', 'Which jobs use Python?', 'Jobs similar to data scientist'"
        ),
    ),
]

# --- Initialize model ---
chat_model = ChatOpenAI(
    model=CAREER_AGENT_MODEL,
    temperature=0,
)


# --- Create agent ---
career_rag_agent = create_openai_functions_agent(
    llm=chat_model,
    prompt=career_agent_prompt,
    tools=tools,
)


# --- Wrap agent in executor ---
career_rag_agent_executor = AgentExecutor(
    agent=career_rag_agent,
    tools=tools,
    return_intermediate_steps=True,
    verbose=True,
)


print("✅ Career RAG Agent initialized successfully")