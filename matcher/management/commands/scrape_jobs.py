from django.core.management.base import BaseCommand
from django.utils import timezone
from matcher.models import JobRequest, WorkerProfile, Skill
from django.contrib.auth.models import User
import requests
from bs4 import BeautifulSoup
import random
from datetime import timedelta

class Command(BaseCommand):
    help = 'Scrape sample job opportunities from public sources'
    
    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=10, help='Number of jobs to scrape')
    
    def handle(self, *args, **options):
        count = options['count']
        self.stdout.write(f'Scraping {count} sample jobs...')
        
        # Sample job data (in production, this would scrape real sites)
        sample_jobs = [
            {
                'title': 'Construction Laborer Needed',
                'description': 'Looking for experienced construction worker for residential building project. Must have experience with framing, drywall, and basic tools.',
                'skills': ['Construction', 'Framing', 'Drywall', 'Power Tools'],
                'location': 'Downtown Area'
            },
            {
                'title': 'Web Developer - Freelance',
                'description': 'Need a web developer to create a responsive website using Django and React. Experience with REST APIs required.',
                'skills': ['Django', 'React', 'JavaScript', 'Python', 'HTML/CSS'],
                'location': 'Remote'
            },
            {
                'title': 'Delivery Driver',
                'description': 'Immediate opening for reliable delivery driver with own vehicle. Food delivery experience preferred.',
                'skills': ['Driving', 'Customer Service', 'Navigation', 'Time Management'],
                'location': 'City Center'
            },
            {
                'title': 'House Cleaning Professional',
                'description': 'Experienced cleaner needed for residential cleaning. Attention to detail and reliability required.',
                'skills': ['Cleaning', 'Organization', 'Time Management'],
                'location': 'Suburban Area'
            },
            {
                'title': 'Graphic Designer',
                'description': 'Freelance graphic designer needed for branding project. Proficiency in Adobe Creative Suite required.',
                'skills': ['Graphic Design', 'Adobe Photoshop', 'Illustrator', 'Branding'],
                'location': 'Remote'
            }
        ]
        
        # Get or create an employer profile for sample jobs
        try:
            # Try to get existing sample employer user
            employer_user = User.objects.get(username='sample_employer')
            employer_profile = WorkerProfile.objects.get(user=employer_user)
        except User.DoesNotExist:
            # Create new sample employer user and profile
            employer_user = User.objects.create_user(
                username='sample_employer',
                email='employer@sample.com',
                password='password123'
            )
            employer_profile = WorkerProfile.objects.create(
                user=employer_user,
                user_type='employer',
                location='Sample Location',
                is_approved=True,
                reliability_score=5.0
            )
            self.stdout.write('Created sample employer user')
        except WorkerProfile.DoesNotExist:
            # User exists but profile doesn't - create profile
            employer_profile = WorkerProfile.objects.create(
                user=employer_user,
                user_type='employer',
                location='Sample Location',
                is_approved=True,
                reliability_score=5.0
            )
            self.stdout.write('Created sample employer profile')
        
        skills_created = 0
        jobs_created = 0
        
        for i in range(count):
            job_data = random.choice(sample_jobs)
            
            # Create job request
            job = JobRequest.objects.create(
                employer=employer_profile,
                title=f"{job_data['title']} #{i+1}",
                description=job_data['description'],
                location=job_data['location'],
                budget=random.randint(50, 500),
                status='open'
            )
            
            # Add required skills
            for skill_name in job_data['skills']:
                skill, created = Skill.objects.get_or_create(
                    name=skill_name,
                    defaults={'category': self.categorize_skill(skill_name)}
                )
                if created:
                    skills_created += 1
                job.required_skills.add(skill)
            
            jobs_created += 1
            self.stdout.write(f'Created job: {job.title}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {jobs_created} jobs and {skills_created} new skills!'
            )
        )
    
    def categorize_skill(self, skill_name):
        """Categorize skills based on keywords"""
        skill_lower = skill_name.lower()
        
        if any(word in skill_lower for word in ['construction', 'carpentry', 'plumbing', 'electrical']):
            return 'Construction'
        elif any(word in skill_lower for word in ['programming', 'developer', 'coding', 'software', 'python', 'javascript']):
            return 'IT & Technology'
        elif any(word in skill_lower for word in ['cleaning', 'housekeeping', 'maintenance']):
            return 'Cleaning & Maintenance'
        elif any(word in skill_lower for word in ['driving', 'delivery', 'transport']):
            return 'Transportation'
        elif any(word in skill_lower for word in ['design', 'graphic', 'creative', 'photoshop']):
            return 'Creative & Design'
        else:
            return 'General'