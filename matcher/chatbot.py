import google.generativeai as genai
import json
import re
import logging
from django.conf import settings
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class WorkNetChatbot:
    def __init__(self):
        self.available = False
        self._configure_gemini()
    
    def _configure_gemini(self):
        """Configure Gemini API with error handling"""
        try:
            api_key = getattr(settings, 'GEMINI_API_KEY', None)
            if not api_key:
                logger.warning("GEMINI_API_KEY not found in settings")
                self.available = False
                return
            
            genai.configure(api_key=api_key)
            # Use flash-lite model which has higher free tier limits
            self.model = genai.GenerativeModel('gemini-1.5-flash-lite')
            self.available = True
            logger.info("Chatbot Gemini configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure chatbot Gemini: {e}")
            self.available = False
    
    def get_response(self, user_message: str, user_profile = None) -> str:
        """Generate chatbot response based on user message with fallback"""
        
        # If Gemini is not available, use fallback responses
        if not self.available:
            return self._fallback_response(user_message, user_profile)
        
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
        
        Be friendly, helpful, and specific. Keep your response conversational and under 300 words.
        """
        
        try:
            response = self.model.generate_content(prompt)
            if response and response.text:
                return response.text
            else:
                return self._fallback_response(user_message, user_profile)
        except Exception as e:
            error_msg = str(e).lower()
            if '429' in error_msg or 'quota' in error_msg or 'rate limit' in error_msg or 'resource exhausted' in error_msg:
                logger.warning(f"Chatbot quota exceeded: {e}")
                return self._fallback_response(user_message, user_profile)
            else:
                logger.error(f"Chatbot error: {e}")
                return self._fallback_response(user_message, user_profile)
    
    def _fallback_response(self, user_message: str, user_profile = None) -> str:
        """Fallback responses when AI is unavailable"""
        message_lower = user_message.lower()
        
        # Simple keyword-based responses
        if any(word in message_lower for word in ['job', 'work', 'find']):
            return "You can find jobs by going to the 'Find Work' section in your dashboard. Use the search filters to narrow down opportunities that match your skills."
        
        elif any(word in message_lower for word in ['skill', 'learn', 'improve']):
            return "To improve your skills, check the 'Skill Analysis' section. You can add new skills to your profile and see recommendations for in-demand skills in your area."
        
        elif any(word in message_lower for word in ['profile', 'update', 'edit']):
            return "You can update your profile by clicking on your name in the top right corner and selecting 'Profile & Visibility'. Make sure to add a detailed bio and list all your skills."
        
        elif any(word in message_lower for word in ['employer', 'hire', 'post']):
            return "To post a job, go to your employer dashboard and click 'Post a Job'. Fill in the details and our matching system will find suitable workers for you."
        
        elif any(word in message_lower for word in ['match', 'recommend']):
            return "Our matching system analyzes job requirements and worker skills to find the best matches. Check your 'Recommended Jobs' or 'Matches' section for personalized suggestions."
        
        else:
            return "I'm here to help! You can ask me about finding jobs, improving your skills, updating your profile, or posting jobs as an employer. What would you like to know?"
    
    def _get_context(self, user_profile) -> str:
        """Get context about the user for personalized responses"""
        if not user_profile:
            return "User profile not available"
        
        try:
            context = f"User type: {user_profile.user_type}, "
            
            if user_profile.user_type == 'worker':
                skills = user_profile.extracted_skills.all() if hasattr(user_profile, 'extracted_skills') else []
                skill_list = [skill.name for skill in skills][:5]
                context += f"Skills: {', '.join(skill_list) if skill_list else 'No skills listed'}, "
                context += f"Location: {user_profile.location}, "
                context += f"Reliability score: {user_profile.reliability_score}"
            
            elif user_profile.user_type == 'employer':
                context += f"Location: {user_profile.location}"
            
            return context
        except Exception as e:
            logger.error(f"Error getting context: {e}")
            return "User profile available but couldn't load details"
    
    def analyze_skills_gap(self, current_skills: List[str], desired_role: str) -> str:
        """Analyze skill gaps for career advancement with fallback"""
        
        if not self.available:
            return self._fallback_skill_gap_analysis(current_skills, desired_role)
        
        prompt = f"""
        Analyze the skill gap between the worker's current skills and their desired role.
        
        Current skills: {', '.join(current_skills)}
        Desired role: {desired_role}
        
        Provide:
        1. Missing key skills for the desired role
        2. Recommended learning resources or steps
        3. Timeline suggestions for skill development
        4. Alternative roles that match current skills
        
        Be specific and actionable in your advice. Keep response under 400 words.
        """
        
        try:
            response = self.model.generate_content(prompt)
            if response and response.text:
                return response.text
            else:
                return self._fallback_skill_gap_analysis(current_skills, desired_role)
        except Exception as e:
            error_msg = str(e).lower()
            if '429' in error_msg or 'quota' in error_msg or 'rate limit' in error_msg:
                logger.warning(f"Skill analysis quota exceeded: {e}")
                return self._fallback_skill_gap_analysis(current_skills, desired_role)
            else:
                logger.error(f"Skill analysis error: {e}")
                return "Unable to analyze skill gap at the moment. Please try again later."
    
    def _fallback_skill_gap_analysis(self, current_skills: List[str], desired_role: str) -> str:
        """Fallback skill gap analysis without AI"""
        
        if not current_skills:
            return f"To become a {desired_role}, you should start by learning basic skills in that field. Consider taking online courses or apprenticeships to gain experience."
        
        common_gaps = {
            'developer': ['JavaScript', 'Python', 'Git', 'Problem Solving'],
            'designer': ['Figma', 'Adobe XD', 'User Research', 'Prototyping'],
            'manager': ['Leadership', 'Communication', 'Project Planning', 'Budgeting'],
            'plumber': ['Pipe Installation', 'Blueprint Reading', 'Building Codes'],
            'electrician': ['Wiring', 'Safety Standards', 'Circuit Design'],
        }
        
        # Find matching role keywords
        recommended_skills = []
        for role, skills in common_gaps.items():
            if role in desired_role.lower():
                recommended_skills = skills
                break
        
        if not recommended_skills:
            recommended_skills = ['Communication', 'Time Management', 'Problem Solving']
        
        missing_skills = [skill for skill in recommended_skills if skill.lower() not in [s.lower() for s in current_skills]]
        
        if missing_skills:
            return f"To advance as a {desired_role}, focus on developing these skills: {', '.join(missing_skills)}. Consider online courses on platforms like Coursera, Udemy, or local vocational training."
        else:
            return f"Your current skills align well with {desired_role}! Focus on gaining practical experience and building a portfolio of your work."