from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import (
    AdminDashboardView, EmployerDashboardView, WorkerDashboardView,
    WorkerProfileUpdateView, JobRequestCreateView, JobRequestDetailView,
    WorkerListView, WorkerDirectoryView,JobSearchView,RecommendedJobsView
)

urlpatterns = [
    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    
    # Home page
    path('', views.home, name='home'),  # Changed to custom home view
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/admin/', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('dashboard/employer/', EmployerDashboardView.as_view(), name='employer_dashboard'),
    path('dashboard/worker/', WorkerDashboardView.as_view(), name='worker_dashboard'),
    
    # Worker Profiles
    path('profile/edit/', WorkerProfileUpdateView.as_view(), name='profile_edit'),
    path('workers/', WorkerListView.as_view(), name='worker_list'),
    path('workers/directory/', WorkerDirectoryView.as_view(), name='worker_directory'),
    path('workers/approve/<int:pk>/', views.approve_worker, name='approve_worker'),
    path('workers/skill-analysis/', views.skill_analysis, name='skill_analysis'),
    path('profile/manual-skills/', views.manual_skill_entry, name='manual_skill_entry'),
    path('api/add-skill/', views.add_skill_manual_ajax, name='add_skill_manual'),
    
    # Jobs
    path('jobs/create/', JobRequestCreateView.as_view(), name='job_create'),
    path('jobs/<int:pk>/', JobRequestDetailView.as_view(), name='job_detail'),
    path('jobs/<int:job_id>/apply/', views.apply_for_job, name='apply_for_job'),
    path('jobs/<int:job_id>/applications/', views.manage_applications, name='manage_applications'),
    path('jobs/<int:job_id>/matches/', views.generate_matches, name='generate_matches'),
    # Job Search URLs
    path('jobs/search/', JobSearchView.as_view(), name='job_search'),
    path('jobs/recommended/', RecommendedJobsView.as_view(), name='recommended_jobs'),
    path('jobs/save/<int:job_id>/', views.save_job, name='save_job'),
    path('jobs/saved/', views.saved_jobs, name='saved_jobs'),
    path('applications/<int:application_id>/<str:status>/', views.update_application_status, name='update_application_status'),
    
    # Ratings
    path('jobs/<int:job_id>/rate/', views.rate_worker, name='rate_worker'),
    
    # Chatbot
    path('chatbot/', views.chatbot, name='chatbot'),
    path('chatbot/history/', views.get_chat_history, name='get_chat_history'),
    
    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),

    # Job Management URLs
    path('jobs/my-applications/', views.my_applications, name='my_applications'),
    path('jobs/my-assigned-jobs/', views.my_assigned_jobs, name='my_assigned_jobs'),
    path('jobs/my-jobs/', views.my_jobs, name='my_jobs'),
    path('jobs/<int:job_id>/complete/', views.mark_job_completed, name='mark_job_completed'),

    # Employer Approvals
    path('employer/approvals/', views.employer_approvals, name='employer_approvals'),
    path('jobs/<int:job_id>/approve/', views.approve_job, name='approve_job'),
]