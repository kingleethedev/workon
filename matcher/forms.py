# matcher/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import WorkerProfile, JobRequest, Rating, JobApplication, Skill
import re

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    user_type = forms.ChoiceField(choices=WorkerProfile.USER_TYPES)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'user_type')
    
    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken. Please choose a different one.")
        return username
    
    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered. Please use a different email.")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            WorkerProfile.objects.create(
                user=user,
                user_type=self.cleaned_data['user_type'],
                location='Unknown',
                reliability_score=3.0
            )
        return user

class WorkerProfileForm(forms.ModelForm):
    class Meta:
        model = WorkerProfile
        fields = ['bio', 'location', 'skills_description', 'hourly_rate']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'skills_description': forms.Textarea(attrs={'rows': 6, 'class': 'form-control', 'placeholder': 'Describe your skills, experience, and expertise in detail...'}),
            'hourly_rate': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class JobRequestForm(forms.ModelForm):
    class Meta:
        model = JobRequest
        fields = ['title', 'description', 'location', 'budget', 'latitude', 'longitude']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Need Plumber for Bathroom Repair'}),
            'description': forms.Textarea(attrs={
                'rows': 8, 
                'class': 'form-control', 
                'placeholder': 'Describe the job in detail. Include required skills, experience level, and specific tasks.\n\nExample: "Need an experienced plumber to fix a leaking pipe and install new bathroom fixtures. Must have own tools. Experience with PVC pipes required."'
            }),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Nairobi, CBD'}),
            'budget': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'KES'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Optional'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Optional'}),
        }
    
    def extract_skills_from_description(self, description):
        """Extract skills from job description using keyword matching"""
        if not description:
            return []
        
        description_lower = description.lower()
        
        # Comprehensive skill keywords mapping
        skill_keywords = {
            # Construction & Trade
            'Plumbing': ['plumber', 'plumbing', 'pipe', 'water pipe', 'drain', 'faucet', 'toilet', 'sink', 'bathroom', 'water heater', 'pipe fitting'],
            'Electrical': ['electrician', 'electrical', 'wiring', 'circuit', 'lighting', 'socket', 'switch', 'breaker', 'fuse', 'power'],
            'Carpentry': ['carpenter', 'carpentry', 'woodwork', 'furniture', 'cabinet', 'joinery', 'wood working', 'shelving'],
            'Masonry': ['mason', 'masonry', 'bricklaying', 'concrete', 'cement', 'block work', 'brick', 'plastering'],
            'Painting': ['painter', 'painting', 'paint', 'coating', 'wall finish', 'spray painting', 'wallpaper'],
            'Welding': ['welder', 'welding', 'metal work', 'fabrication', 'steel', 'aluminum', 'iron work'],
            'Tiling': ['tiler', 'tiling', 'tile', 'floor tile', 'wall tile', 'ceramic', 'grout'],
            'Roofing': ['roofer', 'roofing', 'roof', 'shingles', 'metal roof', 'ceiling'],
            'General Construction': ['construction', 'building', 'renovation', 'remodeling', 'site work', 'handyman'],
            
            # Domestic Services
            'Cleaning': ['cleaner', 'cleaning', 'sanitize', 'sweep', 'mop', 'dusting', 'janitor', 'house cleaning'],
            'Housekeeping': ['housekeeper', 'housekeeping', 'maid', 'domestic work', 'home cleaning'],
            'Laundry': ['laundry', 'washing', 'ironing', 'fold clothes', 'dry cleaning'],
            
            # Transport & Logistics
            'Driving': ['driver', 'driving', 'delivery', 'transport', 'taxi', 'courier', 'pickup', 'drop off'],
            'Loading': ['loader', 'loading', 'unloading', 'moving', 'lifting', 'heavy lifting', 'carrying'],
            
            # Hospitality & Food
            'Cooking': ['cook', 'chef', 'kitchen', 'food preparation', 'meal prep', 'catering', 'cooking'],
            'Baking': ['baker', 'baking', 'pastry', 'bread', 'cakes', 'confectionery'],
            'Restaurant Service': ['waiter', 'waitress', 'server', 'restaurant', 'food service', 'customer service'],
            
            # Landscaping & Outdoor
            'Gardening': ['gardener', 'gardening', 'planting', 'pruning', 'weeding', 'flowers', 'vegetables'],
            'Landscaping': ['landscaper', 'landscaping', 'lawn care', 'grass cutting', 'mowing', 'hedge trimming'],
            'Tree Cutting': ['tree cutter', 'tree cutting', 'tree removal', 'arborist', 'logging'],
            
            # Security
            'Security Guard': ['security guard', 'security', 'guard', 'patrol', 'surveillance', 'watchman', 'safety'],
            
            # Caregiving & Health
            'Childcare': ['nanny', 'babysitter', 'child care', 'kids', 'children', 'daycare', 'infant care'],
            'Elderly Care': ['caregiver', 'elder care', 'senior care', 'aged care', 'old age', 'home care'],
            'Special Needs Care': ['special needs', 'disabled care', 'special education'],
            
            # Education & Tutoring
            'Tutoring': ['tutor', 'tutoring', 'teaching', 'education', 'homework help', 'instruction', 'coaching'],
            'Language Teaching': ['language teacher', 'english', 'swahili', 'french', 'language instruction'],
            
            # Beauty & Fashion
            'Tailoring': ['tailor', 'tailoring', 'sewing', 'stitching', 'alteration', 'dressmaking', 'garment'],
            'Hair Styling': ['hairdresser', 'hair stylist', 'barber', 'haircut', 'hairstyling', 'braiding'],
            'Makeup': ['makeup artist', 'makeup', 'cosmetics', 'beauty', 'facials'],
            'Nail Care': ['manicure', 'pedicure', 'nail art', 'nail technician'],
            
            # Wellness & Fitness
            'Massage': ['masseuse', 'massage', 'therapy', 'spa', 'bodywork', 'therapeutic'],
            'Fitness Training': ['fitness trainer', 'gym instructor', 'personal trainer', 'exercise', 'workout'],
            
            # Technical & Repair
            'Phone Repair': ['phone repair', 'mobile repair', 'smartphone repair', 'iphone repair', 'screen replacement'],
            'Computer Repair': ['computer repair', 'pc repair', 'laptop repair', 'desktop repair', 'tech support'],
            'Appliance Repair': ['appliance repair', 'fridge repair', 'washing machine repair', 'oven repair'],
            'AC Repair': ['ac repair', 'air conditioning', 'hvac', 'cooling system', 'aircon'],
            
            # Office & Admin
            'Data Entry': ['data entry', 'typing', 'office work', 'administrative', 'paperwork', 'filing'],
            'Customer Service': ['customer service', 'sales', 'retail', 'cashier', 'front desk', 'reception'],
            'Secretarial': ['secretary', 'personal assistant', 'admin assistant', 'office assistant'],
        }
        
        extracted_skills = []
        
        for skill_name, keywords in skill_keywords.items():
            for keyword in keywords:
                if keyword in description_lower:
                    extracted_skills.append(skill_name)
                    break  # Add skill once per match
        
        # Remove duplicates while preserving order
        unique_skills = []
        for skill in extracted_skills:
            if skill not in unique_skills:
                unique_skills.append(skill)
        
        return unique_skills
    
    def get_skill_category(self, skill_name):
        """Determine category for a skill"""
        categories = {
            'Plumbing': 'Construction',
            'Electrical': 'Construction',
            'Carpentry': 'Construction',
            'Masonry': 'Construction',
            'Painting': 'Construction',
            'Welding': 'Construction',
            'Tiling': 'Construction',
            'Roofing': 'Construction',
            'General Construction': 'Construction',
            'Cleaning': 'Domestic',
            'Housekeeping': 'Domestic',
            'Laundry': 'Domestic',
            'Driving': 'Transport',
            'Loading': 'General',
            'Cooking': 'Hospitality',
            'Baking': 'Hospitality',
            'Restaurant Service': 'Hospitality',
            'Gardening': 'Landscaping',
            'Landscaping': 'Landscaping',
            'Tree Cutting': 'Landscaping',
            'Security Guard': 'Security',
            'Childcare': 'Caregiving',
            'Elderly Care': 'Caregiving',
            'Special Needs Care': 'Caregiving',
            'Tutoring': 'Education',
            'Language Teaching': 'Education',
            'Tailoring': 'Fashion',
            'Hair Styling': 'Beauty',
            'Makeup': 'Beauty',
            'Nail Care': 'Beauty',
            'Massage': 'Wellness',
            'Fitness Training': 'Wellness',
            'Phone Repair': 'Technical',
            'Computer Repair': 'Technical',
            'Appliance Repair': 'Technical',
            'AC Repair': 'Technical',
            'Data Entry': 'Office',
            'Customer Service': 'Office',
            'Secretarial': 'Office',
        }
        return categories.get(skill_name, 'General')
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if commit:
            instance.save()
            # Extract skills from description after saving
            extracted_skill_names = self.extract_skills_from_description(instance.description)
            
            if extracted_skill_names:
                skills_to_add = []
                for skill_name in extracted_skill_names:
                    # Get or create the skill
                    skill, created = Skill.objects.get_or_create(
                        name=skill_name,
                        defaults={'category': self.get_skill_category(skill_name)}
                    )
                    skills_to_add.append(skill)
                
                # Add skills to the job
                if skills_to_add:
                    instance.required_skills.set(skills_to_add)
        
        return instance

class RatingForm(forms.ModelForm):
    class Meta:
        model = Rating
        fields = ['score', 'comment']
        widgets = {
            'score': forms.Select(choices=[(i, i) for i in range(1, 6)], attrs={'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Share your experience working with this worker...'}),
        }

class JobApplicationForm(forms.ModelForm):
    class Meta:
        model = JobApplication
        fields = ['cover_letter', 'proposed_rate']
        widgets = {
            'cover_letter': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Why are you a good fit for this job?'}),
            'proposed_rate': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Your proposed hourly rate (optional)'}),
        }

class ChatMessageForm(forms.Form):
    message = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ask me about skills, jobs, or how to improve your profile...',
            'autocomplete': 'off'
        })
    )