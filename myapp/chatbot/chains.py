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
from .job_normalizer import EnhancedJobTitleNormalizer

# Load environment variables
load_dotenv()

CAREER_QA_MODEL = os.getenv("CAREER_AGENT_MODEL")
CAREER_CYPHER_MODEL = os.getenv("CAREER_AGENT_MODEL")
SUPABASE_CONNECTION_STRING = os.getenv("SUPABASE_CONNECTION_STRING")
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

# --- Initialize Job Title Normalizer ---
job_normalizer = EnhancedJobTitleNormalizer(graph)


# --- Cypher query generation prompt ---
cypher_generation_prompt = PromptTemplate.from_template("""
Task: Generate a Cypher query for a Neo4j Career Graph database.

Schema:
{schema}

Node: :Job
Properties: name, median_comp, median_workexp, top_language, top_database, top_platform, top_webframe
Relationship: :RELATED_TO (has weight property - lower weight = more similar)

RULES:
1. Use ONLY properties and relationships from the schema above
2. Match exact job names from the database (case-sensitive)
3. Return ONLY the Cypher query - no comments or explanations
4. Use clear aliases for returned values

QUERY PATTERNS:

## Pattern 1: Single Job Property Lookup
Questions: "What is [property] for [job]?", "[job] salary/experience/skills"

Example: "What is the median salary for a data scientist?"
MATCH (j:Job {{name: 'Data scientist'}})
RETURN j.median_comp AS median_salary

Example: "What is the work experience for backend developer?"
MATCH (j:Job {{name: 'Developer, back-end'}})
RETURN j.median_workexp AS work_experience

Example: "What technologies does a full-stack developer use?"
MATCH (j:Job {{name: 'Developer, full-stack'}})
RETURN j.name AS job_title,
       j.top_language AS language, 
       j.top_database AS database, 
       j.top_platform AS platform, 
       j.top_webframe AS framework

## Pattern 2: Related/Similar Jobs
Questions: "Jobs similar to [job]", "Related careers", "Career transitions from [job]"

Example: "What jobs are similar to data scientist?"
MATCH (j:Job {{name: 'Data scientist'}})-[r:RELATED_TO]->(related:Job)
RETURN related.name AS job_name, r.weight AS similarity
ORDER BY r.weight ASC
LIMIT 10

## Pattern 3: Jobs by Technology
Questions: "Jobs that use [technology]", "Careers using Python"

Example: "Which jobs use Python?"
MATCH (j:Job)
WHERE j.top_language = 'Python'
RETURN j.name AS job_name, j.median_comp AS salary
ORDER BY j.median_comp DESC

## Pattern 4: Career Transitions with Filters
Questions: "Jobs with higher salary than [job]", "Career paths from [job]"

Example: "What jobs pay more than backend developer?"
MATCH (current:Job {{name: 'Developer, back-end'}})-[r:RELATED_TO]->(next:Job)
WHERE next.median_comp > current.median_comp
RETURN next.name AS job_name, 
       next.median_comp - current.median_comp AS salary_increase
ORDER BY salary_increase DESC
LIMIT 10

## Pattern 5: Experience-based Queries
Questions: "Entry-level jobs", "Jobs requiring [X] years"

Example: "What jobs require less than 3 years experience?"
MATCH (j:Job)
WHERE j.median_workexp <= 3
RETURN j.name AS job_name, j.median_workexp AS years_required, j.median_comp AS salary
ORDER BY j.median_comp DESC

PROPERTY MAPPING:
- Salary/compensation/pay → median_comp
- Experience/years/seniority → median_workexp
- Skills/technologies/tools → top_language, top_database, top_platform, top_webframe
- Similar/related jobs → RELATED_TO relationship

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
1. Use ONLY the data in Query Results
2. If empty results, say: "I don't have that information in the database."
3. Answer directly - no extra explanations or additional information
4. Format clearly: "[Property] for [Job] is [Value]" or numbered list for multiple items
5. NEVER add information not present in the results
6. Do not mention similarity weights unless specifically asked

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

# --- Initialize embeddings ---
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