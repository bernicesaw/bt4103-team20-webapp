import os
import json
import traceback
import sys
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login, authenticate
from django.contrib import messages

# ensure .env is loaded
try:
    from myapp import load_env  # loads .env into environment if present
except Exception:
    pass

from .forms import SignupForm, JOB_TITLE_CHOICES
from .models import Profile, WorkExperience, CURRENCY_CHOICES
import json

from supabase import create_client, Client


def get_supabase_client(require_service_role: bool = False) -> Client:
    """Return a Supabase client.

    If require_service_role is True, prefer SUPABASE_SERVICE_ROLE_KEY. If it's
    missing we fall back to SUPABASE_KEY but emit a warning because anon keys
    often don't have permission to update rows (RLS).
    """
    url = os.environ.get('SUPABASE_URL', '')
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    anon_key = os.environ.get('SUPABASE_KEY', '')

    key = ''
    if require_service_role:
        if service_key:
            key = service_key
        else:
            # fallback but warn: updates may be blocked by RLS when using anon key
            key = anon_key
            if key:
                print('Warning: SUPABASE_SERVICE_ROLE_KEY not set; falling back to SUPABASE_KEY. Updates may be rejected by Supabase RLS.', file=sys.stderr)
    else:
        key = anon_key

    if not url or not key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY env vars not set")
    return create_client(url, key)


