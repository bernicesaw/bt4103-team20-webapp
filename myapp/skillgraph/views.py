from django.shortcuts import render

# Create your views here.
def graph_view(request):
    """Renders the Skill Adjacency Graph page."""
    # Original data structure (or fetch this from your database)
    raw_jobs_data = [
        ('AI/ML Engineer', 'Python, TensorFlow, Data Pipelines, Optimization'),
        ('Developer, AI apps or physical AI', 'Robotics, IoT, C++, Computer Vision'),
        ('Data Engineer', 'SQL, ETL, Cloud Data Warehouses, Kafka'),
        ('Data or business analyst', 'Excel, Tableau, Statistics, Report Writing'),
        ('Academic Researcher', 'R, MATLAB, Statistical Modeling, Publication Writing'),
        ('System administrator', 'Linux, Networking, Cloud IAM, Scripting (Bash)'),
        ('Developer, QA or test', 'Selenium, Jest/Mocha, CI/CD, Test Automation'),
        ('Developer, full-stack', 'React/Vue, Django/Node, REST APIs, Git'),
        ('Product Manager', 'User Stories, Market Analysis, Agile, Roadmap Planning'),
        ('DevOps Engineer', 'Terraform, Kubernetes, Ansible, Monitoring (Prometheus)')
        # ... add all other jobs ...
    ]
    
    # 🌟 NEW LOGIC: Pre-process the data before passing it to the template
    recommended_jobs = []
    for job_name, skills_string in raw_jobs_data:
        recommended_jobs.append({
            'name': job_name,
            # Split the string into a true Python list of strings
            'skills': [s.strip() for s in skills_string.split(',')] 
        })

    context = {
        'page_title': 'Skill Adjacency Graph',
        'intro_message': 'Visualize your career transitions.',
        'active_nav_item': 'skillgraph', 
        'recommended_jobs': recommended_jobs,  # Pass the pre-processed list
    }
    return render(request, 'skillgraph/graph_view.html', context)

# # sample render function for context
# def render(request, template_name, context=None):
#     """
#     Conceptual function to simulate rendering a template with context.
#     Replace with your framework's actual render function.
#     """
#     print(f"Rendering template: {template_name}")
#     print(f"Context passed: {context}")
#     # In a real app, this would return an HttpResponse containing the rendered HTML
#     pass