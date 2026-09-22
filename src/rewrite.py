
import os
from typing import List

def suggest_bullets(role_title: str, jd_text: str, existing_bullets: List[str], missing_keywords: List[str]) -> List[str]:
    """Offline, templated suggestions to inspire bullet rewrites without fabricating content."""
    tips = []
    for kw in missing_keywords[:8]:
        tips.append(f"Highlight impact with '{kw}': Achieved X% improvement by applying {kw} to [project/task].")
    if not tips:
        tips.append("Quantify results (%, time saved, errors reduced) and lead with strong verbs (Built, Optimized, Deployed).")
    return tips
