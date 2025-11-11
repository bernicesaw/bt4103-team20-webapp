"""
LangChain Chains for Career Chatbot
Merged from FastAPI - contains both Career Graph and Course Recommendation chains
"""
import os
from dotenv import load_dotenv
from langchain.chains import GraphCypherQAChain, RetrievalQA
from langchain_community.graphs import Neo4jGraph
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_openai import ChatOpenAI
from langchain_postgres.vectorstores import PGVector
from langchain_core.prompts import PromptTemplate
from langchain.prompts import (
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    ChatPromptTemplate,
)

# Load environment variables
load_dotenv()

CAREER_QA_MODEL = os.getenv("CAREER_AGENT_MODEL")
CAREER_CYPHER_MODEL = os.getenv("CAREER_AGENT_MODEL")
SUPABASE_CONNECTION_STRING = os.getenv("SUPABASE_POOLER_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# ============================================
# CAREER GRAPH CHAIN (Neo4j)
# ============================================

# --- Connect to Neo4j Career Graph ---
graph = Neo4jGraph(
    url=os.getenv("NEO4J_URI"),
    username=os.getenv("NEO4J_USERNAME"),
    password=os.getenv("NEO4J_PASSWORD"),
)

# Refresh the schema from Neo4j
graph.refresh_schema()


# --- Cypher query generation prompt ---
cypher_generation_prompt = PromptTemplate.from_template("""
Task: Generate a Cypher query for a Neo4j Career Graph database.

Schema:
{schema}

Node: :Job
Properties: name, median_comp, median_workexp, top_language, top_database, top_platform, top_webframe
Relationship: :RELATED_TO (has weight property - lower weight = more similar)

CRITICAL DATA FORMAT:
- Job names are EXACT strings (e.g., 'Data scientist', 'Developer, back-end')
- Technology fields (top_language, top_database, top_platform, top_webframe) contain COMMA-SEPARATED values
- Example: top_language = "Python, JavaScript, TypeScript, SQL"
- ALWAYS use CONTAINS for technology searches, NEVER use = for exact match
                                                        
EXAMPLE JOB NAMES (these are single, exact job names):
- 'Data or business analyst' (ONE job, not two)
- 'Developer, back-end' (ONE job with comma)
- 'Developer, front-end' (ONE job with comma)
- 'UX, Research Ops or UI design professional' (ONE job with both comma and or)
- 'AI/ML engineer' (ONE job with slash)

MATCHING RULES:
- For job names: Use exact match with = (e.g., WHERE j.name = 'Data scientist')
- For technologies: Use CONTAINS (e.g., WHERE j.top_language CONTAINS 'Python')
- Technology names are case-sensitive: 'Python' not 'python'

QUERY PATTERNS:

## Pattern 1: Job Properties (Skills, Salary, Experience)
Use when query asks about a SPECIFIC job's properties

Example: "What is the median salary for a Data scientist?"
MATCH (j:Job {{name: 'Data scientist'}})
RETURN j.median_comp AS median_salary

Example: "What is the work experience for Developer, back-end?"
MATCH (j:Job {{name: 'Developer, back-end'}})
RETURN j.median_workexp AS work_experience

Example: "What technologies does a Developer, full-stack use?"
MATCH (j:Job {{name: 'Developer, full-stack'}})
RETURN j.name AS job_title,
       j.top_language AS language, 
       j.top_database AS database, 
       j.top_platform AS platform, 
       j.top_webframe AS framework

Example: "What skills does a Data scientist need?"
MATCH (j:Job {{name: 'Data scientist'}})
RETURN j.top_language AS language, 
       j.top_database AS database, 
       j.top_platform AS platform, 
       j.top_webframe AS framework

## Pattern 2: Related/Similar Jobs
Use when query asks about jobs similar or related to a SPECIFIC job

Example: "What jobs are similar to Data scientist?"
MATCH (j:Job {{name: 'Data scientist'}})-[r:RELATED_TO]->(related:Job)
RETURN related.name AS job_name, r.weight AS similarity
ORDER BY r.weight ASC
LIMIT 10

Example: "Career transitions from Developer, back-end"
MATCH (j:Job {{name: 'Developer, back-end'}})-[r:RELATED_TO]->(related:Job)
RETURN related.name AS job_name, r.weight AS similarity
ORDER BY r.weight ASC
LIMIT 10

## Pattern 3: Jobs by Technology
Use when query asks WHICH jobs use a specific technology
CRITICAL: Use CONTAINS because technology fields have comma-separated values

Example: "Which jobs use Python as a top language?"
MATCH (j:Job)
WHERE j.top_language CONTAINS 'Python'
RETURN j.name AS job_name, j.median_comp AS salary
ORDER BY j.median_comp DESC

Example: "Jobs that use React"
MATCH (j:Job)
WHERE j.top_webframe CONTAINS 'React'
RETURN j.name AS job_name, j.median_comp AS salary
ORDER BY j.median_comp DESC

Example: "Which jobs use PostgreSQL?"
MATCH (j:Job)
WHERE j.top_database CONTAINS 'PostgreSQL'
RETURN j.name AS job_name, j.median_comp AS salary
ORDER BY j.median_comp DESC

Example: "Jobs using AWS"
MATCH (j:Job)
WHERE j.top_platform CONTAINS 'AWS'
RETURN j.name AS job_name, j.median_comp AS salary
ORDER BY j.median_comp DESC

Example: "Which jobs use both Python and PostgreSQL?"
MATCH (j:Job)
WHERE j.top_language CONTAINS 'Python' 
  AND j.top_database CONTAINS 'PostgreSQL'
RETURN j.name AS job_name, j.median_comp AS salary
ORDER BY j.median_comp DESC

## Pattern 4: Career Transitions with Filters
Use when query asks about salary increases or better-paying jobs

Example: "What jobs pay more than Developer, back-end?"
MATCH (current:Job {{name: 'Developer, back-end'}})-[r:RELATED_TO]->(next:Job)
WHERE next.median_comp > current.median_comp
RETURN next.name AS job_name, 
       next.median_comp - current.median_comp AS salary_increase,
       next.median_comp AS new_salary
ORDER BY salary_increase DESC
LIMIT 10

## Pattern 5: Experience-based Queries
Use when query asks about jobs by experience level

Example: "What jobs require less than 3 years experience?"
MATCH (j:Job)
WHERE j.median_workexp <= 3
RETURN j.name AS job_name, j.median_workexp AS years_required, j.median_comp AS salary
ORDER BY j.median_comp DESC

Example: "Entry-level jobs" (0-2 years)
MATCH (j:Job)
WHERE j.median_workexp <= 2
RETURN j.name AS job_name, j.median_workexp AS years_required, j.median_comp AS salary
ORDER BY j.median_comp DESC

## Pattern 6: Combined Filters
Use when query has multiple conditions

Example: "High-paying Python jobs with less than 5 years experience"
MATCH (j:Job)
WHERE j.top_language CONTAINS 'Python' 
  AND j.median_workexp <= 5 
  AND j.median_comp > 80000
RETURN j.name AS job_name, 
       j.median_comp AS salary,
       j.median_workexp AS experience_years
ORDER BY j.median_comp DESC

KEYWORD MAPPING:
- "skills/technologies/tools/tech stack" for a specific job → Pattern 1 (return properties)
- "salary/compensation/pay" for a specific job → Pattern 1 (return median_comp)
- "experience/years" for a specific job → Pattern 1 (return median_workexp)
- "similar/related/transitions/career path" from a specific job → Pattern 2 (use RELATED_TO)
- "which jobs use [technology]" → Pattern 3 (use CONTAINS)
- "high-paying/better-paying" jobs → Pattern 4 (use WHERE with median_comp)
- "entry-level/junior/senior" → Pattern 5 (use WHERE with median_workexp)

COMMON TECHNOLOGY NAMES (case-sensitive):
Languages: Python, JavaScript, TypeScript, Java, C++, C#, Go, Rust, Ruby, PHP, Swift, Kotlin, R, SQL
Databases: PostgreSQL, MySQL, MongoDB, Redis, SQLite, Oracle, Microsoft SQL Server, Cassandra, DynamoDB
Platforms: AWS, Azure, Google Cloud Platform, Linux, Docker, Kubernetes, Heroku, Jenkins
Frameworks: React, Angular, Vue, Django, Flask, Spring, Express, Laravel, Rails, .NET

User Query: {query}

""")


# --- Natural language answer generation prompt ---
qa_generation_prompt = PromptTemplate(
    input_variables=["context", "question"],  
    template="""You are a data formatter. Convert the query results into a clear answer.

Query Results:
{context}

User Question:
{question}

STRICT RULES:
1. Present EVERY SINGLE result from Query Results - if there are 50 results, show all 50
2. Use ONLY data from Query Results - do not add or omit information
3. If empty results, say: "I don't have that information in the database."
4. Answer directly - no extra explanations or additional information
5. Format: "[Property] for [Job] is [Value]" or numbered list for multiple items
6. NEVER add information not present in the results
7. Do not mention similarity weights unless specifically asked

"""
)


# --- Build the Career Graph QA Chain ---
career_cypher_chain = GraphCypherQAChain.from_llm(
    cypher_llm=ChatOpenAI(model=CAREER_CYPHER_MODEL, temperature=0),
    qa_llm=ChatOpenAI(model=CAREER_QA_MODEL, temperature=0),
    graph=graph,
    verbose=True,
    qa_prompt=qa_generation_prompt,
    cypher_prompt=cypher_generation_prompt,
    validate_cypher=True,
    allow_dangerous_requests=True,
    top_k=50,
)

print("✅ Career Skill Graph QA Chain initialized successfully.")


# ============================================
# COURSE RECOMMENDATION CHAIN (Supabase)
# ============================================
# --- Optionally disable the course recommender for local/dev environments ---
if os.getenv("DISABLE_COURSE_RECOMMENDER", "0").lower() in ("1", "true", "yes"):
    print("Course recommender disabled by DISABLE_COURSE_RECOMMENDER environment variable.")
    supabase_vector_store = None
    qa_chain = None
else:
    # --- Initialize embeddings and vector store inside a guarded try/except ---
    try:
        embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

        # --- Connect to Supabase vector store ---
        print("Connecting to PGVector store...")
        supabase_vector_store = PGVector(
            connection=SUPABASE_CONNECTION_STRING,
            embeddings=embeddings,
            collection_name="course_embeddings",
            use_jsonb=True,
        )

        # --- Define prompt template ---
        course_template = """You are a helpful course recommender system for an online learning platform.

        Based on the following course information, recommend the most relevant courses to the user.

        IMPORTANT: Each course in the context has a 'course_url' in its metadata. You MUST use the EXACT course_url provided - DO NOT make up or modify URLs.

        For each recommended course, format your output as:
        - Course title (use the exact title from metadata)
        - Course URL (use the EXACT course_url from metadata)

        Output as a clean numbered list.

        Course Information:
        {context}

        If no relevant courses are found, politely let the user know and suggest they try a different search term.

        Remember: Use ONLY the actual course_url values from the metadata. Never generate example.com or placeholder URLs.
        """

        system_prompt = SystemMessagePromptTemplate(
            prompt=PromptTemplate(input_variables=["context"], template=course_template)
        )
        human_prompt = HumanMessagePromptTemplate(
            prompt=PromptTemplate(input_variables=["question"], template="{question}")
        )
        review_prompt = ChatPromptTemplate.from_messages([system_prompt, human_prompt])


        # --- Build Course Recommendation RetrievalQA chain ---
        qa_chain = RetrievalQA.from_chain_type(
            llm=ChatOpenAI(model=CAREER_QA_MODEL, temperature=0),
            chain_type="stuff",
            retriever=supabase_vector_store.as_retriever(
                search_kwargs={"k": 5}  # Retrieve top 5 most relevant courses
            ),
            return_source_documents=True,  # Include source documents in response
        )
        qa_chain.combine_documents_chain.llm_chain.prompt = review_prompt

        print("✅ Course Recommender Chain initialized successfully.")
    except Exception as e:
        print("Warning: failed to initialize course recommender:", repr(e))
        supabase_vector_store = None
        qa_chain = None
    except Exception as e:
        print("Warning: failed to initialize course recommender:", repr(e))
        supabase_vector_store = None
        qa_chain = None