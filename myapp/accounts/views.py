"""
Django views for user authentication and profile management.

This module handles:
- User signup with profile creation
- User login/logout
- Profile viewing and editing
- Settings management (notifications, password change)
- Supabase synchronization for profile data
"""

import os
import json
import traceback
import sys
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login, authenticate
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import logout as auth_logout

# Ensure .env is loaded for environment variables
try:
    from myapp import load_env
except Exception:
    pass

from .forms import SignupForm, JOB_TITLE_CHOICES, validate_password_strength
from .models import Profile, WorkExperience, CURRENCY_CHOICES
from supabase import create_client, Client


def get_supabase_client(require_service_role: bool = False) -> Client:
    """
    Create and return a Supabase client instance.
    
    Args:
        require_service_role: If True, prefer SUPABASE_SERVICE_ROLE_KEY for writes.
                             Falls back to SUPABASE_KEY with a warning if service role key is missing.
    
    Returns:
        Supabase Client instance
    
    Raises:
        RuntimeError: If required environment variables are not set
    
    Note:
        Service role key bypasses RLS (Row Level Security) policies, which is necessary
        for server-side operations. Anon keys may be blocked by RLS policies.
    """
    url = os.environ.get('SUPABASE_URL', '')
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    anon_key = os.environ.get('SUPABASE_KEY', '')

    key = ''
    if require_service_role:
        if service_key:
            key = service_key
        else:
            # Fallback to anon key but warn - updates may be blocked by RLS
            key = anon_key
            if key:
                print('Warning: SUPABASE_SERVICE_ROLE_KEY not set; falling back to SUPABASE_KEY. '
                      'Updates may be rejected by Supabase RLS.', file=sys.stderr)
    else:
        key = anon_key

    if not url or not key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY env vars not set")
    
    return create_client(url, key)


def signup_view(request):
    """
    Handle user registration and profile creation.
    
    Creates a Django User and associated Profile, then mirrors the data to Supabase.
    Does not auto-login the user after signup - they must explicitly log in.
    """
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            # Extract validated form data
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            job_title = form.cleaned_data['job_title']
            skills = form.cleaned_data['skills']
            median_salary = form.cleaned_data['median_salary']
            years_experience = form.cleaned_data.get('years_experience')
            currency = form.cleaned_data['currency']
            work_experiences = form.cleaned_data['work_experiences']
            notifications_opt_in = bool(form.cleaned_data.get('notifications'))

            # Check if user already exists
            if User.objects.filter(username=email).exists():
                form.add_error('email', 'A user with that email already exists.')
            else:
                # Create Django User
                user = User.objects.create_user(username=email, email=email, password=password)
                
                # Create Profile with user data
                profile = Profile.objects.create(
                    user=user,
                    job_title=job_title,
                    skills=skills,
                    median_salary=median_salary,
                    currency=currency,
                    years_experience=years_experience
                )
                profile.notifications_enabled = notifications_opt_in
                profile.save()
                
                # Create WorkExperience entries if provided
                for idx, we in enumerate(work_experiences):
                    WorkExperience.objects.create(
                        profile=profile,
                        job_title=we.get('job_title', ''),
                        skills=we.get('skills', []),
                        median_salary=we.get('median_salary') or None,
                        currency=we.get('currency') or currency,
                        order=idx
                    )

                # Mirror user data to Supabase (best-effort, don't block signup on failure)
                try:
                    supabase = get_supabase_client(require_service_role=True)
                    payload = {
                        "email": email,
                        "job_title": job_title,
                        "skills": skills,
                        "median_salary": str(median_salary),
                        "years_experience": str(years_experience) if years_experience is not None else None,
                        "currency": currency,
                        "work_experiences": work_experiences,
                        "notifications_enabled": notifications_opt_in,
                    }

                    # Try upsert first (updates if exists, inserts if new)
                    try:
                        resp = supabase.table('users').upsert(payload, on_conflict='email').execute()
                        # Check for errors in response
                        if hasattr(resp, 'data') and resp.data:
                            print("Supabase signup - user created/updated successfully", file=sys.stderr)
                        else:
                            print("Supabase signup - unexpected response format", file=sys.stderr)
                    except Exception as e:
                        # If upsert fails, try insert as fallback
                        print('Supabase upsert failed, trying insert. Error:', e, file=sys.stderr)
                        traceback.print_exc(file=sys.stderr)
                        try:
                            resp = supabase.table('users').insert(payload).execute()
                            if hasattr(resp, 'data') and resp.data:
                                print("Supabase signup - user inserted successfully", file=sys.stderr)
                        except Exception as e2:
                            print('Supabase insert also failed:', e2, file=sys.stderr)
                            traceback.print_exc(file=sys.stderr)
                except Exception as e:
                    # Log error but don't block signup
                    print("Supabase signup mirror failed:", e, file=sys.stderr)

                # Redirect to success page (user must log in separately)
                return redirect('accounts:signup_success')
    else:
        form = SignupForm()
    
    # Prepare template context for GET requests
    job_titles = sorted(JOB_TITLE_CHOICES)
    currency_list = [code for code, _ in CURRENCY_CHOICES]
    currency_json = json.dumps(currency_list)
    
    return render(request, 'accounts/signup.html', {
        'form': form,
        'job_titles': job_titles,
        'currency_json': currency_json
    })


