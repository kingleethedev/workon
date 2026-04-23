# matcher/matching.py
from django.db.models import Q

# matcher/matching.py
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)

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
        from .models import WorkerProfile, WorkerSkill, Skill
        
        # Log job info
        logger.info(f"=== Matching for Job: {job.title} (ID: {job.id}) ===")
        job_skills = set(job.required_skills.all())
        logger.info(f"Job required skills: {[s.name for s in job_skills]}")
        logger.info(f"Number of required skills: {len(job_skills)}")
        
        workers = WorkerProfile.objects.filter(
            is_approved=True,
            user_type='worker'
        )
        logger.info(f"Total approved workers: {workers.count()}")
        
        matches = []
        
        for worker in workers:
            # Get worker skills from WorkerSkill model (manually entered skills)
            worker_skills_qs = WorkerSkill.objects.filter(worker=worker).select_related('skill')
            worker_skills = set(ws.skill for ws in worker_skills_qs)
            
            # Also check extracted_skills as fallback
            extracted_skills = set(worker.extracted_skills.all())
            all_worker_skills = worker_skills | extracted_skills
            
            logger.debug(f"Worker {worker.user.username}:")
            logger.debug(f"  - Manual skills: {[s.name for s in worker_skills]}")
            logger.debug(f"  - Extracted skills: {[s.name for s in extracted_skills]}")
            logger.debug(f"  - Total skills: {len(all_worker_skills)}")
            
            # Calculate skill match (as decimal 0-1)
            skill_match = 0.0
            if job_skills:
                common_skills = all_worker_skills & job_skills
                skill_match = len(common_skills) / len(job_skills)
                logger.debug(f"  - Common skills: {[s.name for s in common_skills]}")
                logger.debug(f"  - Skill match: {skill_match}")
            else:
                # If no job skills required, give full score
                skill_match = 1.0
                logger.debug(f"  - No job skills required, skill match set to 1.0")
            
            # Calculate proximity (as decimal 0-1)
            proximity = self.calculate_proximity(
                job.latitude or 0, job.longitude or 0,
                worker.latitude or 0, worker.longitude or 0
            )
            
            # Reliability score (normalized to 0-1)
            reliability = worker.reliability_score / 5.0
            
            # Combined score (all as decimals 0-1)
            if job_skills:
                match_score = (skill_match * 0.6 + reliability * 0.2 + proximity * 0.2)
            else:
                match_score = (skill_match * 0.4 + reliability * 0.3 + proximity * 0.3)
            
            # Store scores as decimals (0-1) for database
            logger.debug(f"  - Match score (decimal): {match_score}")
            
            if match_score > 0.1:  # Only include reasonable matches
                matches.append({
                    'worker': worker,
                    'match_score': match_score,  # Keep as decimal for database
                    'skill_relevance': skill_match,  # Keep as decimal
                    'proximity_score': proximity,
                    'reliability_score': reliability,
                    'ai_notes': f"Skills: {skill_match*100:.0f}%, Reliability: {reliability*100:.0f}%, Proximity: {proximity*100:.0f}%"
                })
        
        # Sort by match score
        matches = sorted(matches, key=lambda x: x['match_score'], reverse=True)
        
        logger.info(f"Total matches found: {len(matches)}")
        if matches:
            logger.info(f"Top match score: {matches[0]['match_score']}")
        
        return matches
    
    def _generate_match_notes(self, skill_match, reliability, proximity, skill_variety, skill_count):
        """Generate helpful match notes without using Gemini"""
        notes_parts = []
        
        # Skill match analysis
        if skill_match >= 0.8:
            notes_parts.append(f"✅ Excellent skill match ({skill_match*100:.0f}%)")
        elif skill_match >= 0.6:
            notes_parts.append(f"👍 Good skill match ({skill_match*100:.0f}%)")
        elif skill_match >= 0.4:
            notes_parts.append(f"📊 Moderate skill match ({skill_match*100:.0f}%)")
        elif skill_match > 0:
            notes_parts.append(f"⚠️ Low skill match ({skill_match*100:.0f}%)")
        
        # Reliability analysis
        if reliability >= 0.8:
            notes_parts.append(f"⭐ High reliability ({(reliability*5):.1f}/5)")
        elif reliability >= 0.6:
            notes_parts.append(f"👍 Good reliability ({(reliability*5):.1f}/5)")
        
        # Proximity analysis  
        if proximity >= 0.8:
            notes_parts.append(f"📍 Very close proximity")
        elif proximity >= 0.5:
            notes_parts.append(f"📍 Nearby location")
        
        # Skill variety
        if skill_count > 0:
            notes_parts.append(f"🔧 Has {skill_count} skill(s)")
            if skill_variety >= 0.7:
                notes_parts.append(f"🎯 Versatile worker")
        
        if not notes_parts:
            notes_parts.append("Basic match based on availability")
        
        return " | ".join(notes_parts)
    
    def match_workers_by_skill_only(self, skill_names):
        """Quick matching by skill names only (useful for job search)"""
        from .models import WorkerProfile, WorkerSkill, Skill
        
        # Get skill objects
        skills = Skill.objects.filter(name__in=skill_names)
        
        # Find workers with these skills
        workers = WorkerProfile.objects.filter(
            is_approved=True,
            user_type='worker',
            workerskill__skill__in=skills
        ).distinct().prefetch_related('workerskill_set__skill')
        
        matches = []
        for worker in workers:
            worker_skills = set(ws.skill.name for ws in worker.workerskill_set.all())
            matching_skills = set(skill_names) & worker_skills
            
            skill_match_score = len(matching_skills) / len(skill_names) if skill_names else 0
            
            matches.append({
                'worker': worker,
                'match_score': skill_match_score,
                'matching_skills': list(matching_skills),
                'total_matches': len(matching_skills)
            })
        
        return sorted(matches, key=lambda x: x['match_score'], reverse=True)