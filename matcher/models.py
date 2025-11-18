from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.category})"

class WorkerProfile(models.Model):
    USER_TYPES = (
        ('worker', 'Worker'),
        ('employer', 'Employer'),
        ('admin', 'Admin'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='worker')
    bio = models.TextField(blank=True, default='')
    location = models.CharField(max_length=255, default='Unknown')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    skills_description = models.TextField(blank=True, default='')
    extracted_skills = models.ManyToManyField(Skill, through='WorkerSkill', blank=True)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    reliability_score = models.FloatField(default=3.0, validators=[MinValueValidator(0.0), MaxValueValidator(5.0)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def average_rating(self):
        ratings = self.ratings_received.all()
        if ratings:
            return ratings.aggregate(models.Avg('score'))['score__avg']
        return 0
    
    def completed_jobs_count(self):
        return self.task_history.filter(completed_successfully=True).count()
  
    
    def get_worker_skills_with_details(self):
        """Get skills with proficiency levels and experience"""
        worker_skills = []
        for worker_skill in self.workerskill_set.all():
            worker_skills.append({
                'skill': worker_skill.skill,
                'proficiency_level': worker_skill.proficiency_level,
                'years_of_experience': worker_skill.years_of_experience
            })
        return worker_skills
    
    def get_skill_proficiency(self, skill):
        """Get proficiency level for a specific skill"""
        try:
            worker_skill = self.workerskill_set.get(skill=skill)
            return worker_skill.proficiency_level
        except WorkerSkill.DoesNotExist:
            return 1  # Default proficiency
    
    def __str__(self):
        return f"{self.user.username} - {self.user_type}"

class WorkerSkill(models.Model):
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    proficiency_level = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    years_of_experience = models.FloatField(default=0.0)
    verified = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['worker', 'skill']

class JobRequest(models.Model):
    JOB_STATUS = (
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    employer = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, limit_choices_to={'user_type': 'employer'})
    title = models.CharField(max_length=200)
    description = models.TextField()
    required_skills = models.ManyToManyField(Skill)
    location = models.CharField(max_length=255)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=JOB_STATUS, default='open')
    
    # Add these fields for direct job completion tracking
    assigned_worker = models.ForeignKey(WorkerProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_jobs')
    worker_completion_date = models.DateTimeField(null=True, blank=True)
    employer_approval_date = models.DateTimeField(null=True, blank=True)
    worker_signature = models.TextField(blank=True)
    employer_signature = models.TextField(blank=True)
    completed_successfully = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def is_applied_by(self, worker):
        return self.jobapplication_set.filter(worker=worker).exists()
    
    def get_assigned_worker(self):
        """Get the worker who was accepted for this job"""
        try:
            accepted_application = self.jobapplication_set.get(status='accepted')
            return accepted_application.worker
        except JobApplication.DoesNotExist:
            return None
    
    def can_be_completed_by_worker(self):
        """Check if worker can mark this job as completed"""
        worker = self.get_assigned_worker()
        return (self.status == 'in_progress' and 
                worker is not None and 
                self.worker_completion_date is None)
    
    def can_be_approved_by_employer(self):
        """Check if employer can approve this job"""
        return (self.status == 'in_progress' and 
                self.worker_completion_date is not None and 
                self.employer_approval_date is None)
    
    def mark_worker_completed(self, signature_text=""):
        """Mark job as completed by worker"""
        from django.utils import timezone
        self.worker_completion_date = timezone.now()
        self.worker_signature = signature_text or f"Completed by {self.get_assigned_worker().user.username} on {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        self.save()
        
        # Create notification for employer
        Notification.objects.create(
            user=self.employer.user,
            notification_type='job_completed',
            title='Job Completed',
            message=f"{self.get_assigned_worker().user.username} has marked the job '{self.title}' as completed",
            related_object_id=self.id
        )
    
    def mark_employer_approved(self, signature_text=""):
        """Mark job as approved by employer"""
        from django.utils import timezone
        self.employer_approval_date = timezone.now()
        self.employer_signature = signature_text or f"Approved by {self.employer.user.username} on {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        self.completed_successfully = True
        self.status = 'completed'
        self.save()
        
        # Create notification for worker
        Notification.objects.create(
            user=self.get_assigned_worker().user,
            notification_type='job_approved',
            title='Job Approved',
            message=f"Your work on '{self.title}' has been approved by the employer",
            related_object_id=self.id
        )
    
    def __str__(self):
        return f"{self.title} - {self.employer.user.username}"

class JobApplication(models.Model):
    APPLICATION_STATUS = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    )
    
    job = models.ForeignKey(JobRequest, on_delete=models.CASCADE)
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS, default='pending')
    cover_letter = models.TextField(blank=True)
    proposed_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['job', 'worker']

class Rating(models.Model):
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name='ratings_received')
    job = models.ForeignKey(JobRequest, on_delete=models.CASCADE)
    employer = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name='ratings_given')
    score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['worker', 'job', 'employer']

