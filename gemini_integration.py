import google.generativeai as genai
import json
import re
import logging
from django.conf import settings
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class GeminiSkillExtractor:
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
            logger.info("Gemini API configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure Gemini: {e}")
            self.available = False
    
    def extract_skills_from_description(self, description: str) -> List[Dict[str, Any]]:
        """Extract structured skills from worker's text description with fallback"""
        
        # If Gemini is not available, use fallback
        if not self.available:
            logger.info("Gemini not available, using fallback skill extraction")
            return self._fallback_skill_extraction(description)
        
        prompt = f"""
        Analyze the following worker description and extract skills, categories, and proficiency levels.
        Return ONLY a JSON array of objects with this exact structure:
        [
            {{
                "skill_name": "string",
                "category": "string",
                "proficiency_level": integer (1-5),
                "years_experience": float
            }}
        ]
        
        Description: {description}
        
        Guidelines:
        - skill_name: specific technical or soft skills
        - category: broader category like "Construction", "IT", "Healthcare", "Cleaning", "Driving", etc.
        - proficiency_level: 1 (beginner) to 5 (expert)
        - years_experience: estimate based on context
        
        Return ONLY valid JSON, no other text.
        """
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            
            # Clean the response to extract JSON
            text = re.sub(r'^```json\s*|\s*```$', '', text)
            text = re.sub(r'^```\s*|\s*```$', '', text)
            
            skills_data = json.loads(text)
            if skills_data and len(skills_data) > 0:
                logger.info(f"Successfully extracted {len(skills_data)} skills using Gemini")
                return skills_data
            else:
                return self._fallback_skill_extraction(description)
                
        except Exception as e:
            error_msg = str(e).lower()
            # Check for quota exceeded errors
            if '429' in error_msg or 'quota' in error_msg or 'rate limit' in error_msg or 'resource exhausted' in error_msg:
                logger.warning(f"Gemini quota exceeded: {e}")
                return self._fallback_skill_extraction(description)
            else:
                logger.error(f"Gemini extraction error: {e}")
                return self._fallback_skill_extraction(description)
    
    def _fallback_skill_extraction(self, description: str) -> List[Dict[str, Any]]:
        """Fallback method to extract skills without AI"""
        skills = []
        description_lower = description.lower()
        
        # Common skills mapping
        common_skills = {
            'plumbing': {'category': 'Construction', 'proficiency': 3, 'years': 2},
            'carpentry': {'category': 'Construction', 'proficiency': 3, 'years': 2},
            'electrical': {'category': 'Construction', 'proficiency': 3, 'years': 2},
            'painting': {'category': 'Construction', 'proficiency': 3, 'years': 1},
            'welding': {'category': 'Construction', 'proficiency': 3, 'years': 2},
            'masonry': {'category': 'Construction', 'proficiency': 3, 'years': 2},
            'cleaning': {'category': 'Domestic', 'proficiency': 3, 'years': 1},
            'cooking': {'category': 'Hospitality', 'proficiency': 3, 'years': 2},
            'driving': {'category': 'Transport', 'proficiency': 3, 'years': 2},
            'childcare': {'category': 'Caregiving', 'proficiency': 3, 'years': 1},
            'gardening': {'category': 'Landscaping', 'proficiency': 3, 'years': 1},
            'security': {'category': 'Security', 'proficiency': 3, 'years': 1},
        }
        
        for skill_name, skill_info in common_skills.items():
            if skill_name in description_lower:
                skills.append({
                    'skill_name': skill_name,
                    'category': skill_info['category'],
                    'proficiency_level': skill_info['proficiency'],
                    'years_experience': skill_info['years']
                })
        
        # If no skills found, add a default
        if not skills:
            skills.append({
                'skill_name': 'general_labor',
                'category': 'General',
                'proficiency_level': 3,
                'years_experience': 1
            })
        
        logger.info(f"Fallback extraction found {len(skills)} skills")
        return skills
    
    def generate_job_matches(self, job_description: str, workers_data: List[Dict]) -> List[Dict]:
        """Generate ranked worker matches for a job using AI analysis with fallback"""
        
        # If Gemini is not available, use fallback
        if not self.available:
            logger.info("Gemini not available, using fallback matching")
            return self._fallback_match_generation(workers_data)
        
        prompt = f"""
        Analyze this job request and rank workers based on skill relevance, experience, and reliability.
        
        Job Description: {job_description}
        
        Workers Data: {json.dumps(workers_data, indent=2)}
        
        Return a JSON array of ranked workers with scores (0.0-1.0):
        [
            {{
                "worker_id": "original_id",
                "match_score": float (0.0-1.0),
                "skill_relevance": float (0.0-1.0),
                "proximity_score": float (0.0-1.0),
                "reliability_score": float (0.0-1.0),
                "ai_notes": "string explaining the match"
            }}
        ]
        
        Consider:
        - Skill match between job requirements and worker skills
        - Experience level and proficiency
        - Reliability history
        - Geographic proximity (already included in proximity_score)
        
        Return ONLY valid JSON, no other text.
        """
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            text = re.sub(r'^```json\s*|\s*```$', '', text)
            text = re.sub(r'^```\s*|\s*```$', '', text)
            
            matches = json.loads(text)
            logger.info(f"Successfully generated {len(matches)} matches using Gemini")
            return matches
        except Exception as e:
            error_msg = str(e).lower()
            if '429' in error_msg or 'quota' in error_msg or 'rate limit' in error_msg or 'resource exhausted' in error_msg:
                logger.warning(f"Gemini quota exceeded for matching: {e}")
            else:
                logger.error(f"Gemini matching error: {e}")
            return self._fallback_match_generation(workers_data)
    
    def _fallback_match_generation(self, workers_data: List[Dict]) -> List[Dict]:
        """Fallback method to generate matches without AI"""
        matches = []
        
        for worker in workers_data:
            # Calculate simple match score based on skills and reliability
            skill_count = len(worker.get('skills', []))
            skill_score = min(skill_count / 10, 1.0)  # 10 skills = max score
            
            reliability = worker.get('reliability_score', 3.0) / 5.0  # Convert to 0-1
            
            # Combined score
            match_score = (skill_score * 0.6 + reliability * 0.4)
            
            matches.append({
                'worker_id': worker['worker_id'],
                'match_score': match_score,
                'skill_relevance': skill_score,
                'proximity_score': 0.5,  # Default
                'reliability_score': reliability,
                'ai_notes': 'Basic matching (AI quota exceeded)'
            })
        
        # Sort by match score
        matches.sort(key=lambda x: x['match_score'], reverse=True)
        logger.info(f"Fallback matching generated {len(matches)} matches")
        return matches


