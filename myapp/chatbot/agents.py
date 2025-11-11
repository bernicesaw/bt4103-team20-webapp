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


# --- Agent prompt ---
career_agent_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a career advisor assistant with access to two tools:

1. **CareerGraph** - for job data, skills, salaries, and career information
2. **CourseRecommendations** - for finding courses and learning materials

CRITICAL RULE: Always pass the COMPLETE user query to the tool.

CORRECT EXAMPLES (these are perfect - do exactly this):
✅ User: "What is the average salary for a data analyst?"
   → You invoke: CareerGraph with "What is the average salary for a data analyst?"

✅ User: "Which jobs use Python as a top language?"
   → You invoke: CareerGraph with "Which jobs use Python as a top language?"

WRONG EXAMPLES (NEVER do this):
❌ User: "What is the average salary for a data analyst?"
   → You invoke: CareerGraph with "data analyst salary" (TOO SHORT!)

❌ User: "Which jobs use Python as a top language?"
   → You invoke: CareerGraph with "Python" (MISSING CONTEXT!)

REMEMBER: The tool handles all processing. Your ONLY job is to pass the exact query.
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
tools = [
    Tool(
        name="CourseRecommendations",
        func=course_chain_wrapper,
        description=(
            "Use for questions about courses, tutorials, learning materials, or certifications. "
            "Always pass the COMPLETE user query, not just keywords."
        ),
    ),
    Tool(
        name="CareerGraph",
        func=graph_chain_wrapper,
        description=(
            "Use for questions about jobs, careers, skills, technologies, salaries, or experience. "
            "IMPORTANT: Always pass the COMPLETE user query, not just keywords. "
            "The tool handles job title normalization automatically. "
            "Examples: 'What skills does X need?', 'Which jobs use Python?', 'X salary'"
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