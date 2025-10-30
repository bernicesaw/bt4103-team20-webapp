"""
Career RAG Agent for Django
Merged from FastAPI - now runs directly in Django with job title normalization
"""
import os
import re
from dotenv import load_dotenv
from langchain import hub
from langchain.agents import AgentExecutor, Tool, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

# Load environment variables
load_dotenv()
CAREER_AGENT_MODEL = os.getenv("CAREER_AGENT_MODEL")

from .chains import career_cypher_chain, qa_chain, job_normalizer


# --- Load the agent prompt ---
# career_agent_prompt = hub.pull("hwchase17/openai-functions-agent")

# --- Custom agent prompt for better career query handling ---
career_agent_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a career advisor assistant with access to two tools:

1. **CareerGraph** - for job data, skills, salaries, and career transitions
2. **CourseRecommendations** - for finding courses and learning materials

IMPORTANT RULES:
- Use CareerGraph for ANY question about jobs, careers, skills, technologies, or salaries
- Use CourseRecommendations ONLY when explicitly asked about courses/learning/tutorials
- Present ONLY the information returned by the tools - do NOT add extra information
- If a tool returns related jobs, list only those jobs - don't add skills unless they're in the results
- Be accurate and concise
- If the user mentions a job title informally (like "data scientist" or "backend dev"), 
  the system will automatically normalize it to match the database

Examples:
- "What skills does a data scientist need?" → Use CareerGraph
- "Data scientist salary" → Use CareerGraph  
- "Show me Python courses" → Use CourseRecommendations
- "Jobs similar to backend developer" → Use CareerGraph
"""),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])


def extract_and_normalize_job_titles(query: str) -> str:
    """
    Extract potential job titles from query and normalize them
    Returns the query with normalized job titles
    """
    # Try to normalize the entire query first (in case it's just a job title)
    normalized = job_normalizer.normalize(query, threshold=75)
    if normalized:
        return normalized
    
    # Try to find job titles within the query
    # Split query into potential phrases
    words = query.split()
    
    # Try phrases of different lengths (1-5 words)
    for length in range(5, 0, -1):  # Start with longer phrases
        for i in range(len(words) - length + 1):
            phrase = " ".join(words[i:i+length])
            
            # Try to normalize this phrase
            normalized = job_normalizer.normalize(phrase, threshold=70)
            
            if normalized:
                # Replace the phrase in the original query
                # Use case-insensitive replacement
                pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                normalized_query = pattern.sub(normalized, query)
                
                print(f"🔄 Job title normalized: '{phrase}' → '{normalized}'")
                return normalized_query
    
    # No job title found to normalize
    return query


def graph_chain_wrapper(query: str) -> str:
    """Wrapper that normalizes job titles before querying the career graph"""
    try:
        # Normalize job titles in the query
        normalized_query = extract_and_normalize_job_titles(query)
        
        # Log if normalization occurred
        if normalized_query != query:
            print(f"📝 Original query: {query}")
            print(f"✅ Normalized query: {normalized_query}")
        
        # Invoke the career graph chain with normalized query
        result = career_cypher_chain.invoke({"query": normalized_query})
        return result.get("result", str(result))
    
    except Exception as e:
        print(f"❌ Error in graph_chain_wrapper: {str(e)}")
        return f"I encountered an error querying the career database: {str(e)}"


def course_chain_wrapper(query: str) -> str:
    """Wrapper that extracts real URLs from source_documents"""
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
            "Use this ONLY for questions about courses, tutorials, learning materials, "
            "certifications, or educational content. Examples: 'courses for Python', "
            "'learn machine learning', 'tutorial for React'. "
            "Do NOT use for job information or career data."
        ),
    ),
    Tool(
        name="CareerGraph",
        func=graph_chain_wrapper,
        description=(
            "Use this for questions about: (1) job/career information, (2) skills and "
            "technologies used in jobs, (3) salary/compensation data, (4) career transitions, "
            "(5) similar or related jobs, (6) experience requirements. "
            "Examples: 'data scientist salary', 'jobs similar to backend developer', "
            "'what skills does a data analyst need', 'Python developer jobs'. "
            "The tool automatically normalizes job titles (e.g., 'backend dev' → 'Developer, back-end'). "
            "Do NOT use for finding courses or learning materials."
        ),
    ),
]


# --- Initialize model ---
chat_model = ChatOpenAI(
    model=CAREER_AGENT_MODEL,
    temperature=0,
)


# --- Create OpenAI function-calling agent ---
career_rag_agent = create_openai_functions_agent(
    llm=chat_model,
    prompt=career_agent_prompt,
    tools=tools,
)


# --- Wrap the agent in an executor for orchestration and debugging ---
career_rag_agent_executor = AgentExecutor(
    agent=career_rag_agent,
    tools=tools,
    return_intermediate_steps=True,
    verbose=True,
)


print("✅ Career RAG Agent initialized successfully in Django with job title normalization")


# --- Test function for debugging ---
def test_normalization(test_input: str):
    """Test the job title normalization"""
    print(f"\n{'='*60}")
    print(f"Testing normalization for: '{test_input}'")
    print(f"{'='*60}")
    
    # Get normalization with feedback
    normalized, feedback = job_normalizer.normalize_with_feedback(test_input)
    
    print(f"Result: {normalized}")
    print(f"Feedback: {feedback}")
    print(f"{'='*60}\n")
    
    return normalized


# # --- Uncomment to test the agent ---
# if __name__ == "__main__":
#     print("\n" + "="*80)
#     print("🧪 TESTING JOB TITLE NORMALIZATION")
#     print("="*80)
    
#     # Test various job title inputs
#     test_cases = [
#         "backend dev",
#         "data scientist",
#         "fullstack developer",
#         "ml engineer",
#         "frontend",
#         "what is the salary of a backend developer?",
#     ]
    
#     for test in test_cases:
#         test_normalization(test)
    
#     print("\n" + "="*80)
#     print("🧪 TESTING AGENT WITH NORMALIZATION")
#     print("="*80)
    
#     test_query = "What is the median work experience of a data scientist?"
#     print(f"\n📝 Query: {test_query}")
#     print("\n⏳ Processing...\n")
    
#     result = career_rag_agent_executor.invoke({"input": test_query})
    
#     print("\n" + "="*80)
#     print("🤖 AGENT RESPONSE:")
#     print("="*80)
#     print(result.get("output", result))