class SimpleLoginView(LoginView):
    """
    Custom login view that redirects authenticated users to the chatbot page.
    
    If a 'next' parameter is provided in the URL, redirects there instead.
    """
    template_name = 'accounts/login.html'
    
    def get_success_url(self):
        # Check for redirect parameter first
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to
        # Default: redirect to chatbot page
        try:
            return reverse('chatbot:chat')
        except Exception:
            return '/'


def logout_view(request):
    """
    Log out the current user and redirect to login page.
    
    Accepts both GET and POST requests for flexibility.
    """
    try:
        auth_logout(request)
    except Exception:
        # Ignore logout errors
        pass
    return redirect('accounts:login')


def signup_success_view(request):
    """Render a simple signup success/thank-you page with a link to login."""
    return render(request, 'accounts/signup_success.html')


@login_required
def profile_view(request):
    """
    Allow logged-in users to view and edit their profile.
    
    Handles both GET (display form) and POST (process updates) requests.
    Validates all input, updates Django models, and syncs to Supabase.
    """
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)

    # Prepare template data (used for both GET and error re-renders)
    job_titles = sorted(JOB_TITLE_CHOICES)
    currency_list = [code for code, _ in CURRENCY_CHOICES]
    currency_json = json.dumps(currency_list)

    if request.method == 'POST':
        # Extract and validate form data
        email = request.POST.get('email', '').strip()
        job_title = request.POST.get('job_title', '').strip()
        skills_raw = request.POST.get('skills', '')
        median_salary_raw = request.POST.get('median_salary', '')
        years_experience_raw = request.POST.get('years_experience', '')
        currency = request.POST.get('currency', '')
        work_experiences_raw = request.POST.get('work_experiences', '[]')
        notifications_raw = request.POST.get('notifications')

        # Validate required fields
        errors = []
        if not email:
            errors.append('Email is required.')
        if not job_title:
            errors.append('Job title is required.')

        # Parse and validate skills
        skills = [s.strip() for s in (skills_raw or '').split(',') if s.strip()]
        if not skills:
            errors.append('At least one skill is required.')
        if len(skills) > 10:
            errors.append('At most 10 skills allowed.')
        
        # Validate skills against authoritative list
        try:
            from .forms import SignupForm
            SKILLS = getattr(SignupForm, 'SKILLS', [])
            unknown = [s for s in skills if s not in SKILLS]
            if unknown:
                errors.append(f"Unknown skills: {', '.join(unknown)}")
        except Exception:
            pass

        # Parse and validate median salary
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

        # Parse and validate years of experience
        years_experience = None
        if years_experience_raw is None or years_experience_raw == '':
            errors.append('Years of experience is required.')
        else:
            try:
                years_experience = float(str(years_experience_raw))
                if years_experience < 0:
                    errors.append('Years of experience must be non-negative.')
            except Exception:
                errors.append('Years of experience must be a number (e.g. 0.5).')

        # Parse and validate work experiences
        work_exps = []
        try:
            arr = json.loads(work_experiences_raw or '[]')
            if not isinstance(arr, list):
                raise ValueError('work_experiences must be a list')
            for idx, exp in enumerate(arr):
                if not exp.get('job_title'):
                    errors.append(f'Work experience #{idx+1} missing job_title.')
                
                # Validate salary
                sal = exp.get('median_salary')
                try:
                    if sal in (None, ''):
                        raise ValueError('missing')
                    s_num = float(sal)
                    if s_num < 0:
                        errors.append(f'Work experience #{idx+1} has a negative median_salary.')
                except Exception:
                    errors.append(f'Work experience #{idx+1} has invalid median_salary.')
                
                # Validate currency
                if not exp.get('currency'):
                    errors.append(f'Work experience #{idx+1} missing currency.')
                
                # Validate skills count
                sks = exp.get('skills') or []
                if len(sks) > 10:
                    errors.append(f'Work experience #{idx+1} has more than 5 skills.')
                
                work_exps.append(exp)
        except Exception:
            errors.append('Invalid work_experiences JSON.')

        # Validate currency
        if not currency:
            errors.append('Currency is required.')

        # If validation errors exist, re-render form with errors
        if errors:
            for e in errors:
                messages.error(request, e)
            
            # Re-render with posted values (need to reconstruct JSON for work experiences)
            return render(request, 'accounts/profile.html', {
                'user': user,
                'profile': profile,
                'job_titles': job_titles,
                'currency_list': currency_list,
                'currency_json': currency_json,
                'work_experiences_json': work_experiences_raw,
                'skills_json': json.dumps(skills),
            })

        # All validation passed - update Django models
        # Update user email if changed
        if email and email != user.email:
            user.email = email
            user.username = email
            user.save()

        # Update profile fields
        profile.job_title = job_title
        profile.skills = skills
        profile.median_salary = median_salary
        profile.years_experience = years_experience
        if currency:
            profile.currency = currency
        # Only update notifications if explicitly provided
        if notifications_raw is not None:
            profile.notifications_enabled = (notifications_raw.lower() in ('1', 'true', 'on'))
        profile.save()

        # Replace all work experiences (delete old, create new)
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

        # Sync to Supabase (best-effort, don't block user on failure)
        supabase_success = False
        try:
            supabase = get_supabase_client(require_service_role=True)
            payload = {
                'email': user.email,
                'job_title': profile.job_title,
                'skills': profile.skills,
                'median_salary': str(profile.median_salary) if profile.median_salary is not None else None,
                'currency': profile.currency,
                'years_experience': str(profile.years_experience) if profile.years_experience is not None else None,
                'work_experiences': work_exps,
                'notifications_enabled': profile.notifications_enabled,
            }
            
            # Try upsert first
            try:
                resp = supabase.table('users').upsert(payload, on_conflict='email').execute()
                # Check if response indicates success
                if hasattr(resp, 'data') and resp.data:
                    supabase_success = True
                    print('Supabase profile update - success', file=sys.stderr)
                else:
                    print('Supabase profile update - unexpected response format', file=sys.stderr)
            except Exception as e:
                # Fallback to insert if upsert fails
                print('Supabase upsert failed for profile update, trying insert. Error:', e, file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                try:
                    resp = supabase.table('users').insert(payload).execute()
                    if hasattr(resp, 'data') and resp.data:
                        supabase_success = True
                        print('Supabase profile update - insert success', file=sys.stderr)
                    else:
                        print('Supabase profile update - insert failed (no data in response)', file=sys.stderr)
                except Exception as e2:
                    print('Supabase insert also failed for profile update:', e2, file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)
        except Exception as e:
            # Log error but continue - don't block user
            print('Supabase profile update failed:', e, file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

        # Show success message (always show if Django update succeeded)
        messages.success(request, 'Profile updated successfully.')
        
        # Redirect to profile page to show success message
        return redirect('accounts:profile')

    # GET request: prepare existing data for form
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
    """
    Allow users to manage settings: notifications and password.
    
    Handles two separate forms on the same page:
    1. Notifications toggle form (submit button: 'save_notifications')
    2. Password change form (submit button: 'change_password')
    """
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)

    notif_message = None
    pwd_message = None

    if request.method == 'POST':
        # Determine which form was submitted
        if 'save_notifications' in request.POST:
            # Handle notifications preference update
            new_val = request.POST.get('notifications')
            profile.notifications_enabled = (new_val == 'on' or new_val in ('1', 'true'))
            profile.save()
            
            # Sync to Supabase (best-effort)
            try:
                supabase = get_supabase_client(require_service_role=True)
                payload = {
                    'email': user.email,
                    'notifications_enabled': profile.notifications_enabled,
                }
                try:
                    resp = supabase.table('users').upsert(payload, on_conflict='email').execute()
                    if hasattr(resp, 'data') and resp.data:
                        print('Supabase settings upsert - success', file=sys.stderr)
                    else:
                        print('Supabase settings upsert - unexpected response', file=sys.stderr)
                except Exception as e:
                    print('Supabase settings upsert failed:', e, file=sys.stderr)
            except Exception as e:
                print('Supabase settings mirror failed:', e, file=sys.stderr)
            
            notif_message = 'Notification preferences saved.'

        elif 'change_password' in request.POST:
            # Handle password change
            form = PasswordChangeForm(user, request.POST)
            if form.is_valid():
                # Enforce password strength requirements (same as signup)
                try:
                    new_pw = form.cleaned_data.get('new_password1', '')
                    validate_password_strength(new_pw)
                except Exception as e:
                    # Attach validation error to form
                    try:
                        from django.core.exceptions import ValidationError
                        if isinstance(e, ValidationError):
                            for msg in e.messages:
                                form.add_error('new_password1', msg)
                        else:
                            form.add_error('new_password1', str(e))
                    except Exception:
                        form.add_error('new_password1', 'Password does not meet requirements.')

            # Re-check validity after potential password strength validation
            if form.is_valid():
                form.save()
                # Keep user logged in after password change
                update_session_auth_hash(request, form.user)
                pwd_message = 'Password changed successfully.'
            else:
                # Display form errors
                pwd_message = form.errors.as_text()

    # Prepare password change form for display
    pwd_form = PasswordChangeForm(user)
    
    # Add Bootstrap classes to password form fields
    try:
        for fname in ('old_password', 'new_password1', 'new_password2'):
            if fname in pwd_form.fields:
                pwd_form.fields[fname].widget.attrs.update({
                    'class': 'form-control',
                    'id': f'id_{fname}'
                })
                # Hide Django's default password help text
                try:
                    pwd_form.fields[fname].help_text = ''
                except Exception:
                    pass
    except Exception:
        # Ignore widget attribute failures
        pass

    return render(request, 'accounts/settings.html', {
        'profile': profile,
        'pwd_form': pwd_form,
        'notif_message': notif_message,
        'pwd_message': pwd_message,
    })
