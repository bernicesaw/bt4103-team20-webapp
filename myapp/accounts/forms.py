from django import forms
from django.core.exceptions import ValidationError
from .models import CURRENCY_CHOICES

# Authoritative list of job titles used for datalist suggestions and optional choice lists.
# Extracted from data cleaning of our dataset
JOB_TITLE_CHOICES = [
    'AI/ML engineer', 'Academic researcher', 'Applied scientist', 'Architect, software or solutions',
    'Blockchain', 'Cloud infrastructure engineer', 'Cybersecurity or InfoSec professional', 'Data engineer',
    'Data or business analyst', 'Data scientist', 'Data scientist or machine learning specialist',
    'Database administrator', 'Database administrator or engineer', 'Designer', 'DevOps engineer or professional',
    'DevOps specialist', 'Developer Advocate', 'Developer Experience', 'Developer, AI',
    'Developer, AI apps or physical AI', 'Developer, QA or test', 'Developer, back-end',
    'Developer, desktop or enterprise applications', 'Developer, embedded applications or devices',
    'Developer, front-end', 'Developer, full-stack', 'Developer, game or graphics', 'Developer, mobile',
    'Educator', 'Engineer, data', 'Engineer, site reliability', 'Engineering manager',
    'Financial analyst or engineer', 'Founder, technology or otherwise', 'Hardware Engineer',
    'Marketing or sales professional', 'Other (please specify):', 'Product manager', 'Project manager',
    'Research & Development role', 'Retired', 'Scientist', 'Security professional',
    'Senior Executive (C-Suite, VP, etc.)', 'Senior executive (C-suite, VP, etc.)', 'Senior executive/VP',
    'Student', 'Support engineer or analyst', 'System administrator', 'UX, Research Ops or UI design professional'
]


def validate_password_strength(value):
    if len(value) < 8:
        raise ValidationError('Password must be at least 8 characters long.')
    if not any(c.isdigit() for c in value):
        raise ValidationError('Password must contain at least one digit.')
    if not any(c.islower() for c in value):
        raise ValidationError('Password must contain at least one lowercase letter.')
    if not any(c.isupper() for c in value):
        raise ValidationError('Password must contain at least one uppercase letter.')


