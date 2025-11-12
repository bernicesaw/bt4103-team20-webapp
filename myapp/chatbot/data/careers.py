import networkx as nx
import pandas as pd
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

# Get the current directory of the script
script_dir = os.path.dirname(__file__)

# Define the file path relative to the script directory
file_path = os.path.join(script_dir, 'processed_devtype_skills_salaries_exp.csv')

df = pd.read_csv(file_path)

salary_diffs = []
exp_diffs = []
for i, row_a in df.iterrows():
    for j, row_b in df.iterrows():
        if i != j:
            s_diff = row_a['MedianComp'] - row_b['MedianComp']
            salary_diffs.append(s_diff)
            e_diff = row_a['MedianWorkExp'] - row_b['MedianWorkExp']
            exp_diffs.append(e_diff)

# Get min and max salary difference
salary_min = min(salary_diffs)
salary_max = max(salary_diffs)
exp_min = min(exp_diffs)
exp_max = max(exp_diffs)

# define functions to compute weights for each edge

def jaccard_similarity(a, b):
    '''
    Compute Jaccard similarity between two sets a and b.
    Range between 0 and 1, where 1 means identical sets.
    '''
    if not a or not b:
        return 0
    return len(a & b) / len(a | b)

def compute_weight(job_a, job_b):
    '''
    Compute weight of edge moving from job A to job B based on salary difference and skill similarity.
    Smaller weight = better transition

    NOTE: add normalization later
    '''
    # Salary difference (higher increase = smaller weight)
    salary_diff = job_b['MedianComp'] - job_a['MedianComp']  # changed direction so that higher salary in job B gives smaller weight
    norm_salary_component = (salary_diff - salary_min) / (salary_max - salary_min)
    # print("Normalized salary:", norm_salary_component)

    # Skill similarity (more overlap = smaller weight)
    skills_set_a = set(job_a['Top_LanguageHaveWorkedWith'].split(', ')) | set(job_a['Top_DatabaseHaveWorkedWith'].split(', ')) | set(job_a['Top_PlatformHaveWorkedWith'].split(', ')) | set(job_a['Top_WebframeHaveWorkedWith'].split(', '))
    skills_set_b = set(job_b['Top_LanguageHaveWorkedWith'].split(', ')) | set(job_b['Top_DatabaseHaveWorkedWith'].split(', ')) | set(job_b['Top_PlatformHaveWorkedWith'].split(', ')) | set(job_b['Top_WebframeHaveWorkedWith'].split(', '))
    sim = jaccard_similarity(skills_set_a, skills_set_b)
    norm_skill_component = 1 - sim 
    # print("Normalized skill:", norm_skill_component)

    # Job experience difference (lower increase = smaller weight)
    exp_diff = job_b['MedianWorkExp'] - job_a['MedianWorkExp']  # changed direction so that lower experience in job B gives smaller weight
    if exp_diff < 0:
        exp_diff = 0  # if job B requires less experience, set difference to 0
    norm_exp_component = (exp_diff - exp_min) / (exp_max - exp_min)  # smaller is better
    # print("Normalized experience:", norm_exp_component)

    # Normalize or weight components if needed
    return norm_salary_component + norm_skill_component + norm_exp_component

# --- Create the NetworkX Graph ---
Skills_Adj_Graph = nx.DiGraph()

# Add nodes to the graph
for idx, row in df.iterrows():
    Skills_Adj_Graph.add_node(
        row['DevType'],
        median_comp=row['MedianComp'],
        median_workexp=row['MedianWorkExp'],
        top_language=row['Top_LanguageHaveWorkedWith'],
        top_database=row['Top_DatabaseHaveWorkedWith'],
        top_platform=row['Top_PlatformHaveWorkedWith'],
        top_webframe=row['Top_WebframeHaveWorkedWith']
    )

# Add edges with weights
for i, row_a in df.iterrows():
    for j, row_b in df.iterrows():
        if i != j:
            weight = compute_weight(row_a, row_b)
            Skills_Adj_Graph.add_edge(row_a['DevType'], row_b['DevType'], weight=weight)

# --- Connect to Neo4j ---
# Load environment variables from .env file
load_dotenv()

# Retrieve the values from the environment
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# Instantiate the Neo4j driver
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

# --- Store nodes and edges in Neo4j ---
def store_graph_in_neo4j(graph):
    with driver.session() as session:
        # Store nodes
        for node, data in graph.nodes(data=True):
            session.run(
                "MERGE (n:Job {name: $name}) "
                "SET n.median_comp = $median_comp, "
                "n.median_workexp = $median_workexp, "
                "n.top_language = $top_language, "
                "n.top_database = $top_database, "
                "n.top_platform = $top_platform, "
                "n.top_webframe = $top_webframe",
                name=node,
                median_comp=data['median_comp'],
                median_workexp=data['median_workexp'],
                top_language=data['top_language'],
                top_database=data['top_database'],
                top_platform=data['top_platform'],
                top_webframe=data['top_webframe']
            )
        
        # Store edges with weights
        for u, v, data in graph.edges(data=True):
            session.run(
                "MATCH (a:Job {name: $u}), (b:Job {name: $v}) "
                "MERGE (a)-[r:RELATED_TO]->(b) "
                "SET r.weight = $weight",
                u=u, v=v, weight=data['weight']
            )

# Call the function to store the graph
store_graph_in_neo4j(Skills_Adj_Graph)

print("Graph stored in Neo4j successfully.")