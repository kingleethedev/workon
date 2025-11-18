import google.generativeai as genai
import json
import re
from django.conf import settings
from typing import List, Dict, Any

class GeminiSkillExtractor:
    def __init__(self):
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in settings")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-pro')
    
    def extract_skills_from_description(self, description: str) -> List[Dict[str, Any]]:
        """Extract structured skills from worker's text description"""
        
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
            
            skills_data = json.loads(text)
            return skills_data
        except Exception as e:
            print(f"Error extracting skills: {e}")
            return []
    
    def generate_job_matches(self, job_description: str, workers_data: List[Dict]) -> List[Dict]:
        """Generate ranked worker matches for a job using AI analysis"""
        
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
            
            matches = json.loads(text)
            return matches
        except Exception as e:
            print(f"Error generating matches: {e}")
            return []

class MatchingEngine:
    def __init__(self):
        self.gemini = GeminiSkillExtractor()
    
    def calculate_proximity(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate proximity score between two locations (0-1)"""
        if not all([lat1, lon1, lat2, lon2]):
            return 0.5  # Default score if location data missing
        
        # Simple distance calculation (Haversine would be better in production)
        distance = ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5
        
        # Convert to proximity score (closer = higher score)
        max_distance = 0.1  # Adjust based on your scale
        proximity = max(0, 1 - (distance / max_distance))
        return min(proximity, 1.0)
    
    def match_workers_to_job(self, job):
        """Main matching function that combines AI and algorithmic scoring"""
        
        # Import models here to avoid circular imports
        from matcher.models import WorkerProfile, WorkerSkill, JobMatch
        
        # Get approved workers with relevant skills
        workers = WorkerProfile.objects.filter(
            is_approved=True,
            user_type='worker'
        ).distinct()
        
        # If job has required skills, filter by them
        if job.required_skills.exists():
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
                    'lat': worker.latitude or 0,
                    'lon': worker.longitude or 0
                }
            })
        
        # Get AI-generated matches
        ai_matches = self.gemini.generate_job_matches(
            job.description,
            workers_data
        )
        
        # Combine AI scores with algorithmic proximity
        final_matches = []
        for ai_match in ai_matches:
            try:
                worker = workers.get(id=ai_match['worker_id'])
                
                # Calculate proximity if location data available
                proximity = self.calculate_proximity(
                    job.latitude or 0, job.longitude or 0,
                    worker.latitude or 0, worker.longitude or 0
                )
                
                # Combine scores (adjust weights as needed)
                final_score = (
                    ai_match['skill_relevance'] * 0.5 +
                    ai_match['reliability_score'] * 0.3 +
                    proximity * 0.2
                )
                
                final_matches.append({
                    'worker': worker,
                    'match_score': final_score,
                    'skill_relevance': ai_match['skill_relevance'],
                    'proximity_score': proximity,
                    'reliability_score': ai_match['reliability_score'],
                    'ai_notes': ai_match['ai_notes']
                })
            except WorkerProfile.DoesNotExist:
                continue  # Skip if worker doesn't exist
        
        # Sort by final match score
        return sorted(final_matches, key=lambda x: x['match_score'], reverse=True)