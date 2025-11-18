import google.generativeai as genai
import json
import re
from django.conf import settings
from typing import List, Dict, Any
from .models import Skill, WorkerProfile

class WorkNetChatbot:
    def __init__(self):
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in settings")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-pro')
    
    def get_response(self, user_message: str, user_profile: WorkerProfile = None) -> str:
        """Generate chatbot response based on user message"""
        
        context = self._get_context(user_profile)
        
        prompt = f"""
        You are WorkNet Assistant, a helpful AI chatbot for the WorkNet platform that connects workers with employers.
        
        Context about the user: {context}
        
        User message: {user_message}
        
        Your role is to:
        1. Help workers understand what skills are in demand
        2. Assist employers in finding the right workers
        3. Provide guidance on improving profiles
        4. Explain how the matching system works
        5. Offer career advice and skill development suggestions
        
        Be friendly, helpful, and specific. If you need more information to provide better advice, ask clarifying questions.
        
        Keep your response conversational and under 300 words.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"I apologize, but I'm having trouble responding right now. Please try again later. Error: {str(e)}"
    
    def _get_context(self, user_profile: WorkerProfile) -> str:
        """Get context about the user for personalized responses"""
        if not user_profile:
            return "User profile not available"
        
        context = f"User type: {user_profile.user_type}, "
        
        if user_profile.user_type == 'worker':
            skills = user_profile.extracted_skills.all()
            skill_list = [skill.name for skill in skills]
            context += f"Skills: {', '.join(skill_list) if skill_list else 'No skills listed'}, "
            context += f"Location: {user_profile.location}, "
            context += f"Reliability score: {user_profile.reliability_score}"
        
        elif user_profile.user_type == 'employer':
            context += f"Location: {user_profile.location}"
        
        # Add platform statistics
        total_workers = WorkerProfile.objects.filter(user_type='worker', is_approved=True).count()
        total_skills = Skill.objects.count()
        context += f". Platform has {total_workers} active workers and {total_skills} different skills."
        
        return context
    
    def analyze_skills_gap(self, current_skills: List[str], desired_role: str) -> str:
        """Analyze skill gaps for career advancement"""
        
        prompt = f"""
        Analyze the skill gap between the worker's current skills and their desired role.
        
        Current skills: {', '.join(current_skills)}
        Desired role: {desired_role}
        
        Provide:
        1. Missing key skills for the desired role
        2. Recommended learning resources or steps
        3. Timeline suggestions for skill development
        4. Alternative roles that match current skills
        
        Be specific and actionable in your advice.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Unable to analyze skill gap at the moment. Please try again later."
    
    def suggest_skill_improvements(self, worker_profile: WorkerProfile) -> str:
        """Suggest improvements for worker's skill profile"""
        
        skills = worker_profile.extracted_skills.all()
        skill_data = [f"{skill.name} (Level: {worker_profile.workerskill_set.get(skill=skill).proficiency_level})" 
                     for skill in skills]
        
        prompt = f"""
        Analyze this worker's profile and suggest improvements:
        
        Current skills: {', '.join(skill_data)}
        Bio: {worker_profile.bio}
        Skills description: {worker_profile.skills_description}
        Location: {worker_profile.location}
        
        Provide specific suggestions for:
        1. Skills to add based on location and market demand
        2. How to improve existing skill proficiency levels
        3. Profile bio improvements
        4. Pricing strategy (current rate: {worker_profile.hourly_rate})
        
        Be constructive and practical in your advice.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return "Unable to provide skill improvement suggestions at the moment."