class SignupForm(forms.Form):
    email = forms.EmailField(label='Email Address', widget=forms.EmailInput(attrs={'class': 'form-control'}))
    email_repeat = forms.EmailField(label='Confirm Email Address', widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), validators=[validate_password_strength], label='Password')
    password_repeat = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label='Confirm Password')

    # free-form job title with client-side suggestions
    job_title = forms.CharField(label='Job Title', required=True)

    skills = forms.CharField(required=True, help_text='Comma-separated skills (add up to five)')

    median_salary = forms.DecimalField(max_digits=12, decimal_places=2, label='Monthly Median Salary', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    # prepend a placeholder option for the currency select so the dropdown shows "Select currency"
    CURRENCY_CHOICES_WITH_PLACEHOLDER = [('', 'Select currency')] + CURRENCY_CHOICES
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES_WITH_PLACEHOLDER, label='Currency', widget=forms.Select(attrs={'class': 'form-select'}))

    # We'll accept working experience as JSON string from the client
    work_experiences = forms.CharField(required=False, help_text='JSON array of experiences')

    # Optional notifications opt-in on signup
    notifications = forms.BooleanField(required=False, label='Receive notifications')

    # Authoritative skills list used for suggestions and server-side validation.
    # Extracted from data cleaning of our dataset
    SKILLS = [
        'Ada', 'Alibaba Cloud', 'Amazon Redshift', 'Amazon Web Services (Aws)', 'Android', 'Angular', 'Angular.Js',
        'Angularjs', 'Ansible', 'Apex', 'Apl', 'Apt', 'Arduino', 'Asp.Net', 'Asp.Net Core', 'Assembly', 'Astro',
        'Aws', 'Axum', 'Bash/Shell', 'Bash/Shell (All Shells)', 'Bash/Shell/Powershell', 'Bigquery', 'Blazor', 'Bun',
        'C', 'C#', 'C++', 'Cargo', 'Cassandra', 'Chocolatey', 'Clickhouse', 'Clojure', 'Cloud Firestore', 'Cloudflare',
        'Cobol', 'Cockroachdb', 'Codeigniter', 'Colocation', 'Composer', 'Cosmos Db', 'Couch Db', 'Couchbase',
        'Couchdb', 'Crystal', 'Dart', 'Databricks', 'Databricks Sql', 'Datadog', 'Datomic', 'Delphi', 'Deno',
        'Digital Ocean', 'Digitalocean', 'Django', 'Docker', 'Drupal', 'Duckdb', 'Dynamodb', 'Elasticsearch',
        'Elixir', 'Elm', 'Erlang', 'Eventstoredb', 'Express', 'F#', 'Fastapi', 'Fastify', 'Firebase',
        'Firebase Realtime Database', 'Firebird', 'Flask', 'Flow', 'Fly.Io', 'Fortran', 'Gatsby', 'Gdscript',
        'Gleam', 'Go', 'Google Cloud', 'Google Cloud Platform', 'Gradle', 'Groovy', 'H2', 'Haskell', 'Heroku',
        'Hetzner', 'Homebrew', 'Html/Css', 'Htmx', 'Ibm Cloud', 'Ibm Cloud Or Watson', 'Ibm Db2', 'Influxdb',
        'Ios', 'Java', 'Javascript', 'Jquery', 'Julia', 'Kotlin', 'Kubernetes', 'Laravel', 'Linode',
        'Linode, Now Akamai', 'Linux', 'Lisp', 'Lit', 'Lua', 'Macos', 'Make', 'Managed Hosting', 'Mariadb',
        'Matlab', 'Maven (Build Tool)', 'Micropython', 'Microsoft Access', 'Microsoft Azure', 'Microsoft Sql Server',
        'Mojo', 'Mongodb', 'Msbuild', 'Mysql', 'Neo4J', 'Nestjs', 'Netlify', 'New Relic', 'Next.Js', 'Nim', 'Ninja',
        'Node.Js', 'Npm', 'Nuget', 'Nuxt.Js', 'Objective-C', 'Ocaml', 'Openshift', 'Openstack', 'Oracle',
        'Oracle Cloud Infrastructure', 'Oracle Cloud Infrastructure (Oci)', 'Ovh', 'Pacman', 'Perl', 'Phoenix', 'Php',
        'Pip', 'Play Framework', 'Pnpm', 'Pocketbase', 'Podman', 'Poetry', 'Postgresql', 'Powershell', 'Presto',
        'Prolog', 'Prometheus', 'Python', 'Pythonanywhere', 'Qwik', 'R', 'Railway', 'Raku', 'Raspberry Pi',
        'Ravendb', 'React', 'React.Js', 'Redis', 'Remix', 'Render', 'Ruby', 'Ruby On Rails', 'Rust', 'Sas', 'Scala',
        'Scaleway', 'Slack Apps And Integrations', 'Snowflake', 'Solid.Js', 'Solidity', 'Solr', 'Splunk', 'Spring',
        'Spring Boot', 'Sql', 'Sqlite', 'Strapi', 'Supabase', 'Svelte', 'Swift', 'Symfony', 'Terraform', 'Tidb',
        'Typescript', 'Valkey', 'Vba', 'Vercel', 'Visual Basic (.Net)', 'Vite', 'Vmware', 'Vue.Js', 'Vultr',
        'Webpack', 'Windows', 'Wordpress', 'Yandex Cloud', 'Yarn', 'Yii 2', 'Zephyr', 'Zig'
    ]

    def clean_email_repeat(self):
        a = self.cleaned_data.get('email')
        b = self.cleaned_data.get('email_repeat')
        if a != b:
            raise ValidationError("Emails do not match.")
        return b

    def clean_password_repeat(self):
        a = self.cleaned_data.get('password')
        b = self.cleaned_data.get('password_repeat')
        if a != b:
            raise ValidationError("Passwords do not match.")
        return b

    def clean_skills(self):
        raw = self.cleaned_data.get('skills') or ''
        skills = [s.strip() for s in raw.split(',') if s.strip()]
        if len(skills) > 5:
            raise ValidationError("You may select at most 5 skills.")
        # ensure each skill is in our authoritative SKILLS list
        unknown = [s for s in skills if s not in getattr(self, 'SKILLS', [])]
        if unknown:
            raise ValidationError(f"Unknown skills: {', '.join(unknown)}. Please choose from the allowed options.")
        return skills

    def clean_work_experiences(self):
        import json
        raw = self.cleaned_data.get('work_experiences') or '[]'
        try:
            arr = json.loads(raw)
        except Exception:
            raise ValidationError("Invalid work_experiences JSON.")
        if not isinstance(arr, list):
            raise ValidationError("work_experiences must be a list.")
        if len(arr) > 10:
            raise ValidationError("Too many work experience entries.")
        for idx, exp in enumerate(arr):
            skills = exp.get('skills', [])
            if len(skills) > 5:
                raise ValidationError(f"Work experience #{idx+1} has more than 5 skills.")
            # validate each skill in experience against authoritative list
            unknown_exp = [s for s in skills if s not in getattr(self, 'SKILLS', [])]
            if unknown_exp:
                raise ValidationError(f"Work experience #{idx+1} contains unknown skills: {', '.join(unknown_exp)}.")
            # ensure required fields in each experience are present
            if not exp.get('job_title'):
                raise ValidationError(f"Work experience #{idx+1} missing job_title.")
            if exp.get('median_salary') in (None, ''):
                raise ValidationError(f"Work experience #{idx+1} missing median_salary.")
            # ensure median_salary is numeric and non-negative
            val = exp.get('median_salary')
            try:
                num = float(val)
            except Exception:
                raise ValidationError(f"Work experience #{idx+1} has an invalid median_salary. Please enter a number.")
            if num < 0:
                raise ValidationError(f"Work experience #{idx+1} has a negative median_salary. Please enter a non-negative number.")
            if not exp.get('skills'):
                raise ValidationError(f"Work experience #{idx+1} missing skills.")
        return arr