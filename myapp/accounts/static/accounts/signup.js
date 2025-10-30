// signup.js - handles skills chips, suggestions, work experience entries, and salary formatting

// Format a number into locale string with 2 decimals
function formatCurrencyInput(el) {
  if (!el) return;
  let v = (el.value || '').toString().replace(/,/g, '');
  if (v === '') return;
  let num = parseFloat(v);
  if (isNaN(num)) return;
  // If the input is a number input, avoid inserting commas (which break number inputs).
  // Use a plain numeric string with two decimals so the user can continue editing large numbers.
  if (el.type === 'number') {
    el.value = num.toFixed(2);
  } else {
    el.value = num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
}

function initSignupForm() {
  const skillsInput = document.getElementById('skills-input');
  const skillsList = document.getElementById('skills-list');
  const skillsHidden = document.getElementById('skills-hidden');
  const addWorkBtn = document.getElementById('add-work-exp');
  const workExpsContainer = document.getElementById('work-exps');
  const workExpsHidden = document.getElementById('work-experiences-hidden');
  const skillSuggestionsBox = document.getElementById('skill-suggestions');

  // lightweight skill suggestions; extend as needed
  const SKILL_SUGGESTIONS = [
    'Ada','Alibaba Cloud','Amazon Redshift','Amazon Web Services (Aws)','Android','Angular','Angular.Js','Angularjs',
    'Ansible','Apex','Apl','Apt','Arduino','Asp.Net','Asp.Net Core','Assembly','Astro','Aws','Axum','Bash/Shell',
    'Bash/Shell (All Shells)','Bash/Shell/Powershell','Bigquery','Blazor','Bun','C','C#','C++','Cargo','Cassandra',
    'Chocolatey','Clickhouse','Clojure','Cloud Firestore','Cloudflare','Cobol','Cockroachdb','Codeigniter',
    'Colocation','Composer','Cosmos Db','Couch Db','Couchbase','Couchdb','Crystal','Dart','Databricks','Databricks Sql',
    'Datadog','Datomic','Delphi','Deno','Digital Ocean','Digitalocean','Django','Docker','Drupal','Duckdb','Dynamodb',
    'Elasticsearch','Elixir','Elm','Erlang','Eventstoredb','Express','F#','Fastapi','Fastify','Firebase',
    'Firebase Realtime Database','Firebird','Flask','Flow','Fly.Io','Fortran','Gatsby','Gdscript','Gleam','Go',
    'Google Cloud','Google Cloud Platform','Gradle','Groovy','H2','Haskell','Heroku','Hetzner','Homebrew','Html/Css',
    'Htmx','Ibm Cloud','Ibm Cloud Or Watson','Ibm Db2','Influxdb','Ios','Java','Javascript','Jquery','Julia','Kotlin',
    'Kubernetes','Laravel','Linode','Linode, Now Akamai','Linux','Lisp','Lit','Lua','Macos','Make','Managed Hosting',
    'Mariadb','Matlab','Maven (Build Tool)','Micropython','Microsoft Access','Microsoft Azure','Microsoft Sql Server',
    'Mojo','Mongodb','Msbuild','Mysql','Neo4J','Nestjs','Netlify','New Relic','Next.Js','Nim','Ninja','Node.Js','Npm',
    'Nuget','Nuxt.Js','Objective-C','Ocaml','Openshift','Openstack','Oracle','Oracle Cloud Infrastructure',
    'Oracle Cloud Infrastructure (Oci)','Ovh','Pacman','Perl','Phoenix','Php','Pip','Play Framework','Pnpm','Pocketbase',
    'Podman','Poetry','Postgresql','Powershell','Presto','Prolog','Prometheus','Python','Pythonanywhere','Qwik','R',
    'Railway','Raku','Raspberry Pi','Ravendb','React','React.Js','Redis','Remix','Render','Ruby','Ruby On Rails','Rust',
    'Sas','Scala','Scaleway','Slack Apps And Integrations','Snowflake','Solid.Js','Solidity','Solr','Splunk','Spring',
    'Spring Boot','Sql','Sqlite','Strapi','Supabase','Svelte','Swift','Symfony','Terraform','Tidb','Typescript','Valkey',
    'Vba','Vercel','Visual Basic (.Net)','Vite','Vmware','Vue.Js','Vultr','Webpack','Windows','Wordpress','Yandex Cloud',
    'Yarn','Yii 2','Zephyr','Zig'
  ];

  let skills = [];
  let workExps = [];

  // prefill skills from hidden input if present
  try {
    if (window && window.PREFILL_SKILLS) {
      // PREFILL_SKILLS is expected to be an array
      try { skills = (window.PREFILL_SKILLS || []).slice(0,5); } catch(e) { /* noop */ }
    } else if (skillsHidden && skillsHidden.value) {
      skills = (skillsHidden.value || '').split(',').map(s => s.trim()).filter(Boolean).slice(0,5);
    }
  } catch (e) { skills = []; }
  renderSkills();

  function renderSkillSuggestions(filter) {
    if (!skillSuggestionsBox) return;
    skillSuggestionsBox.innerHTML = '';
    const q = (filter||'').toLowerCase().trim();
    if (!q) return;
    const matches = SKILL_SUGGESTIONS.filter(s => s.toLowerCase().includes(q) && !skills.includes(s)).slice(0,8);
    matches.forEach(m => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn btn-sm btn-outline-secondary me-1 mb-1';
      b.textContent = m;
      b.onclick = () => { addSkill(m); skillsInput.focus(); };
      skillSuggestionsBox.appendChild(b);
    });
  }

  function renderSkills() {
    if (!skillsList) return;
    skillsList.innerHTML = '';
    skills.forEach((s, idx) => {
      const span = document.createElement('span');
      span.className = 'badge bg-secondary text-white me-1';
      span.style.cursor = 'pointer';
      span.textContent = s + ' ×';
      span.onclick = () => {
        skills.splice(idx, 1);
        renderSkills();
      };
      skillsList.appendChild(span);
    });
    if (skillsHidden) skillsHidden.value = skills.join(', ');
  }

  function addSkill(val) {
    const v = (val || (skillsInput ? skillsInput.value : '') || '').trim();
    if (!v) return;
    if (skills.length >= 5) {
      alert('Max 5 skills allowed');
      if (skillsInput) skillsInput.value = '';
      return;
    }
    if (!skills.includes(v)) skills.push(v);
    if (skillsInput) skillsInput.value = '';
    renderSkills();
    // clear any top-level skills validation now that a chip exists
    try { clearFieldError(skillsInput); } catch (e) {}
    renderSkillSuggestions('');
  }

  if (skillsInput) {
    // show suggestions and clear validation while typing
    skillsInput.addEventListener('input', (e) => { renderSkillSuggestions(e.target.value); clearFieldError(skillsInput); });
    skillsInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } });
  }

  function addWorkExp(prefill) {
    if (!workExpsContainer) return;
    if (workExps.length >= 10) {
      alert('Max 10 work experiences allowed');
      return;
    }
    const idx = workExps.length;
    const container = document.createElement('div');
    container.className = 'work-exp border rounded p-2 mb-2';

  const jobTitle = document.createElement('input');
    jobTitle.placeholder = 'Job Title';
    jobTitle.className = 'form-control mb-2';
    jobTitle.setAttribute('list', 'jobtitles');
    jobTitle.required = true;

    // per-experience skills: an input, suggestions, and chips list
    const expSkillsInput = document.createElement('input');
    expSkillsInput.placeholder = 'Type a skill';
  expSkillsInput.className = 'form-control mb-2';
  // Do not mark the visible per-experience skills input as required —
  // validation is performed against the selected chips (hidden field).
    const expSkillSuggestions = document.createElement('div');
    expSkillSuggestions.className = 'mb-2';
    const expSkillsList = document.createElement('div');
    expSkillsList.className = 'mb-2';
    const expSkillsHidden = document.createElement('input');
    expSkillsHidden.type = 'hidden';
    let expSkillsArr = [];

    function renderExpSkills() {
      expSkillsList.innerHTML = '';
      expSkillsArr.forEach((s, i) => {
        const span = document.createElement('span');
        span.className = 'badge bg-secondary text-white me-1';
        span.style.cursor = 'pointer';
        span.textContent = s + ' ×';
        span.onclick = () => { expSkillsArr.splice(i,1); renderExpSkills(); };
        expSkillsList.appendChild(span);
      });
      expSkillsHidden.value = expSkillsArr.join(', ');
      // clear any previous validation state for this experience skills input
      try { clearFieldError(expSkillsInput); } catch (e) {}
    }

    function renderExpSkillSuggestions(q) {
      expSkillSuggestions.innerHTML = '';
      const ql = (q||'').toLowerCase().trim();
      if (!ql) return;
      const matches = SKILL_SUGGESTIONS.filter(s => s.toLowerCase().includes(ql) && !expSkillsArr.includes(s)).slice(0,6);
      matches.forEach(m => {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'btn btn-sm btn-outline-secondary me-1 mb-1'; b.textContent = m;
        b.onclick = () => { expSkillsArr.push(m); expSkillsInput.value = ''; renderExpSkills(); expSkillsInput.focus(); };
        expSkillSuggestions.appendChild(b);
      });
    }

  expSkillsInput.addEventListener('input', (e)=> renderExpSkillSuggestions(e.target.value));
    expSkillsInput.addEventListener('keydown', (e)=> { if (e.key === 'Enter') { e.preventDefault(); const v=expSkillsInput.value.trim(); if(v && expSkillsArr.length<5 && !expSkillsArr.includes(v)){ expSkillsArr.push(v); expSkillsInput.value=''; renderExpSkills(); } } });

    const salary = document.createElement('input');
  // Use number input so mobile keyboards show numeric by default, but avoid comma formatting
  salary.type = 'number';
  salary.inputMode = 'decimal';
  salary.placeholder = 'Monthly Median Salary';
    salary.className = 'form-control me-2';
    salary.style.maxWidth = '260px';
  // accept two decimals and disallow negatives
  salary.setAttribute('step', '0.01');
  salary.setAttribute('min', '0');
  salary.required = true;

    // Prevent negative input on the client as the user types (strip minus signs)
    salary.addEventListener('input', () => {
      try {
        if (salary.value && salary.value.toString().startsWith('-')) {
          // remove all minus signs
          salary.value = salary.value.toString().replace(/-/g, '');
        }
      } catch (e) { /* noop */ }
    });

    const currency = document.createElement('select');
    currency.className = 'form-select w-auto';
    // prefer server-injected currency list; fallback to a small set if not provided
    const CURRENCY_OPTIONS = (window && window.CURRENCY_OPTIONS) ? window.CURRENCY_OPTIONS : ['USD','SGD','EUR','GBP'];
  // placeholder option
  const placeholderOpt = document.createElement('option');
  placeholderOpt.value = '';
  placeholderOpt.text = 'Select currency';
  placeholderOpt.selected = true;
  placeholderOpt.disabled = true;
  currency.appendChild(placeholderOpt);
  CURRENCY_OPTIONS.forEach(c => { const o = document.createElement('option'); o.value = c; o.text = c; currency.appendChild(o); });
  // require a selection for per-experience currency
  currency.required = true;

  const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn btn-sm btn-outline-danger ms-2';
    removeBtn.textContent = 'Remove';
    removeBtn.onclick = () => {
      workExps.splice(idx, 1);
      container.remove();
      updateWorkHidden();
    };

  salary.addEventListener('blur', () => formatCurrencyInput(salary));

    // clear validation when user interacts
    jobTitle.addEventListener('input', () => clearFieldError(jobTitle));
    salary.addEventListener('input', () => clearFieldError(salary));
    currency.addEventListener('change', () => clearFieldError(currency));
    expSkillsInput.addEventListener('input', () => clearFieldError(expSkillsInput));

  container.appendChild(jobTitle);
  // job title required indicator
  // skills input for this experience
  container.appendChild(expSkillsInput);
  container.appendChild(expSkillSuggestions);
  container.appendChild(expSkillsList);
  container.appendChild(expSkillsHidden);

    const row = document.createElement('div');
    row.className = 'd-flex align-items-center';
    row.appendChild(salary);
    row.appendChild(currency);
    row.appendChild(removeBtn);
    container.appendChild(row);

    workExpsContainer.appendChild(container);

    const entry = { jobTitle, salary, currency, expSkillsHidden, expSkillsInput };
    workExps.push(entry);
    // if prefill provided, populate fields
    if (prefill && typeof prefill === 'object') {
      if (prefill.job_title) jobTitle.value = prefill.job_title;
      if (prefill.median_salary !== undefined && prefill.median_salary !== null) salary.value = prefill.median_salary;
      if (prefill.currency) currency.value = prefill.currency;
      if (Array.isArray(prefill.skills) && prefill.skills.length) {
        expSkillsArr = prefill.skills.slice(0,5);
        renderExpSkills();
      }
      // clear validation state for this prefilling
      clearFieldError(jobTitle);
      clearFieldError(salary);
      clearFieldError(currency);
      clearFieldError(expSkillsInput);
    }

    updateWorkHidden();
  }

  function clearFieldError(el) {
    if (!el) return;
    el.classList.remove('is-invalid');
    // remove any sibling invalid-feedback msg
    const next = el.parentNode && el.parentNode.querySelector('.invalid-feedback');
    if (next) next.remove();
  }

  function markFieldError(el, msg) {
    if (!el) return;
    el.classList.add('is-invalid');
    // create or update invalid-feedback
    let fb = el.parentNode && el.parentNode.querySelector('.invalid-feedback');
    if (!fb) {
      fb = document.createElement('div');
      fb.className = 'invalid-feedback';
      el.parentNode.appendChild(fb);
    }
    fb.textContent = msg || 'Invalid value';
  }

  function updateWorkHidden() {
    if (!workExpsHidden) return;
    const arr = workExps.map(w => {
      // support per-experience skills hidden field if present
      let skillsArr = [];
      if (w.expSkillsHidden) {
        skillsArr = (w.expSkillsHidden.value || '').split(',').map(s => s.trim()).filter(Boolean);
      } else {
        skillsArr = (w.skillsField.value || '').split(',').map(s => s.trim()).filter(Boolean);
      }
      if (skillsArr.length > 5) skillsArr = skillsArr.slice(0,5);
      let salaryRaw = (w.salary.value||'').toString().replace(/,/g, '');
      let salaryNum = salaryRaw ? parseFloat(salaryRaw) : null;
      return {
        job_title: w.jobTitle.value || '',
        skills: skillsArr,
        median_salary: salaryNum,
        // do not silently default currency here; allow server-side validation to catch empty values
        currency: w.currency.value || ''
      };
    });
    workExpsHidden.value = JSON.stringify(arr);
  }

  function validateWorkExps() {
    let valid = true;
    let firstInvalid = null;
    workExps.forEach((w, idx) => {
      // clear previous state
      clearFieldError(w.jobTitle);
      clearFieldError(w.salary);
      clearFieldError(w.currency);
      // job title
      if (!w.jobTitle.value || !w.jobTitle.value.trim()) {
        markFieldError(w.jobTitle, 'Job title is required.');
        valid = false;
        if (!firstInvalid) firstInvalid = w.jobTitle;
      }
      // salary
      const salaryRaw = (w.salary.value||'').toString().replace(/,/g, '');
      const num = salaryRaw ? parseFloat(salaryRaw) : NaN;
      if (isNaN(num)) {
        markFieldError(w.salary, 'Enter a valid number for salary.');
        valid = false;
        if (!firstInvalid) firstInvalid = w.salary;
      } else if (num < 0) {
        markFieldError(w.salary, 'Salary must be non-negative.');
        valid = false;
        if (!firstInvalid) firstInvalid = w.salary;
      }
      // currency
      if (!w.currency.value) {
        markFieldError(w.currency, 'Please select a currency.');
        valid = false;
        if (!firstInvalid) firstInvalid = w.currency;
      }
      // skills
      let skillsArr = [];
      if (w.expSkillsHidden) skillsArr = (w.expSkillsHidden.value||'').split(',').map(s=>s.trim()).filter(Boolean);
      if (skillsArr.length === 0) {
        // mark the hidden input's previous visible element if possible
        if (w.expSkillsHidden && w.expSkillsHidden.previousSibling) markFieldError(w.expSkillsHidden.previousSibling, 'Add at least one skill.');
        valid = false;
        if (!firstInvalid && w.expSkillsHidden && w.expSkillsHidden.previousSibling) firstInvalid = w.expSkillsHidden.previousSibling;
      } else if (skillsArr.length > 5) {
        if (w.expSkillsHidden && w.expSkillsHidden.previousSibling) markFieldError(w.expSkillsHidden.previousSibling, 'At most 5 skills allowed.');
        valid = false;
        if (!firstInvalid && w.expSkillsHidden && w.expSkillsHidden.previousSibling) firstInvalid = w.expSkillsHidden.previousSibling;
      }
    });
    if (!valid && firstInvalid) {
      try { firstInvalid.focus(); } catch (e) {}
    }
    return valid;
  }

  if (addWorkBtn) addWorkBtn.addEventListener('click', addWorkExp);

  // If there are pre-existing work experiences in the hidden input, populate them
  try {
    // Prefer server-injected window.PREFILL_WORK_EXPERIENCES when present
    if (window && window.PREFILL_WORK_EXPERIENCES) {
      try {
        const pre = window.PREFILL_WORK_EXPERIENCES;
        if (Array.isArray(pre) && pre.length) {
          workExpsContainer.innerHTML = '';
          workExps = [];
          pre.forEach(p => addWorkExp(p));
        }
      } catch (e) { console.warn('Failed to prefill from window.PREFILL_WORK_EXPERIENCES', e); }
    } else if (workExpsHidden && workExpsHidden.value) {
      const pre = JSON.parse(workExpsHidden.value || '[]');
      if (Array.isArray(pre) && pre.length) {
        // clear any existing UI
        workExpsContainer.innerHTML = '';
        workExps = [];
        pre.forEach(p => addWorkExp(p));
      }
    }
  } catch (e) { console.warn('Failed to prefill work experiences', e); }

  // update hidden fields on form submit
  const form = document.getElementById('signup-form');
  if (form) {
    form.addEventListener('submit', (e) => {
      if (skillsHidden) skillsHidden.value = skills.join(', ');
      updateWorkHidden();
      // run client-side validation for experiences and top-level skills (chips)
      const workOk = validateWorkExps();
      let ok = workOk;
      if (!skills || skills.length === 0) {
        // require at least one selected top-level skill (chips)
        markFieldError(skillsInput, 'Add at least one skill.');
        ok = false;
        if (workOk) {
          try { skillsInput.focus(); } catch (e) {}
        }
      }
      if (!ok) {
        e.preventDefault();
      }
    });
  }
}

// initialize behavior when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // format main median salary field if present
  const mainSalary = document.getElementById('id_median_salary');
  if (mainSalary) mainSalary.addEventListener('blur', () => formatCurrencyInput(mainSalary));
  // initialize dynamic form behaviors
  try { initSignupForm(); } catch (e) { console.warn('initSignupForm failed', e); }
});