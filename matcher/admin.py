from django.contrib import admin
from .models import WorkerProfile, Skill, JobRequest, Rating, TaskHistory, JobMatch

@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'user_type', 'location', 'is_approved', 'reliability_score']
    list_filter = ['user_type', 'is_approved']
    search_fields = ['user__username', 'location']
    actions = ['approve_workers']
    
    def approve_workers(self, request, queryset):
        queryset.update(is_approved=True)
    approve_workers.short_description = "Approve selected workers"

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'created_at']
    list_filter = ['category']
    search_fields = ['name']

@admin.register(JobRequest)
class JobRequestAdmin(admin.ModelAdmin):
    list_display = ['title', 'employer', 'location', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'description']

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['worker', 'employer', 'score', 'created_at']
    list_filter = ['score']

@admin.register(TaskHistory)
class TaskHistoryAdmin(admin.ModelAdmin):
    list_display = ['worker', 'job', 'start_date', 'completed_successfully']
    list_filter = ['completed_successfully', 'start_date']

@admin.register(JobMatch)
class JobMatchAdmin(admin.ModelAdmin):
    list_display = ['job', 'worker', 'match_score', 'created_at']
    list_filter = ['created_at']
    readonly_fields = ['ai_notes']