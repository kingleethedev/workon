# matcher/matching.py
from django.db.models import Q

class SimpleMatchingEngine:
    """Simple matching engine that doesn't require Gemini API"""
    
    def calculate_proximity(self, lat1, lon1, lat2, lon2):
        """Simple proximity calculation"""
        if not all([lat1, lon1, lat2, lon2]):
            return 0.5
        distance = ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5
        max_distance = 0.1
        proximity = max(0, 1 - (distance / max_distance))
        return min(proximity, 1.0)
    
    def match_workers_to_job(self, job):
        """Simple matching based on skills and reliability"""
        from .models import WorkerProfile
        
        workers = WorkerProfile.objects.filter(
            is_approved=True,
            user_type='worker'
        )
        
        matches = []
        for worker in workers:
            # Calculate skill match
            skill_match = 0.0
            if job.required_skills.exists():
                worker_skills = worker.extracted_skills.all()
                common_skills = worker_skills & job.required_skills.all()
                if job.required_skills.count() > 0:
                    skill_match = len(common_skills) / job.required_skills.count()
            
            # Calculate proximity
            proximity = self.calculate_proximity(
                job.latitude or 0, job.longitude or 0,
                worker.latitude or 0, worker.longitude or 0
            )
            
            # Reliability score (normalized to 0-1)
            reliability = worker.reliability_score / 5.0
            
            # Combined score
            if job.required_skills.exists():
                match_score = (skill_match * 0.6 + reliability * 0.2 + proximity * 0.2)
            else:
                match_score = (reliability * 0.5 + proximity * 0.5)
            
            if match_score > 0.1:  # Only include reasonable matches
                matches.append({
                    'worker': worker,
                    'match_score': match_score,
                    'skill_relevance': skill_match,
                    'proximity_score': proximity,
                    'reliability_score': reliability,
                    'ai_notes': f"Skills: {skill_match:.2f}, Reliability: {reliability:.2f}, Proximity: {proximity:.2f}"
                })
        
        return sorted(matches, key=lambda x: x['match_score'], reverse=True)