class TaskHistory(models.Model):
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name='task_history')
    job = models.ForeignKey(JobRequest, on_delete=models.CASCADE)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    completed_successfully = models.BooleanField(default=False)
    employer_feedback = models.TextField(blank=True)
    worker_feedback = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.worker.user.username} - {self.job.title}"

class JobMatch(models.Model):
    job = models.ForeignKey(JobRequest, on_delete=models.CASCADE)
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE)
    match_score = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    skill_relevance = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    proximity_score = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    reliability_score = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    ai_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['job', 'worker']

class ChatMessage(models.Model):
    MESSAGE_TYPES = (
        ('user', 'User Message'),
        ('bot', 'Bot Response'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('job_match', 'New Job Match'),
        ('application', 'Job Application'),
        ('application_accepted', 'Application Accepted'),
        ('application_rejected', 'Application Rejected'),
        ('rating', 'New Rating'),
        ('message', 'New Message'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    related_object_id = models.IntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']

    @classmethod
    def create_application_notification(cls, user, application, notification_type):
        """Create notification for job application status changes"""
        notification_map = {
            'application': {
                'title': 'New Job Application',
                'message': f"{application.worker.user.username} applied for your job: {application.job.title}"
            },
            'application_accepted': {
                'title': 'Application Accepted!',
                'message': f"Your application for {application.job.title} has been accepted!"
            },
            'application_rejected': {
                'title': 'Application Rejected',
                'message': f"Your application for {application.job.title} has been rejected"
            }
        }
        
        if notification_type in notification_map:
            return cls.objects.create(
                user=user,
                notification_type=notification_type,
                title=notification_map[notification_type]['title'],
                message=notification_map[notification_type]['message'],
                related_object_id=application.job.id
            )
        
class TaskHistory(models.Model):
    TASK_STATUS = (
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('disputed', 'Disputed'),
    )
    
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name='task_history')
    job = models.ForeignKey(JobRequest, on_delete=models.CASCADE)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    completed_successfully = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=TASK_STATUS, default='assigned')
    
    # Completion confirmations
    worker_completion_date = models.DateTimeField(null=True, blank=True)
    employer_approval_date = models.DateTimeField(null=True, blank=True)
    
    # Digital signatures (simple text confirmation for now)
    worker_signature = models.TextField(blank=True)  # Could be "confirmed by [username] on [date]"
    employer_signature = models.TextField(blank=True)
    
    # Feedback and ratings
    employer_feedback = models.TextField(blank=True)
    worker_feedback = models.TextField(blank=True)
    
    # Dispute resolution
    dispute_reason = models.TextField(blank=True)
    dispute_resolved = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.worker.user.username} - {self.job.title}"
    
    def mark_worker_completed(self, signature_text=""):
        """Mark task as completed by worker"""
        from django.utils import timezone
        self.worker_completion_date = timezone.now()
        self.worker_signature = signature_text or f"Completed by {self.worker.user.username} on {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        self.status = 'completed'
        self.save()
        
        # Create notification for employer
        Notification.objects.create(
            user=self.job.employer.user,
            notification_type='task_completed',
            title='Task Completed',
            message=f"{self.worker.user.username} has marked the task '{self.job.title}' as completed",
            related_object_id=self.job.id
        )
    
    def mark_employer_approved(self, signature_text=""):
        """Mark task as approved by employer"""
        from django.utils import timezone
        self.employer_approval_date = timezone.now()
        self.employer_signature = signature_text or f"Approved by {self.job.employer.user.username} on {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        self.completed_successfully = True
        self.end_date = timezone.now()
        self.save()
        
        # Create notification for worker
        Notification.objects.create(
            user=self.worker.user,
            notification_type='task_approved',
            title='Task Approved',
            message=f"Your work on '{self.job.title}' has been approved by the employer",
            related_object_id=self.job.id
        )
        
        # Update job status
        self.job.status = 'completed'
        self.job.save()
    
    def can_be_completed_by_worker(self):
        """Check if worker can mark this task as completed"""
        return self.status in ['assigned', 'in_progress']
    
    def can_be_approved_by_employer(self):
        """Check if employer can approve this task"""
        return self.status == 'completed' and self.worker_completion_date is not None
    
    def get_completion_status(self):
        """Get human-readable completion status"""
        if self.completed_successfully:
            return "Fully Completed & Approved"
        elif self.employer_approval_date:
            return "Awaiting Payment"  # You can add payment integration later
        elif self.worker_completion_date:
            return "Awaiting Employer Approval"
        else:
            return self.get_status_display()