def signup_view(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            job_title = form.cleaned_data['job_title']
            skills = form.cleaned_data['skills']
            median_salary = form.cleaned_data['median_salary']
            currency = form.cleaned_data['currency']
            work_experiences = form.cleaned_data['work_experiences']
            notifications_opt_in = bool(form.cleaned_data.get('notifications'))

            # create Django user
            if User.objects.filter(username=email).exists():
                form.add_error('email', 'A user with that email already exists.')
            else:
                user = User.objects.create_user(username=email, email=email, password=password)
                profile = Profile.objects.create(
                    user=user,
                    job_title=job_title,
                    skills=skills,
                    median_salary=median_salary,
                    currency=currency
                )
                # store notification preference
                profile.notifications_enabled = notifications_opt_in
                profile.save()
                # create work experiences
                for idx, we in enumerate(work_experiences):
                    WorkExperience.objects.create(
                        profile=profile,
                        job_title=we.get('job_title', ''),
                        skills=we.get('skills', []),
                        median_salary=we.get('median_salary') or None,
                        currency=we.get('currency') or currency,
                        order=idx
                    )

                # Mirror to Supabase and print response for debugging
                try:
                    # Prefer service role key for server-side writes so upsert/update
                    # operations are allowed even when RLS is enabled.
                    supabase = get_supabase_client(require_service_role=True)
                    # Prepare payload using native Python types for JSONB columns
                    payload = {
                        "email": email,
                        "job_title": job_title,
                        "skills": skills,
                        "median_salary": str(median_salary),
                        "currency": currency,
                        "work_experiences": work_experiences,
                        "notifications_enabled": notifications_opt_in,
                    }

                    # Use upsert so repeated signups update existing record instead of failing
                    try:
                        # Use email as the conflict target so upsert matches on the unique email column
                        resp = supabase.table('users').upsert(payload, on_conflict='email').execute()
                    except Exception as e:
                        # If upsert isn't supported or fails, fallback to insert and log the error
                        print('Supabase upsert failed, trying insert. Error:', e, file=sys.stderr)
                        traceback.print_exc(file=sys.stderr)
                        try:
                            resp = supabase.table('users').insert(payload).execute()
                        except Exception as e2:
                            print('Supabase insert also failed:', e2, file=sys.stderr)
                            traceback.print_exc(file=sys.stderr)
                            resp = None

                    # Print details to server console for debugging
                    if resp is not None:
                        try:
                            data = getattr(resp, 'data', None)
                            error = getattr(resp, 'error', None)
                            status = getattr(resp, 'status_code', None)
                            print("Supabase response - status:", status, file=sys.stderr)
                            print("Supabase response - data:", data, file=sys.stderr)
                            print("Supabase response - error:", error, file=sys.stderr)
                            # Surface a clearer server-side note when permission-like
                            # status codes are returned so the developer knows to
                            # provide a service role key.
                            if status in (401, 403):
                                print('Supabase returned permission error (401/403). Ensure SUPABASE_SERVICE_ROLE_KEY is set for server writes.', file=sys.stderr)
                        except Exception:
                            try:
                                print("Supabase response (repr):", repr(resp), file=sys.stderr)
                            except Exception:
                                print("Supabase response: (unable to repr)", file=sys.stderr)
                except Exception as e:
                    # do not block signup on Supabase failure, but notify admin/log
                    print("Supabase insert failed:", e, file=sys.stderr)

                # After creating the account and mirroring to Supabase, show a success page.
                # We do not auto-login here so the user can explicitly log in via the login page.
                return redirect('accounts:signup_success')
    else:
        form = SignupForm()
    # prepare job titles for client-side datalist (sorted alphabetically)
    # JOB_TITLE_CHOICES is a list of labels
    job_titles = sorted(JOB_TITLE_CHOICES)
    # expose currency codes to template as JSON for client-side selects
    currency_list = [code for code, _ in CURRENCY_CHOICES]
    currency_json = json.dumps(currency_list)
    return render(request, 'accounts/signup.html', {'form': form, 'job_titles': job_titles, 'currency_json': currency_json})


from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

from django.contrib.auth import logout as auth_logout
from django.urls import reverse
from django.shortcuts import redirect


class SimpleLoginView(LoginView):
    template_name = 'accounts/login.html'
    
    def get_success_url(self):
        # If a next parameter (redirect) was provided, use it.
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to
        # Default: send users who logged in from the login page to AskAI.
        try:
            return reverse('chatbot:chat')
        except Exception:
            return '/'


def logout_view(request):
    """Log out the current user and redirect to the login page.

    Accepts GET and POST so the Sign Out link can be a simple anchor.
    """
    try:
        auth_logout(request)
    except Exception:
        # ignore logout errors
        pass
    return redirect('accounts:login')


def signup_success_view(request):
    """Render a simple signup success/thank-you page with a button linking to the login page."""
    return render(request, 'accounts/signup_success.html')


@login_required
def profile_view(request):
    """Allow logged-in users to view and edit their profile (fields mirror the signup form)."""
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)

    # prepare lists for template
    job_titles = sorted(JOB_TITLE_CHOICES)
    currency_list = [code for code, _ in CURRENCY_CHOICES]
    currency_json = json.dumps(currency_list)

    if request.method == 'POST':
        # basic field extraction and validation
        email = request.POST.get('email', '').strip()
        job_title = request.POST.get('job_title', '').strip()
        skills_raw = request.POST.get('skills', '')
        median_salary_raw = request.POST.get('median_salary', '')
        currency = request.POST.get('currency', '')
        work_experiences_raw = request.POST.get('work_experiences', '[]')
        # notifications (may be changed elsewhere via settings page)
        notifications_raw = request.POST.get('notifications')

        # validate/minimal checks (ensure required fields from signup are also required here)
        errors = []
        if not email:
            errors.append('Email is required.')
        if not job_title:
            errors.append('Job title is required.')

        # parse skills (required on signup, enforce here too)
        skills = [s.strip() for s in (skills_raw or '').split(',') if s.strip()]
        if not skills:
            errors.append('At least one skill is required.')
        if len(skills) > 5:
            errors.append('At most 5 skills allowed.')
        # ensure skills are from authoritative list if available
        try:
            from .forms import SignupForm
            SKILLS = getattr(SignupForm, 'SKILLS', [])
            unknown = [s for s in skills if s not in SKILLS]
            if unknown:
                errors.append(f"Unknown skills: {', '.join(unknown)}")
        except Exception:
            pass

        # median salary parse (required on signup)
        median_salary = None
        if not median_salary_raw:
            errors.append('Median salary is required.')
        else:
            try:
                median_salary = float(str(median_salary_raw).replace(',', ''))
                if median_salary < 0:
                    errors.append('Median salary must be non-negative.')
            except Exception:
                errors.append('Median salary must be a number.')

        # work_experiences parse and validation
        work_exps = []
        try:
            arr = json.loads(work_experiences_raw or '[]')
            if not isinstance(arr, list):
                raise ValueError('work_experiences must be a list')
            for idx, exp in enumerate(arr):
                if not exp.get('job_title'):
                    errors.append(f'Work experience #{idx+1} missing job_title.')
                # salary validation
                sal = exp.get('median_salary')
                try:
                    if sal in (None, ''):
                        raise ValueError('missing')
                    s_num = float(sal)
                    if s_num < 0:
                        errors.append(f'Work experience #{idx+1} has a negative median_salary.')
                except Exception:
                    errors.append(f'Work experience #{idx+1} has invalid median_salary.')
                # currency
                if not exp.get('currency'):
                    errors.append(f'Work experience #{idx+1} missing currency.')
                # skills count check
                sks = exp.get('skills') or []
                if len(sks) > 5:
                    errors.append(f'Work experience #{idx+1} has more than 5 skills.')
                work_exps.append(exp)
        except Exception:
            errors.append('Invalid work_experiences JSON.')

        # Ensure top-level currency is present (signup requires it)
        if not currency:
            errors.append('Currency is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            # re-render form with posted values
            return render(request, 'accounts/profile.html', {
                'user': user,
                'profile': profile,
                'job_titles': job_titles,
                'currency_list': currency_list,
                'currency_json': currency_json,
                'work_experiences_json': work_experiences_raw,
            })

        # all good: persist changes
        # update user email
        if email and email != user.email:
            user.email = email
            user.username = email
            user.save()

        profile.job_title = job_title
        profile.skills = skills
        profile.median_salary = median_salary
        # Only update notifications if provided in the profile edit form
        if notifications_raw is not None:
            profile.notifications_enabled = (notifications_raw.lower() in ('1', 'true', 'on'))
        if currency:
            profile.currency = currency
        profile.save()

        # replace work experiences
        profile.work_experiences.all().delete()
        for idx, we in enumerate(work_exps):
            WorkExperience.objects.create(
                profile=profile,
                job_title=we.get('job_title', ''),
                skills=we.get('skills', []),
                median_salary=we.get('median_salary') or None,
                currency=we.get('currency') or profile.currency,
                order=idx
            )

        # Mirror profile update to Supabase (best-effort, do not block user)
        # Mirror to Supabase (best-effort) and notify the user of the outcome.
        try:
            # Prefer service role key for server-side writes so updates are allowed
            supabase = get_supabase_client(require_service_role=True)
            payload = {
                'email': user.email,
                'job_title': profile.job_title,
                'skills': profile.skills,
                'median_salary': str(profile.median_salary) if profile.median_salary is not None else None,
                'currency': profile.currency,
                'work_experiences': work_exps,
                'notifications_enabled': profile.notifications_enabled,
            }
            resp = None
            # Debug: log payload we will send to Supabase
            try:
                print('Supabase profile update payload:', payload, file=sys.stderr)
            except Exception:
                pass
            try:
                # Use email as the conflict target so upsert matches on the unique email column
                resp = supabase.table('users').upsert(payload, on_conflict='email').execute()
            except Exception as e:
                print('Supabase upsert failed for profile update, trying insert. Error:', e, file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                try:
                    resp = supabase.table('users').insert(payload).execute()
                except Exception as e2:
                    print('Supabase insert also failed for profile update:', e2, file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)
                    resp = None

            # Interpret response and add a message for the user
            if resp is not None:
                # try to detect an error attribute
                err = getattr(resp, 'error', None)
                status = getattr(resp, 'status_code', None)
                # Log permission issues or errors server-side only. Do not show
                # Supabase-specific messages in the UI.
                if status in (401, 403):
                    print('Supabase profile update - permission denied (status):', status, file=sys.stderr)
                elif err:
                    print('Supabase profile update - error:', err, file=sys.stderr)
                else:
                    print('Supabase profile update - status:', status, file=sys.stderr)
            else:
                # Supabase response was None (insert/upsert attempts failed).
                # Keep this as a server-side log only.
                print('Supabase profile update - no response (insert/upsert failed)', file=sys.stderr)
        except Exception as e:
            # Do not block the user; surface a small warning so they know mirroring failed.
            # Keep errors logged server-side; don't add Supabase-specific UI messages.
            print('Supabase profile update failed:', e, file=sys.stderr)

        messages.success(request, 'Profile updated successfully.')
        return redirect('accounts:profile')

    # GET: prepare existing work experiences JSON
    we_list = []
    for we in profile.work_experiences.all():
        we_list.append({
            'job_title': we.job_title,
            'skills': we.skills or [],
            'median_salary': str(we.median_salary) if we.median_salary is not None else None,
            'currency': we.currency,
        })
    work_experiences_json = json.dumps(we_list)
    skills_json = json.dumps(profile.skills or [])

    return render(request, 'accounts/profile.html', {
        'user': user,
        'profile': profile,
        'job_titles': job_titles,
        'currency_list': currency_list,
        'currency_json': currency_json,
        'work_experiences_json': work_experiences_json,
        'skills_json': skills_json,
    })


@login_required
def settings_view(request):
    """Allow the user to toggle notification preference and change password.

    Two POST actions are supported on the same page:
    - notifications form: includes 'save_notifications' submit button
    - password change form: uses Django's PasswordChangeForm and 'change_password' submit
    """
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)

    notif_message = None
    pwd_message = None

    if request.method == 'POST':
        # Distinguish which form was submitted
        if 'save_notifications' in request.POST:
            # Toggle notification preference
            new_val = request.POST.get('notifications')
            profile.notifications_enabled = (new_val == 'on' or new_val in ('1', 'true'))
            profile.save()
            # Mirror to Supabase (best-effort)
            try:
                supabase = get_supabase_client(require_service_role=True)
                payload = {
                    'email': user.email,
                    'notifications_enabled': profile.notifications_enabled,
                }
                try:
                    resp = supabase.table('users').upsert(payload, on_conflict='email').execute()
                    print('Supabase settings upsert response:', getattr(resp, 'status_code', None), file=sys.stderr)
                except Exception as e:
                    print('Supabase settings upsert failed:', e, file=sys.stderr)
            except Exception as e:
                print('Supabase settings mirror failed:', e, file=sys.stderr)
            notif_message = 'Notification preferences saved.'

        elif 'change_password' in request.POST:
            form = PasswordChangeForm(user, request.POST)
            if form.is_valid():
                form.save()
                # Keep the user logged in after password change
                update_session_auth_hash(request, form.user)
                pwd_message = 'Password changed successfully.'
            else:
                # attach form errors to pwd_message to display
                pwd_message = form.errors.as_text()

    # Prepare initial forms/values
    pwd_form = PasswordChangeForm(user)
    # Ensure password inputs have Bootstrap classes when rendered. We set these
    # attributes server-side to avoid a dependency on third-party template
    # filters (e.g. django-widget-tweaks) in templates.
    try:
        for fname in ('old_password', 'new_password1', 'new_password2'):
            if fname in pwd_form.fields:
                pwd_form.fields[fname].widget.attrs.update({'class': 'form-control', 'id': f'id_{fname}'})
    except Exception:
        # Ignore widget attribute failures; rendering without classes is acceptable
        pass

    return render(request, 'accounts/settings.html', {
        'profile': profile,
        'pwd_form': pwd_form,
        'notif_message': notif_message,
        'pwd_message': pwd_message,
    })