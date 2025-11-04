import json
import ast
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
# Import BOTH models. Assuming 'Users' is in your models.py
from .models import StackoverflowJobs2025, Users 

# Create your views here.
# @login_required
def graph_view(request):
    """Renders the Skill Adjacency Graph page."""

    # --- 1. Get Graph Data (for weights AND D3 graph) ---
    graph_data = {
        'ego_node': 'My Role',
        'transitions': []
    }
    # This dictionary will map job names to their transition weight
    # e.g., {'Data Engineer': 0.024, 'Project manager': 0.262}
    transition_weights = {}

    # Get the sample user
    sample_user = Users.objects.get(id='03865452-bc5e-4292-8951-9c3604a7858e')
    
    if sample_user:
        # graph_data['ego_node'] = sample_user.job_title or 'My Role'
        graph_data['ego_node'] = 'My Role' + ' (' + sample_user.job_title + ')'
        job_transitions_data = sample_user.job_transitions
        
        # Handle if data is stored as a JSON string
        if isinstance(job_transitions_data, str):
            try:
                # Try parsing as JSON
                job_transitions_data = json.loads(job_transitions_data)
            except json.JSONDecodeError:
                try:
                    # Try parsing as a Python literal
                    job_transitions_data = ast.literal_eval(job_transitions_data)
                except (ValueError, SyntaxError):
                    job_transitions_data = [] # Give up, set to empty
        
        if isinstance(job_transitions_data, list):
            graph_data['transitions'] = job_transitions_data
            
            # Create the weight lookup dictionary
            for item in job_transitions_data:
                transition_weights[item.get('transition_job')] = item.get('transition_weight')

    # --- 2. Get All Jobs Data (for right panel) ---
    # Fetch all fields needed for processing, using .values() for efficiency
    all_jobs_query = StackoverflowJobs2025.objects.values(
        'job',
        'top_language',
        'top_database',
        'top_platform',
        'top_framework',
        'work_exp',
        'yearly_comp'
    )

    recommended_jobs = []
    
    # Process the "All Jobs" data
    for job_data in all_jobs_query:
        job_name = job_data.get('job')
        
        # --- MODIFIED SECTION ---
        # Clean up the skills list (handles data that is already a list OR a string)
        skills_list = []
        for key in ['top_language', 'top_database', 'top_platform', 'top_framework']:
            skill_data = job_data.get(key)
            if not skill_data:
                continue
            
            if isinstance(skill_data, list):
                # It's already a list, just add its contents
                skills_list.extend(skill_data)
            elif isinstance(skill_data, str):
                # It's a string, clean it like before
                cleaned_skill = skill_data.strip("[]'\" ")
                
                # Handle comma-separated skills inside the brackets, e.g., "['Python', 'Java']"
                if ',' in cleaned_skill:
                    skills_list.extend([s.strip(" '\"") for s in cleaned_skill.split(',')])
                elif cleaned_skill: # Ensure it's not an empty string
                    skills_list.append(cleaned_skill)
        # --- END MODIFIED SECTION ---

        # Create the dictionary for the template
        recommended_jobs.append({
            'name': job_name,
            'skills': list(set(skills_list)), # Use set to remove duplicates
            'work_exp': job_data.get('work_exp'),
            'yearly_comp': job_data.get('yearly_comp'),
            # Add the transition weight from our lookup.
            # Use float('inf') as a default for jobs NOT in the user's graph,
            # so they sort to the bottom.
            'transition_weight': transition_weights.get(job_name, float('inf'))
        })

    # --- 3. SORT the list ---
    # This is the new logic you requested:
    # Sort by 'transition_weight' in ascending order (smallest first)
    recommended_jobs.sort(key=lambda x: x['transition_weight'])

    # --- 4. Set up context ---
    context = {
        'page_title': 'Skill Adjacency Graph',
        'intro_message': 'Visualize your career transitions.',
        'active_nav_item': 'skillgraph', 
        'recommended_jobs': recommended_jobs, # This list is now sorted by weight
        'graph_data': graph_data,              # This is for the D3 graph
    }
    return render(request, 'skillgraph/graph_view.html', context)

