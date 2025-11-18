from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q, Avg
from .models import WorkerProfile, JobRequest, Rating, TaskHistory, JobMatch, Skill
from .forms import CustomUserCreationForm, WorkerProfileForm, JobRequestForm, RatingForm
from gemini_integration import MatchingEngine, GeminiSkillExtractor
from .models import JobApplication, ChatMessage, Notification
from .forms import JobApplicationForm, ChatMessageForm, RatingForm
from .chatbot import WorkNetChatbot
from django.http import JsonResponse
from django.utils import timezone
import json


def home(request):
    """Landing page for WorkNet"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    # Get some stats for the landing page
    total_workers = WorkerProfile.objects.filter(user_type='worker', is_approved=True).count()
    total_jobs = JobRequest.objects.filter(status='open').count()
    total_employers = WorkerProfile.objects.filter(user_type='employer').count()
    
    return render(request, 'home.html', {
        'total_workers': total_workers,
        'total_jobs': total_jobs,
        'total_employers': total_employers,
    })

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                messages.success(request, 'Account created successfully! Please log in.')
                return redirect('login')
            except Exception as e:
                messages.error(request, f'Error creating account: {str(e)}')
        else:
            # Form is invalid, show error messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'registration/register.html', {'form': form})

@login_required
def dashboard(request):
    try:
        profile = request.user.workerprofile
    except WorkerProfile.DoesNotExist:
        # If profile doesn't exist, create one
        profile = WorkerProfile.objects.create(
            user=request.user,
            user_type='worker',  # default type
            location='Unknown',
            reliability_score=3.0
        )
    
    if profile.user_type == 'admin':
        return redirect('admin_dashboard')
    elif profile.user_type == 'employer':
        return redirect('employer_dashboard')
    else:
        return redirect('worker_dashboard')

class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = WorkerProfile
    template_name = 'dashboard/admin_dashboard.html'
    context_object_name = 'workers'
    
    def test_func(self):
        return self.request.user.workerprofile.user_type == 'admin'
    
    def get_queryset(self):
        return WorkerProfile.objects.filter(user_type='worker')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_approvals'] = WorkerProfile.objects.filter(is_approved=False, user_type='worker')
        context['total_jobs'] = JobRequest.objects.count()
        context['active_jobs'] = JobRequest.objects.filter(status='open').count()
        return context

class EmployerDashboardView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = JobRequest
    template_name = 'dashboard/employer_dashboard.html'
    context_object_name = 'jobs'
    
    def test_func(self):
        return self.request.user.workerprofile.user_type == 'employer'
    
    def get_queryset(self):
        return JobRequest.objects.filter(employer=self.request.user.workerprofile)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employer = self.request.user.workerprofile
        context['active_jobs'] = JobRequest.objects.filter(employer=employer, status='open').count()
        context['completed_jobs'] = JobRequest.objects.filter(employer=employer, status='completed').count()
        return context

class WorkerDashboardView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = JobRequest
    template_name = 'dashboard/worker_dashboard.html'
    context_object_name = 'job_matches'
    
    def test_func(self):
        return self.request.user.workerprofile.user_type == 'worker'
    
    def get_queryset(self):
        worker = self.request.user.workerprofile
        return JobMatch.objects.filter(worker=worker).select_related('job', 'job__employer__user').order_by('-match_score')[:10]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        worker = self.request.user.workerprofile
        
        # Basic profile data
        context['profile'] = worker
        context['task_history'] = TaskHistory.objects.filter(worker=worker)[:5]
        context['average_rating'] = Rating.objects.filter(worker=worker).aggregate(Avg('score'))['score__avg'] or 0
        
        # Job application stats
        context['applied_jobs_count'] = JobApplication.objects.filter(worker=worker).count()
        context['active_applications_count'] = JobApplication.objects.filter(worker=worker, status='pending').count()
        context['recent_applications'] = JobApplication.objects.filter(worker=worker).select_related('job').order_by('-applied_at')[:3]
        
        return context

class WorkerProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = WorkerProfile
    form_class = WorkerProfileForm
    template_name = 'workers/profile_edit.html'
    success_url = reverse_lazy('worker_dashboard')
    
    def get_object(self):
        return self.request.user.workerprofile
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Extract skills using Gemini AI when skills description is updated
        if 'skills_description' in form.changed_data:
            gemini = GeminiSkillExtractor()
            skills_data = gemini.extract_skills_from_description(form.cleaned_data['skills_description'])
            
            # Clear existing skills
            self.object.extracted_skills.clear()
            
            # Add new extracted skills
            for skill_info in skills_data:
                skill, created = Skill.objects.get_or_create(
                    name=skill_info['skill_name'],
                    defaults={'category': skill_info['category']}
                )
                
                # Create WorkerSkill relationship
                from .models import WorkerSkill
                WorkerSkill.objects.create(
                    worker=self.object,
                    skill=skill,
                    proficiency_level=skill_info['proficiency_level'],
                    years_of_experience=skill_info['years_experience']
                )
            
            messages.success(self.request, 'Skills extracted and updated successfully!')
        
        return response
class WorkerListView(LoginRequiredMixin, ListView):
    model = WorkerProfile
    template_name = 'workers/workerprofile_list.html'
    context_object_name = 'workers'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = WorkerProfile.objects.filter(user_type='worker').select_related('user').prefetch_related('extracted_skills')
        
        # Search by name or skill
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(user__username__icontains=search_query) |
                Q(user__first_name__icontains=search_query) |
                Q(user__last_name__icontains=search_query) |
                Q(extracted_skills__name__icontains=search_query) |
                Q(bio__icontains=search_query)
            ).distinct()
        
        # Filter by category
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(extracted_skills__category=category).distinct()
        
        # Filter by location
        location = self.request.GET.get('location')
        if location:
            queryset = queryset.filter(location__icontains=location)
        
        # Filter by specific skill
        skill = self.request.GET.get('skill')
        if skill:
            queryset = queryset.filter(extracted_skills__name__icontains=skill).distinct()
        
        return queryset.order_by('-reliability_score', '-is_approved')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workers = self.get_queryset()
        
        context['approved_count'] = workers.filter(is_approved=True).count()
        context['high_rated_count'] = workers.filter(reliability_score__gte=4.0).count()
        
        # Count unique skill categories
        from django.db.models import Count
        categories_count = workers.annotate(
            skill_count=Count('extracted_skills__category', distinct=True)
        ).aggregate(total_categories=Count('extracted_skills__category', distinct=True))
        context['categories_count'] = categories_count['total_categories']
        
        return context
class JobRequestCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = JobRequest
    form_class = JobRequestForm
    template_name = 'jobs/job_create.html'
    success_url = reverse_lazy('employer_dashboard')
    
    def test_func(self):
        return self.request.user.workerprofile.user_type == 'employer'
    
    def form_valid(self, form):
        form.instance.employer = self.request.user.workerprofile
        response = super().form_valid(form)
        
        # Generate matches for the new job
        try:
            # Try Gemini matching first
            from gemini_integration import MatchingEngine
            matching_engine = MatchingEngine()
            matches = matching_engine.match_workers_to_job(form.instance)
            match_source = "AI"
        except Exception as e:
            # Fall back to simple matching
            from .matching import SimpleMatchingEngine
            matching_engine = SimpleMatchingEngine()
            matches = matching_engine.match_workers_to_job(form.instance)
            match_source = "simple"
            print(f"Gemini matching failed, using simple matching: {e}")
        
        # Save matches to database
        for match in matches:
            from .models import JobMatch
            JobMatch.objects.create(
                job=form.instance,
                worker=match['worker'],
                match_score=match['match_score'],
                skill_relevance=match['skill_relevance'],
                proximity_score=match['proximity_score'],
                reliability_score=match['reliability_score'],
                ai_notes=match['ai_notes']
            )
        
        if matches:
            messages.success(self.request, f'Job created and matched with {len(matches)} workers using {match_source} matching!')
        else:
            messages.success(self.request, 'Job created! No workers available for matching yet.')
        
        return response
class JobRequestDetailView(LoginRequiredMixin, DetailView):
    model = JobRequest
    template_name = 'jobs/job_detail.html'
    context_object_name = 'job'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['matches'] = JobMatch.objects.filter(job=self.object).order_by('-match_score')
        return context

class WorkerListView(LoginRequiredMixin, ListView):
    model = WorkerProfile
    template_name = 'workers/worker_list.html'
    context_object_name = 'workers'
    
    def get_queryset(self):
        return WorkerProfile.objects.filter(user_type='worker', is_approved=True)

@login_required
def approve_worker(request, pk):
    if not request.user.workerprofile.user_type == 'admin':
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')
    
    worker = get_object_or_404(WorkerProfile, pk=pk, user_type='worker')
    worker.is_approved = True
    worker.save()
    messages.success(request, f'Worker {worker.user.username} approved successfully!')
    return redirect('admin_dashboard')

@login_required
def generate_matches(request, job_id):
    job = get_object_or_404(JobRequest, id=job_id)
    
    if not request.user.workerprofile.user_type == 'employer' or job.employer != request.user.workerprofile:
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')
    
    matching_engine = MatchingEngine()
    matches = matching_engine.match_workers_to_job(job)
    
    # Update existing matches
    JobMatch.objects.filter(job=job).delete()
    for match in matches:
        JobMatch.objects.create(
            job=job,
            worker=match['worker'],
            match_score=match['match_score'],
            skill_relevance=match['skill_relevance'],
            proximity_score=match['proximity_score'],
            reliability_score=match['reliability_score'],
            ai_notes=match['ai_notes']
        )
    
    messages.success(request, 'Matches regenerated successfully!')
    return redirect('job_detail', pk=job_id)

# Add these imports at the top
from .models import JobApplication, ChatMessage, Notification
from .forms import JobApplicationForm, ChatMessageForm, RatingForm
from .chatbot import WorkNetChatbot
from django.http import JsonResponse
import json

# Add these new views after existing ones

class WorkerDirectoryView(LoginRequiredMixin, ListView):
    model = WorkerProfile
    template_name = 'workers/worker_directory.html'  # Make sure this matches
    context_object_name = 'workers'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = WorkerProfile.objects.filter(
            user_type='worker'
        ).select_related('user').prefetch_related('extracted_skills')
        
        # Search by name or skill
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(user__username__icontains=search_query) |
                Q(user__first_name__icontains=search_query) |
                Q(user__last_name__icontains=search_query) |
                Q(extracted_skills__name__icontains=search_query) |
                Q(bio__icontains=search_query)
            ).distinct()
        
        # Filter by category
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(extracted_skills__category=category).distinct()
        
        # Filter by location
        location = self.request.GET.get('location')
        if location:
            queryset = queryset.filter(location__icontains=location)
        
        return queryset.order_by('-reliability_score', '-is_approved')

@login_required
def apply_for_job(request, job_id):
    job = get_object_or_404(JobRequest, id=job_id)
    
    if request.user.workerprofile.user_type != 'worker':
        messages.error(request, 'Only workers can apply for jobs.')
        return redirect('job_detail', pk=job_id)
    
    if JobApplication.objects.filter(job=job, worker=request.user.workerprofile).exists():
        messages.warning(request, 'You have already applied for this job.')
        return redirect('job_detail', pk=job_id)
    
    if request.method == 'POST':
        form = JobApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.job = job
            application.worker = request.user.workerprofile
            application.save()
            
            # Create notification for employer
            Notification.objects.create(
                user=job.employer.user,
                notification_type='application',
                title='New Job Application',
                message=f"{request.user.username} applied for your job: {job.title}",
                related_object_id=job.id
            )
            
            messages.success(request, 'Application submitted successfully!')
            return redirect('job_detail', pk=job_id)
    else:
        form = JobApplicationForm()
    
    return render(request, 'jobs/job_apply.html', {
        'form': form,
        'job': job
    })

@login_required
def manage_applications(request, job_id):
    job = get_object_or_404(JobRequest, id=job_id)
    
    # Check if user owns the job
    if job.employer != request.user.workerprofile:
        messages.error(request, 'You can only manage applications for your own jobs.')
        return redirect('employer_dashboard')
    
    applications = JobApplication.objects.filter(job=job).select_related('worker__user')
    
    return render(request, 'jobs/manage_applications.html', {
        'job': job,
        'applications': applications
    })

@login_required
def update_application_status(request, application_id, status):
    application = get_object_or_404(JobApplication, id=application_id)
    
    # Check if user owns the job
    if application.job.employer != request.user.workerprofile:
        messages.error(request, 'Permission denied.')
        return redirect('employer_dashboard')
    
    valid_statuses = ['accepted', 'rejected', 'withdrawn']
    if status in valid_statuses:
        application.status = status
        application.save()
        
        # Create notification for worker
        Notification.objects.create(
            user=application.worker.user,
            notification_type=f'application_{status}',
            title=f'Application {status.capitalize()}',
            message=f"Your application for {application.job.title} has been {status}",
            related_object_id=application.job.id
        )
        
        messages.success(request, f'Application {status} successfully.')
    
    return redirect('manage_applications', job_id=application.job.id)

@login_required
def rate_worker(request, job_id):
    job = get_object_or_404(JobRequest, id=job_id)
    
    # Check if user owns the job and it's completed
    if job.employer != request.user.workerprofile or job.status != 'completed':
        messages.error(request, 'You can only rate workers for your completed jobs.')
        return redirect('employer_dashboard')
    
    # Check if rating already exists
    if Rating.objects.filter(job=job, employer=request.user.workerprofile).exists():
        messages.warning(request, 'You have already rated this worker for this job.')
        return redirect('employer_dashboard')
    
    if request.method == 'POST':
        form = RatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.job = job
            rating.employer = request.user.workerprofile
            rating.worker = job.task_history.first().worker  # Get worker from task history
            rating.save()
            
            # Update worker's reliability score
            worker_profile = rating.worker
            avg_rating = worker_profile.ratings_received.aggregate(models.Avg('score'))['score__avg']
            worker_profile.reliability_score = avg_rating or worker_profile.reliability_score
            worker_profile.save()
            
            messages.success(request, 'Rating submitted successfully!')
            return redirect('employer_dashboard')
    else:
        form = RatingForm()
    
    return render(request, 'ratings/rate_worker.html', {
        'form': form,
        'job': job
    })

@login_required
def chatbot(request):
    if request.method == 'POST':
        form = ChatMessageForm(request.POST)
        if form.is_valid():
            message = form.cleaned_data['message']
            
            # Save user message
            ChatMessage.objects.create(
                user=request.user,
                message_type='user',
                content=message
            )
            
            # Get bot response
            try:
                chatbot = WorkNetChatbot()
                bot_response = chatbot.get_response(message, request.user.workerprofile)
            except Exception as e:
                bot_response = "I'm currently unavailable. Please try again later."
            
            # Save bot response
            ChatMessage.objects.create(
                user=request.user,
                message_type='bot',
                content=bot_response
            )
            
            return JsonResponse({'response': bot_response})
    
    # Get chat history
    chat_history = ChatMessage.objects.filter(user=request.user).order_by('timestamp')[:20]
    
    return render(request, 'chatbot/chatbot.html', {
        'chat_history': chat_history,
        'form': ChatMessageForm()
    })

@login_required
def get_chat_history(request):
    """API endpoint to get chat history"""
    chat_history = ChatMessage.objects.filter(user=request.user).order_by('timestamp')[:50]
    history_data = [
        {
            'type': msg.message_type,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%H:%M')
        }
        for msg in chat_history
    ]
    return JsonResponse({'history': history_data})

@login_required
def skill_analysis(request):
    """AI-powered skill analysis for workers"""
    if request.user.workerprofile.user_type != 'worker':
        messages.error(request, 'This feature is only available for workers.')
        return redirect('dashboard')
    
    worker_profile = request.user.workerprofile
    skills = worker_profile.extracted_skills.all()
    
    analysis = None
    if request.method == 'POST':
        desired_role = request.POST.get('desired_role')
        if desired_role:
            try:
                chatbot = WorkNetChatbot()
                current_skills = [skill.name for skill in skills]
                analysis = chatbot.analyze_skills_gap(current_skills, desired_role)
            except Exception as e:
                messages.error(request, 'Unable to perform skill analysis at the moment.')
                print(f"Skill analysis error: {e}")  # For debugging
    
    # Get worker skills with proficiency levels
    worker_skills_data = []
    for skill in skills:
        try:
            worker_skill = worker_profile.workerskill_set.get(skill=skill)
            worker_skills_data.append({
                'skill': skill,
                'proficiency_level': worker_skill.proficiency_level,
                'years_of_experience': worker_skill.years_of_experience
            })
        except WorkerSkill.DoesNotExist:
            # If no WorkerSkill exists, create a default one
            worker_skills_data.append({
                'skill': skill,
                'proficiency_level': 1,
                'years_of_experience': 0
            })
    
    return render(request, 'workers/skill_analysis.html', {
        'worker_profile': worker_profile,
        'skills': skills,
        'worker_skills_data': worker_skills_data,
        'analysis': analysis
    })

@login_required
def notifications(request):
    """View and manage notifications"""
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    
    return render(request, 'notifications/notifications.html', {
        'notifications': notifications,
        'unread_count': unread_count
    })

@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    
    return JsonResponse({'success': True})

@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('notifications')

class JobSearchView(LoginRequiredMixin, ListView):
    model = JobRequest
    template_name = 'jobs/job_search.html'
    context_object_name = 'jobs'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = JobRequest.objects.filter(status='open').select_related('employer__user').prefetch_related('required_skills')
        
        # Search by title or description
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(required_skills__name__icontains=search_query)
            ).distinct()
        
        # Filter by location
        location = self.request.GET.get('location')
        if location:
            queryset = queryset.filter(location__icontains=location)
        
        # Filter by budget range
        min_budget = self.request.GET.get('min_budget')
        max_budget = self.request.GET.get('max_budget')
        if min_budget:
            queryset = queryset.filter(budget__gte=min_budget)
        if max_budget:
            queryset = queryset.filter(budget__lte=max_budget)
        
        # Filter by skill
        skill = self.request.GET.get('skill')
        if skill:
            queryset = queryset.filter(required_skills__name__icontains=skill).distinct()
        
        # Sort options
        sort = self.request.GET.get('sort', 'newest')
        if sort == 'budget_high':
            queryset = queryset.order_by('-budget')
        elif sort == 'budget_low':
            queryset = queryset.order_by('budget')
        elif sort == 'closest':
            # For now, sort by location match - in production you'd use geolocation
            location_match = self.request.GET.get('location')
            if location_match:
                queryset = queryset.filter(location__icontains=location_match)
            queryset = queryset.order_by('created_at')
        else:  # newest first
            queryset = queryset.order_by('-created_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['skills'] = Skill.objects.all()
        context['total_jobs'] = JobRequest.objects.filter(status='open').count()
        
        # Add applied job IDs for current user
        if self.request.user.is_authenticated and hasattr(self.request.user, 'workerprofile'):
            applied_jobs = JobApplication.objects.filter(
                worker=self.request.user.workerprofile
            ).values_list('job_id', flat=True)
            context['applied_job_ids'] = list(applied_jobs)
        
        return context

class RecommendedJobsView(LoginRequiredMixin, ListView):
    model = JobMatch
    template_name = 'jobs/recommended_jobs.html'
    context_object_name = 'job_matches'
    paginate_by = 10
    
    def get_queryset(self):
        if not hasattr(self.request.user, 'workerprofile'):
            return JobMatch.objects.none()
        
        worker = self.request.user.workerprofile
        return JobMatch.objects.filter(
            worker=worker,
            job__status='open'
        ).select_related('job', 'job__employer__user').order_by('-match_score')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self.request.user, 'workerprofile'):
            context['worker_profile'] = self.request.user.workerprofile
            
            # Add applied job IDs for current user
            applied_jobs = JobApplication.objects.filter(
                worker=self.request.user.workerprofile
            ).values_list('job_id', flat=True)
            context['applied_job_ids'] = list(applied_jobs)
        
        return context
@login_required
def save_job(request, job_id):
    """Save a job for later viewing"""
    job = get_object_or_404(JobRequest, id=job_id)
    
    # For now, we'll just track in session. In production, you'd want a SavedJob model
    saved_jobs = request.session.get('saved_jobs', [])
    if job_id not in saved_jobs:
        saved_jobs.append(job_id)
        request.session['saved_jobs'] = saved_jobs
        messages.success(request, 'Job saved successfully!')
    else:
        messages.info(request, 'Job already saved.')
    
    return redirect('job_detail', pk=job_id)

@login_required
def saved_jobs(request):
    """View saved jobs"""
    saved_job_ids = request.session.get('saved_jobs', [])
    saved_jobs = JobRequest.objects.filter(id__in=saved_job_ids, status='open')
    
    return render(request, 'jobs/saved_jobs.html', {
        'saved_jobs': saved_jobs
    })
@login_required
def manage_applications(request, job_id):
    job = get_object_or_404(JobRequest, id=job_id)
    
    # Check if user owns the job
    if job.employer != request.user.workerprofile:
        messages.error(request, 'You can only manage applications for your own jobs.')
        return redirect('employer_dashboard')
    
    applications = JobApplication.objects.filter(job=job).select_related('worker__user')
    
    return render(request, 'jobs/manage_applications.html', {
        'job': job,
        'applications': applications
    })
@login_required
def update_application_status(request, application_id, status):
    application = get_object_or_404(JobApplication, id=application_id)
    
    # Check if user owns the job
    if application.job.employer != request.user.workerprofile:
        messages.error(request, 'Permission denied.')
        return redirect('employer_dashboard')
    
    valid_statuses = ['accepted', 'rejected', 'withdrawn']
    if status in valid_statuses:
        application.status = status
        application.save()
        
        # When application is accepted, update the job directly
        if status == 'accepted':
            application.job.status = 'in_progress'
            application.job.assigned_worker = application.worker
            application.job.save()
            
            # Create notification for worker
            Notification.objects.create(
                user=application.worker.user,
                notification_type='job_assigned',
                title='Job Assigned!',
                message=f"Your application for '{application.job.title}' has been accepted! You can now start working.",
                related_object_id=application.job.id
            )
        
        # Create notification for application status change
        if status in ['accepted', 'rejected']:
            Notification.create_application_notification(
                user=application.worker.user,
                application=application,
                notification_type=f'application_{status}'
            )
        
        messages.success(request, f'Application {status} successfully.')
    
    return redirect('manage_applications', job_id=application.job.id)
def send_application_status_email(application, status):
    """Send email notification for application status change"""
    # This is a placeholder - you can implement email functionality later
    # For now, we'll just print to console
    print(f"Email: Application for {application.job.title} has been {status}")

@login_required
def my_jobs(request):
    """View for workers to see their assigned jobs"""
    if request.user.workerprofile.user_type != 'worker':
        messages.error(request, 'This page is only available for workers.')
        return redirect('dashboard')
    
    worker = request.user.workerprofile
    
    # Get jobs where this worker's application was accepted
    accepted_applications = JobApplication.objects.filter(
        worker=worker, 
        status='accepted'
    ).select_related('job', 'job__employer__user')
    
    # Ensure jobs are properly set up
    for application in accepted_applications:
        job = application.job
        # Auto-fix common issues
        if job.status == 'open':
            job.status = 'in_progress'
            job.save()
        if job.assigned_worker is None:
            job.assigned_worker = worker
            job.save()
    
    # Get the actual job objects
    jobs = [app.job for app in accepted_applications]
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        if status_filter == 'in_progress':
            jobs = [job for job in jobs if job.status == 'in_progress']
        elif status_filter == 'completed':
            jobs = [job for job in jobs if job.status == 'completed']
    
    # Debug info
    print(f"Found {len(jobs)} jobs for worker {worker.user.username}")
    for job in jobs:
        print(f"Job: {job.title}, Status: {job.status}, Can complete: {job.can_be_completed_by_worker()}")
    
    return render(request, 'jobs/my_jobs.html', {
        'jobs': jobs,
        'status_filter': status_filter
    })
@login_required
def mark_job_completed(request, job_id):
    """Worker marks a job as completed"""
    job = get_object_or_404(JobRequest, id=job_id)
    
    # Check if user is the assigned worker for this job
    assigned_worker = job.get_assigned_worker()
    if assigned_worker != request.user.workerprofile:
        messages.error(request, 'You can only complete jobs assigned to you.')
        return redirect('my_jobs')
    
    if not job.can_be_completed_by_worker():
        messages.error(request, 'This job cannot be marked as completed at this time.')
        return redirect('my_jobs')
    
    if request.method == 'POST':
        # Get form data
        feedback = request.POST.get('feedback', '')
        signature_text = request.POST.get('signature', f"Completed by {request.user.username}")
        
        # Update job - mark as completed by worker
        job.worker_completion_date = timezone.now()
        job.worker_signature = signature_text
        job.save()
        
        # Create notification for employer
        Notification.objects.create(
            user=job.employer.user,
            notification_type='job_completed',
            title='Job Completed by Worker',
            message=f"{request.user.username} has marked the job '{job.title}' as completed and is waiting for your approval",
            related_object_id=job.id
        )
        
        messages.success(request, 'Job marked as completed! Waiting for employer approval.')
        return redirect('my_jobs')
    
    return render(request, 'jobs/mark_job_completed.html', {
        'job': job
    })

@login_required
def approve_job(request, job_id):
    """Employer approves a completed job"""
    from django.db import models  # Add this import
    from django.utils import timezone
    
    job = get_object_or_404(JobRequest, id=job_id)
    
    # Check if user owns the job
    if job.employer != request.user.workerprofile:
        messages.error(request, 'You can only approve your own jobs.')
        return redirect('employer_approvals')
    
    if not job.can_be_approved_by_employer():
        messages.error(request, 'This job cannot be approved at this time.')
        return redirect('employer_approvals')
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        feedback = request.POST.get('feedback', '')
        signature_text = request.POST.get('signature', f"Approved by {request.user.username}")
        
        # Update job - mark as approved by employer
        job.employer_approval_date = timezone.now()
        job.employer_signature = signature_text
        job.completed_successfully = True
        job.status = 'completed'
        job.save()
        
        # Create rating if provided
        if rating:
            Rating.objects.create(
                worker=job.get_assigned_worker(),
                job=job,
                employer=request.user.workerprofile,
                score=rating,
                comment=feedback
            )
            
            # Update worker's reliability score
            worker_profile = job.get_assigned_worker()
            avg_rating = worker_profile.ratings_received.aggregate(models.Avg('score'))['score__avg']
            worker_profile.reliability_score = avg_rating or worker_profile.reliability_score
            worker_profile.save()
        
        # Create notification for worker
        Notification.objects.create(
            user=job.get_assigned_worker().user,
            notification_type='job_approved',
            title='Job Approved!',
            message=f"Your work on '{job.title}' has been approved by the employer",
            related_object_id=job.id
        )
        
        messages.success(request, 'Job approved successfully! Payment can now be processed.')
        return redirect('employer_approvals')
    
    return render(request, 'jobs/approve_job.html', {
        'job': job
    })
@login_required
def employer_approvals(request):
    """View for employers to see jobs waiting for approval"""
    if request.user.workerprofile.user_type != 'employer':
        messages.error(request, 'This page is only available for employers.')
        return redirect('dashboard')
    
    employer = request.user.workerprofile
    
    # Get jobs that are completed by workers but not yet approved
    jobs_to_approve = JobRequest.objects.filter(
        employer=employer,
        status='in_progress',
        worker_completion_date__isnull=False,
        employer_approval_date__isnull=True
    )
    
    # Get all jobs for this employer
    all_jobs = JobRequest.objects.filter(employer=employer).order_by('-created_at')
    
    # Additional stats
    completed_jobs_count = JobRequest.objects.filter(
        employer=employer, 
        status='completed'
    ).count()
    
    in_progress_jobs_count = JobRequest.objects.filter(
        employer=employer,
        status='in_progress'
    ).count()
    
    return render(request, 'jobs/employer_approvals.html', {
        'jobs_to_approve': jobs_to_approve,
        'all_jobs': all_jobs,
        'completed_jobs_count': completed_jobs_count,
        'in_progress_jobs_count': in_progress_jobs_count
    })

@login_required
def my_applications(request):
    """View for workers to see all jobs they've applied to"""
    if request.user.workerprofile.user_type != 'worker':
        messages.error(request, 'This page is only available for workers.')
        return redirect('dashboard')
    
    worker = request.user.workerprofile
    applications = JobApplication.objects.filter(worker=worker).select_related('job', 'job__employer__user').order_by('-applied_at')
    
    return render(request, 'jobs/my_applications.html', {
        'applications': applications
    })
@login_required
def my_assigned_jobs(request):
    """View for workers to see jobs where their application was accepted"""
    if request.user.workerprofile.user_type != 'worker':
        messages.error(request, 'This page is only available for workers.')
        return redirect('dashboard')
    
    worker = request.user.workerprofile
    accepted_applications = JobApplication.objects.filter(
        worker=worker, 
        status='accepted'
    ).select_related('job', 'job__employer__user').order_by('-applied_at')
    
    # Get corresponding tasks for these accepted jobs
    assigned_jobs = []
    for application in accepted_applications:
        task = TaskHistory.objects.filter(job=application.job, worker=worker).first()
        assigned_jobs.append({
            'application': application,
            'job': application.job,
            'task': task  # This will be None if no task created yet
        })
    
    return render(request, 'jobs/my_assigned_jobs.html', {
        'assigned_jobs': assigned_jobs
    })