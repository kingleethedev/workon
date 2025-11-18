from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from matcher.models import WorkerProfile, Skill

class Command(BaseCommand):
    help = 'Create initial sample data for the application'
    
    def handle(self, *args, **options):
        self.stdout.write('Creating sample data...')
        
        # Create sample skills
        sample_skills = [
            {'name': 'Construction', 'category': 'Construction'},
            {'name': 'Plumbing', 'category': 'Construction'},
            {'name': 'Electrical', 'category': 'Construction'},
            {'name': 'Python', 'category': 'IT & Technology'},
            {'name': 'Django', 'category': 'IT & Technology'},
            {'name': 'JavaScript', 'category': 'IT & Technology'},
            {'name': 'React', 'category': 'IT & Technology'},
            {'name': 'Cleaning', 'category': 'Cleaning & Maintenance'},
            {'name': 'Driving', 'category': 'Transportation'},
            {'name': 'Graphic Design', 'category': 'Creative & Design'},
        ]
        
        for skill_data in sample_skills:
            skill, created = Skill.objects.get_or_create(
                name=skill_data['name'],
                defaults={'category': skill_data['category']}
            )
            if created:
                self.stdout.write(f'Created skill: {skill.name}')
        
        self.stdout.write(
            self.style.SUCCESS('Sample data created successfully!')
        )