class MatchingEngine:
    def __init__(self):
        self.gemini = GeminiSkillExtractor()
    
    def calculate_proximity(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate proximity score between two locations (0-1)"""
        if not all([lat1, lon1, lat2, lon2]):
            return 0.5  # Default score if location data missing
        
        # Simple distance calculation
        distance = ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5
        
        # Convert to proximity score (closer = higher score)
        max_distance = 0.1
        proximity = max(0, 1 - (distance / max_distance))
        return min(proximity, 1.0)
    
    def match_workers_to_job(self, job):
        """Main matching function that combines AI and algorithmic scoring"""
        
        # Import models here to avoid circular imports
        from .models import WorkerProfile, WorkerSkill
        
        # Get approved workers with relevant skills
        workers = WorkerProfile.objects.filter(
            is_approved=True,
            user_type='worker'
        ).distinct()
        
        # If job has required skills, filter by them
        if hasattr(job, 'required_skills') and job.required_skills.exists():
            workers = workers.filter(
                extracted_skills__in=job.required_skills.all()
            ).distinct()
        
        workers_data = []
        for worker in workers:
            worker_skills = WorkerSkill.objects.filter(worker=worker)
            skills_list = [
                {
                    'skill_name': ws.skill.name,
                    'category': ws.skill.category,
                    'proficiency': ws.proficiency_level,
                    'experience': ws.years_of_experience
                }
                for ws in worker_skills
            ]
            
            workers_data.append({
                'worker_id': worker.id,
                'skills': skills_list,
                'reliability_score': worker.reliability_score,
                'location': {
                    'lat': getattr(worker, 'latitude', 0) or 0,
                    'lon': getattr(worker, 'longitude', 0) or 0
                }
            })
        
        # If no workers, return empty list
        if not workers_data:
            return []
        
        # Get AI-generated matches (with automatic fallback)
        ai_matches = self.gemini.generate_job_matches(
            getattr(job, 'description', ''),
            workers_data
        )
        
        # Combine AI scores with algorithmic proximity
        final_matches = []
        for ai_match in ai_matches:
            try:
                worker = workers.get(id=ai_match['worker_id'])
                
                # Calculate proximity if location data available
                proximity = self.calculate_proximity(
                    getattr(job, 'latitude', 0) or 0, 
                    getattr(job, 'longitude', 0) or 0,
                    getattr(worker, 'latitude', 0) or 0, 
                    getattr(worker, 'longitude', 0) or 0
                )
                
                # Combine scores
                final_score = (
                    ai_match.get('skill_relevance', 0.5) * 0.5 +
                    ai_match.get('reliability_score', 0.5) * 0.3 +
                    proximity * 0.2
                )
                
                final_matches.append({
                    'worker': worker,
                    'match_score': final_score,
                    'skill_relevance': ai_match.get('skill_relevance', 0.5),
                    'proximity_score': proximity,
                    'reliability_score': ai_match.get('reliability_score', 0.5),
                    'ai_notes': ai_match.get('ai_notes', 'Matching completed')
                })
            except WorkerProfile.DoesNotExist:
                continue
        
        # Sort by final match score
        final_matches.sort(key=lambda x: x['match_score'], reverse=True)
        
        # Log the matching method used
        if any('quota' in match.get('ai_notes', '').lower() for match in final_matches[:1]):
            logger.info("Using fallback matching due to quota limits")
        else:
            logger.info(f"Successfully matched {len(final_matches)} workers")
        
        return final_matches